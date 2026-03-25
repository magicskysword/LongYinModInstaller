from __future__ import annotations

import fnmatch
import json
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from ..constants import (
    BACKUP_DIRECTORY_NAME,
    INSTALLER_STATE_DIRECTORY_NAME,
    INSTALL_MANIFESTS_DIRECTORY_NAME,
    MODS_DIRECTORY_NAME,
    MODS_OF_LONG_DIRECTORY_NAME,
)
from ..models import (
    Catalog,
    CatalogSource,
    DownloadDefinition,
    InstallRecord,
    InstalledMod,
    ManagedInstallManifest,
    ModEntry,
    ReleaseSource,
)
from ..utils.runtime import ensure_directory, get_user_config_dir, safe_join
from .catalog import CatalogService, is_http_url

USER_AGENT = "LongYinModInstaller/0.1"


@dataclass(slots=True)
class DownloadCandidate:
    url: str
    label: str


class ModManager:
    def __init__(self, catalog_service: CatalogService) -> None:
        self.catalog_service = catalog_service
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.cache_dir = ensure_directory(get_user_config_dir() / "cache")
        self.backup_dir = ensure_directory(get_user_config_dir() / BACKUP_DIRECTORY_NAME)

    def scan_installed_mods(self, game_dir: Path, catalog: Catalog | None = None) -> list[InstalledMod]:
        mods_dir = game_dir / MODS_DIRECTORY_NAME
        if not mods_dir.exists():
            return []

        known_mods_by_id = {mod.id: mod for mod in (catalog.mods if catalog else [])}
        known_names_by_file = {
            (mod.file_name or "").lower(): mod.name
            for mod in (catalog.mods if catalog else [])
            if mod.file_name
        }

        installed: list[InstalledMod] = []
        claimed_paths: set[str] = set()

        for manifest in self._load_manifests(game_dir):
            existing_paths = self._existing_manifest_paths(game_dir, manifest)
            if not existing_paths:
                continue

            primary_path = next(
                (path for path in existing_paths if path.name.lower() == manifest.primary_name.lower()),
                existing_paths[0],
            )
            for path in existing_paths:
                claimed_paths.add(str(path.resolve()).lower())

            latest_mtime = max(self._path_latest_mtime(path) for path in existing_paths)
            installed.append(
                InstalledMod(
                    identifier=manifest.mod_id,
                    display_name=known_mods_by_id.get(manifest.mod_id, None).name
                    if manifest.mod_id in known_mods_by_id
                    else manifest.mod_name,
                    artifact_name=manifest.primary_name,
                    path=str(primary_path),
                    size_bytes=sum(self._path_total_size(path) for path in existing_paths),
                    modified_at=datetime.fromtimestamp(latest_mtime),
                    managed_by_catalog=manifest.mod_id in known_mods_by_id,
                    mod_id=manifest.mod_id,
                )
            )

        for dll_path in sorted(mods_dir.glob("*.dll"), key=lambda item: item.name.lower()):
            resolved = str(dll_path.resolve()).lower()
            if resolved in claimed_paths:
                continue

            stat = dll_path.stat()
            installed.append(
                InstalledMod(
                    identifier=dll_path.name,
                    display_name=known_names_by_file.get(dll_path.name.lower(), dll_path.name),
                    artifact_name=dll_path.name,
                    path=str(dll_path),
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                    managed_by_catalog=dll_path.name.lower() in known_names_by_file,
                    mod_id=None,
                )
            )

        mods_of_long_dir = mods_dir / MODS_OF_LONG_DIRECTORY_NAME
        if mods_of_long_dir.exists():
            for mod_dir in sorted(mods_of_long_dir.glob("mod*"), key=lambda item: item.name.lower()):
                resolved = str(mod_dir.resolve()).lower()
                if resolved in claimed_paths:
                    continue
                installed.append(
                    InstalledMod(
                        identifier=self._relative_to_game_root(game_dir, mod_dir),
                        display_name=self._resolve_data_mod_display_name(mod_dir),
                        artifact_name=mod_dir.name,
                        path=str(mod_dir),
                        size_bytes=self._path_total_size(mod_dir),
                        modified_at=datetime.fromtimestamp(self._path_latest_mtime(mod_dir)),
                        managed_by_catalog=False,
                        mod_id=None,
                    )
                )

        installed.sort(key=lambda item: (item.mod_id is None, item.display_name.lower(), item.artifact_name.lower()))
        return installed

    def install_mods(
        self,
        game_dir: Path,
        catalog: Catalog,
        catalog_sources: list[CatalogSource],
        release_sources: list[ReleaseSource],
        mod_ids: list[str],
        log: callable | None = None,
    ) -> list[Path]:
        mods_by_id = {mod.id: mod for mod in catalog.mods}
        installed_paths: list[Path] = []
        for mod_id in mod_ids:
            mod = mods_by_id.get(mod_id)
            if not mod:
                raise ValueError(f"引用了不存在的 Mod：{mod_id}")
            installed_paths.append(
                self.install_mod(game_dir, catalog, catalog_sources, release_sources, mod, log)
            )
        return installed_paths

    def uninstall_mod(
        self,
        game_dir: Path,
        identifier: str,
        log: callable | None = None,
    ) -> Path:
        manifest_path = self._manifest_path(game_dir, identifier)
        if manifest_path.exists():
            manifest = self._load_manifest_file(manifest_path)
            self._reverse_records(game_dir, manifest.records, log=log, cleanup_backups=True)
            manifest_path.unlink(missing_ok=True)
            if log:
                log(f"已按安装记录卸载 {manifest.mod_name}")
            return manifest_path

        target_path = self._resolve_unmanaged_identifier(game_dir, identifier)
        if not target_path.exists():
            raise FileNotFoundError(f"Mod 文件不存在：{target_path}")
        backup_path = self.backup_dir / Path(self._relative_to_game_root(game_dir, target_path))
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.is_dir():
            if backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            shutil.copytree(target_path, backup_path)
            shutil.rmtree(target_path)
        else:
            shutil.copy2(target_path, backup_path)
            target_path.unlink()
        if log:
            log(f"已卸载 {identifier}，备份到 {backup_path}")
        return backup_path

    def install_mod(
        self,
        game_dir: Path,
        catalog: Catalog,
        catalog_sources: list[CatalogSource],
        release_sources: list[ReleaseSource],
        mod: ModEntry,
        log: callable | None = None,
    ) -> Path:
        existing_manifest_path = self._manifest_path(game_dir, mod.id)
        if existing_manifest_path.exists():
            if log:
                log(f"{mod.name} 已存在旧安装记录，先执行清理。")
            self.uninstall_mod(game_dir, mod.id, log=log)

        candidates = self._build_download_candidates(mod, catalog, catalog_sources, release_sources, log)
        if not candidates:
            raise ValueError(f"Mod {mod.name} 没有可用的下载来源。")

        last_error: Exception | None = None
        for candidate in candidates:
            payload_path: Path | None = None
            is_temporary = False
            try:
                if log:
                    log(f"正在准备 {mod.name}：{candidate.label}")
                payload_path, is_temporary = self._materialize_candidate(candidate.url)
                manifest = self._install_payload(game_dir, mod, payload_path, log)
                self._save_manifest(game_dir, manifest)
                installed_path = safe_join(game_dir, manifest.records[0].path)
                if log:
                    log(f"{mod.name} 已安装到 {installed_path}")
                return installed_path
            except Exception as exc:
                last_error = exc
                if log:
                    log(f"{mod.name} 来源失败：{candidate.label}，原因：{exc}")
            finally:
                if is_temporary and payload_path and payload_path.exists():
                    payload_path.unlink(missing_ok=True)

        raise RuntimeError(f"安装 {mod.name} 失败：{last_error}")

    def install_local_package(
        self,
        game_dir: Path,
        package_path: Path,
        log: callable | None = None,
    ) -> Path:
        package_path = package_path.resolve()
        if not package_path.exists():
            raise FileNotFoundError(f"本地文件不存在：{package_path}")
        if package_path.suffix.lower() not in {".dll", ".zip"}:
            raise ValueError(f"仅支持安装 .dll 或 .zip：{package_path.name}")

        local_mod = self._build_local_mod_entry(package_path)
        existing_manifest_path = self._manifest_path(game_dir, local_mod.id)
        if existing_manifest_path.exists():
            self.uninstall_mod(game_dir, local_mod.id, log=log)

        manifest = self._install_payload(game_dir, local_mod, package_path, log)
        self._save_manifest(game_dir, manifest)
        installed_path = safe_join(game_dir, manifest.records[0].path)
        if log:
            log(f"本地包 {package_path.name} 已安装到 {installed_path}")
        return installed_path

    def _build_download_candidates(
        self,
        mod: ModEntry,
        catalog: Catalog,
        catalog_sources: list[CatalogSource],
        release_sources: list[ReleaseSource],
        log: callable | None = None,
    ) -> list[DownloadCandidate]:
        download_type = mod.download.type.lower()
        if download_type == "file":
            return [
                DownloadCandidate(url=url, label=url)
                for url in self.catalog_service.build_file_download_candidates(mod, catalog, catalog_sources)
            ]
        if download_type == "repo_release":
            return self._build_release_download_candidates(mod, release_sources, log)
        raise ValueError(f"不支持的下载类型：{mod.download.type}")

    def _build_release_download_candidates(
        self,
        mod: ModEntry,
        release_sources: list[ReleaseSource],
        log: callable | None = None,
    ) -> list[DownloadCandidate]:
        if not mod.download.repo:
            raise ValueError(f"{mod.name} 缺少 repo_release.repo 配置。")

        candidates: list[DownloadCandidate] = []
        seen: set[str] = set()
        errors: list[str] = []

        for source in release_sources:
            if not source.enabled:
                continue
            if "<" in source.api_base or "<" in source.download_base:
                if log:
                    log(f"跳过未配置的 Release 源：{source.name}")
                continue

            release_url = self.catalog_service.build_release_api_url(source, mod.download.repo, mod.download.tag)
            try:
                response = self.session.get(release_url, timeout=30)
                response.raise_for_status()
                release_data = response.json()
                tag_name = str(release_data.get("tag_name") or mod.download.tag)
                asset = self._select_release_asset(mod, release_data.get("assets", []))
                asset_name = str(asset["name"])
                for url in (
                    self.catalog_service.build_release_download_url(source, mod.download.repo, tag_name, asset_name),
                    str(asset.get("browser_download_url") or ""),
                ):
                    normalized = url.strip()
                    if not normalized:
                        continue
                    key = normalized.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(
                        DownloadCandidate(
                            url=normalized,
                            label=f"{source.name} · {asset_name}",
                        )
                    )
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")

        if not candidates:
            raise RuntimeError(f"未能解析 {mod.name} 的 Release 资产：{' | '.join(errors)}")
        return candidates

    @staticmethod
    def _build_local_mod_entry(package_path: Path) -> ModEntry:
        stem = package_path.stem.strip() or package_path.name
        sanitized = "".join(ch.lower() if ch.isalnum() else "-" for ch in stem).strip("-")
        if not sanitized:
            sanitized = "local-package"

        file_name = package_path.name if package_path.suffix.lower() == ".dll" else None
        return ModEntry(
            id=f"local-package-{sanitized}",
            name=stem,
            version="本地导入",
            description=f"从本地文件导入：{package_path.name}",
            file_name=file_name,
            install_to=MODS_DIRECTORY_NAME,
            download=DownloadDefinition(type="file", repo_path=str(package_path)),
        )

    def _select_release_asset(self, mod: ModEntry, assets: object) -> dict[str, object]:
        if not isinstance(assets, list):
            raise ValueError("Release 资产列表格式错误。")

        scored: list[tuple[tuple[int, int, int], dict[str, object]]] = []
        for item in assets:
            if not isinstance(item, dict):
                continue
            asset_name = str(item.get("name", "")).strip()
            if not asset_name or not self._is_supported_asset_name(asset_name):
                continue
            if not self.catalog_service.asset_matches(mod, asset_name):
                continue
            scored.append((self._score_release_asset(mod, asset_name), item))

        if not scored:
            raise ValueError("Release 中没有匹配到 dll 或 zip 资产。")

        scored.sort(key=lambda entry: entry[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            names = ", ".join(str(item.get("name", "")) for _, item in scored[:5])
            raise ValueError(f"匹配到多个同优先级资产，请补充 asset_name 或 asset_patterns：{names}")
        return scored[0][1]

    @staticmethod
    def _is_supported_asset_name(asset_name: str) -> bool:
        lowered = asset_name.lower()
        if lowered.startswith("source code"):
            return False
        return Path(asset_name).suffix.lower() in {".dll", ".zip"}

    @staticmethod
    def _score_release_asset(mod: ModEntry, asset_name: str) -> tuple[int, int, int]:
        lowered = asset_name.lower()
        explicit_name = (mod.download.asset_name or "").lower()
        file_name = (mod.file_name or "").lower()
        patterns = [pattern.lower() for pattern in mod.download.asset_patterns]

        exact_name = 1 if explicit_name and lowered == explicit_name else 0
        exact_file_name = 1 if file_name and lowered == file_name else 0
        matched_pattern = 1 if any(pattern and fnmatch.fnmatch(lowered, pattern) for pattern in patterns) else 0
        suffix_priority = 1 if Path(asset_name).suffix.lower() == ".zip" else 0
        return (exact_name + exact_file_name, matched_pattern, suffix_priority)

    def _materialize_candidate(self, candidate: str) -> tuple[Path, bool]:
        if is_http_url(candidate):
            parsed = urlparse(candidate)
            suffix = Path(parsed.path).suffix or ".bin"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=self.cache_dir) as handle:
                with self.session.get(candidate, stream=True, timeout=120) as response:
                    response.raise_for_status()
                    for chunk in response.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            handle.write(chunk)
                temp_path = Path(handle.name)
            return temp_path, True

        path = Path(candidate)
        if not path.exists():
            raise FileNotFoundError(f"本地文件不存在：{path}")
        return path, False

    def _install_payload(
        self,
        game_dir: Path,
        mod: ModEntry,
        payload_path: Path,
        log: callable | None = None,
    ) -> ManagedInstallManifest:
        suffix = payload_path.suffix.lower()
        records: list[InstallRecord] = []
        backup_root = ensure_directory(
            self.backup_dir / f"{mod.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        )

        try:
            if suffix == ".dll":
                destination = game_dir / MODS_DIRECTORY_NAME / (mod.file_name or payload_path.name)
                self._install_file(game_dir, payload_path, destination, backup_root, records)
                primary_name = destination.name
            elif suffix == ".zip":
                primary_name = self._install_zip_payload(game_dir, payload_path, backup_root, records, log)
            else:
                raise ValueError(f"不支持的安装包类型：{payload_path.name}")
        except Exception:
            self._reverse_records(game_dir, records, log=log, cleanup_backups=False)
            raise

        if not records:
            raise ValueError("没有生成任何安装记录。")

        return ManagedInstallManifest(
            mod_id=mod.id,
            mod_name=mod.name,
            version=mod.version,
            primary_name=primary_name,
            records=records,
            installed_at=datetime.now().isoformat(timespec="seconds"),
        )

    def _install_zip_payload(
        self,
        game_dir: Path,
        payload_path: Path,
        backup_root: Path,
        records: list[InstallRecord],
        log: callable | None = None,
    ) -> str:
        with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_dir:
            temp_root = Path(temp_dir)
            with zipfile.ZipFile(payload_path) as archive:
                archive.extractall(temp_root)

            mod_dirs = self._discover_mod_directories(temp_root)
            dll_files = self._discover_dll_files(temp_root, excluded_dirs=mod_dirs)

            if not dll_files and not mod_dirs:
                raise ValueError("zip 内未找到 dll 或 mod* 数据目录。")

            for dll_path in dll_files:
                destination = game_dir / MODS_DIRECTORY_NAME / dll_path.name
                self._install_file(game_dir, dll_path, destination, backup_root, records)
                if log:
                    log(f"已写入 DLL：{destination.name}")

            for mod_dir in mod_dirs:
                destination = game_dir / MODS_DIRECTORY_NAME / MODS_OF_LONG_DIRECTORY_NAME / mod_dir.name
                self._install_directory(game_dir, mod_dir, destination, backup_root, records)
                if log:
                    log(f"已写入数据 Mod：{destination.name}")

            if dll_files:
                return dll_files[0].name
            return mod_dirs[0].name

    def _install_file(
        self,
        game_dir: Path,
        source_file: Path,
        target_file: Path,
        backup_root: Path,
        records: list[InstallRecord],
    ) -> None:
        backup_path = self._backup_target(game_dir, target_file, backup_root)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)
        records.append(
            InstallRecord(
                path=self._relative_to_game_root(game_dir, target_file),
                record_type="file",
                backup_path=str(backup_path) if backup_path else None,
            )
        )

    def _install_directory(
        self,
        game_dir: Path,
        source_dir: Path,
        target_dir: Path,
        backup_root: Path,
        records: list[InstallRecord],
    ) -> None:
        backup_path = self._backup_target(game_dir, target_dir, backup_root)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, target_dir)
        records.append(
            InstallRecord(
                path=self._relative_to_game_root(game_dir, target_dir),
                record_type="directory",
                backup_path=str(backup_path) if backup_path else None,
            )
        )

    def _backup_target(self, game_dir: Path, target_path: Path, backup_root: Path) -> Path | None:
        if not target_path.exists():
            return None

        backup_path = backup_root / Path(self._relative_to_game_root(game_dir, target_path))
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.is_dir():
            shutil.copytree(target_path, backup_path)
        else:
            shutil.copy2(target_path, backup_path)
        return backup_path

    def _reverse_records(
        self,
        game_dir: Path,
        records: list[InstallRecord],
        log: callable | None = None,
        cleanup_backups: bool = False,
    ) -> None:
        for record in reversed(records):
            target_path = safe_join(game_dir, record.path)
            if target_path.exists():
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()

            if record.backup_path:
                backup_path = Path(record.backup_path)
                if backup_path.exists():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    if record.record_type == "directory":
                        shutil.copytree(backup_path, target_path)
                    else:
                        shutil.copy2(backup_path, target_path)
                    if cleanup_backups:
                        if backup_path.is_dir():
                            shutil.rmtree(backup_path, ignore_errors=True)
                        else:
                            backup_path.unlink(missing_ok=True)
            if log:
                log(f"已回滚 {record.path}")

    def _discover_mod_directories(self, extracted_root: Path) -> list[Path]:
        candidates = sorted(
            (
                path
                for path in extracted_root.rglob("*")
                if path.is_dir() and path.name.lower().startswith("mod")
            ),
            key=lambda item: (len(item.parts), str(item).lower()),
        )

        selected: list[Path] = []
        for candidate in candidates:
            if any(parent in candidate.parents for parent in selected):
                continue
            selected.append(candidate)
        return selected

    def _discover_dll_files(self, extracted_root: Path, excluded_dirs: list[Path]) -> list[Path]:
        excluded_resolved = {directory.resolve() for directory in excluded_dirs}
        dlls: list[Path] = []
        for dll_path in extracted_root.rglob("*.dll"):
            if any(parent.resolve() in excluded_resolved for parent in dll_path.parents):
                continue
            dlls.append(dll_path)
        dlls.sort(key=lambda item: str(item).lower())
        return dlls

    def _save_manifest(self, game_dir: Path, manifest: ManagedInstallManifest) -> None:
        manifest_path = self._manifest_path(game_dir, manifest.mod_id)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "mod_id": manifest.mod_id,
                    "mod_name": manifest.mod_name,
                    "version": manifest.version,
                    "primary_name": manifest.primary_name,
                    "installed_at": manifest.installed_at,
                    "records": [asdict(record) for record in manifest.records],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _load_manifests(self, game_dir: Path) -> list[ManagedInstallManifest]:
        manifest_dir = self._manifest_dir(game_dir)
        if not manifest_dir.exists():
            return []

        manifests: list[ManagedInstallManifest] = []
        for manifest_path in sorted(manifest_dir.glob("*.json")):
            try:
                manifests.append(self._load_manifest_file(manifest_path))
            except Exception:
                continue
        return manifests

    @staticmethod
    def _load_manifest_file(path: Path) -> ManagedInstallManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ManagedInstallManifest(
            mod_id=str(data.get("mod_id", "")),
            mod_name=str(data.get("mod_name", "")),
            version=str(data.get("version", "")),
            primary_name=str(data.get("primary_name", "")),
            installed_at=str(data.get("installed_at", "")),
            records=[
                InstallRecord(
                    path=str(item.get("path", "")),
                    record_type=str(item.get("record_type", "file")),
                    backup_path=str(item.get("backup_path")) if item.get("backup_path") else None,
                )
                for item in data.get("records", [])
                if isinstance(item, dict)
            ],
        )

    def _manifest_dir(self, game_dir: Path) -> Path:
        return game_dir / MODS_DIRECTORY_NAME / INSTALLER_STATE_DIRECTORY_NAME / INSTALL_MANIFESTS_DIRECTORY_NAME

    def _manifest_path(self, game_dir: Path, mod_id: str) -> Path:
        safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in mod_id)
        return self._manifest_dir(game_dir) / f"{safe_name}.json"

    def _resolve_unmanaged_identifier(self, game_dir: Path, identifier: str) -> Path:
        if "/" in identifier or "\\" in identifier:
            return safe_join(game_dir, identifier)
        return game_dir / MODS_DIRECTORY_NAME / identifier

    @staticmethod
    def _resolve_data_mod_display_name(mod_dir: Path) -> str:
        info_path = mod_dir / "Info.json"
        if info_path.exists():
            try:
                data = json.loads(info_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for key, value in data.items():
                        if key.lower() == "name" and isinstance(value, str) and value.strip():
                            return value.strip()
            except Exception:
                pass

        folder_name = mod_dir.name
        if folder_name.lower().startswith("mod"):
            fallback = folder_name[3:].lstrip(" _-")
            if fallback:
                return fallback
        return folder_name

    @staticmethod
    def _relative_to_game_root(game_dir: Path, target_path: Path) -> str:
        return target_path.relative_to(game_dir).as_posix()

    @staticmethod
    def _existing_manifest_paths(game_dir: Path, manifest: ManagedInstallManifest) -> list[Path]:
        paths: list[Path] = []
        for record in manifest.records:
            target = safe_join(game_dir, record.path)
            if target.exists():
                paths.append(target)
        return paths

    @staticmethod
    def _path_total_size(path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())

    @staticmethod
    def _path_latest_mtime(path: Path) -> float:
        if path.is_file():
            return path.stat().st_mtime
        mtimes = [path.stat().st_mtime]
        mtimes.extend(item.stat().st_mtime for item in path.rglob("*"))
        return max(mtimes)
