from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from urllib.parse import urljoin

import requests

from ..constants import DEFAULT_GITHUB_DOWNLOAD_BASE
from ..models import Catalog, CatalogMetadata, CatalogSource, DownloadDefinition, ModEntry, ReleaseSource
from ..utils.runtime import get_local_catalog_path


def is_http_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


class CatalogService:
    def __init__(self, local_catalog_path: Path | None = None) -> None:
        self.local_catalog_path = local_catalog_path or get_local_catalog_path()
        self.session = requests.Session()

    def load_catalog(
        self,
        sources: list[CatalogSource],
        log: callable | None = None,
    ) -> Catalog:
        errors: list[str] = []

        for source in sources:
            if not source.enabled:
                continue
            if "<" in source.catalog_url and ">" in source.catalog_url:
                if log:
                    log(f"跳过未配置的仓库源：{source.name}")
                continue
            try:
                data = self._read_json(source.catalog_url)
                if log:
                    log(f"已从 {source.name} 读取 Mod 列表。")
                return self._parse_catalog(data, source.name, source.catalog_url)
            except Exception as exc:  # pragma: no cover
                errors.append(f"{source.name}: {exc}")

        data = self._read_json(str(self.local_catalog_path))
        if log:
            for error in errors:
                log(f"远程仓库失败：{error}")
            log("已回退到内置 Mod 仓库。")
        return self._parse_catalog(data, "内置仓库", str(self.local_catalog_path))

    def build_file_download_candidates(
        self,
        mod: ModEntry,
        catalog: Catalog,
        sources: list[CatalogSource],
    ) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()

        def add(candidate: str | None) -> None:
            if not candidate:
                return
            key = candidate.lower()
            if key in seen:
                return
            seen.add(key)
            candidates.append(candidate)

        add(mod.download.url)
        for mirror in mod.download.mirrors:
            add(mirror)

        if mod.download.repo_path:
            add(self.resolve_repo_path(catalog.source_url, mod.download.repo_path))
            for source in sources:
                if not source.enabled:
                    continue
                if "<" in source.catalog_url and ">" in source.catalog_url:
                    continue
                add(self.resolve_repo_path(source.catalog_url, mod.download.repo_path))
            add(str((self.local_catalog_path.parent / mod.download.repo_path).resolve()))

        return candidates

    @staticmethod
    def build_release_api_url(source: ReleaseSource, repo: str, tag: str) -> str:
        api_base = source.api_base.rstrip("/")
        if tag.lower() == "latest":
            return f"{api_base}/repos/{repo}/releases/latest"
        return f"{api_base}/repos/{repo}/releases/tags/{tag}"

    @staticmethod
    def build_release_download_url(
        source: ReleaseSource,
        repo: str,
        tag: str,
        asset_name: str,
    ) -> str:
        base = source.download_base.rstrip("/") or DEFAULT_GITHUB_DOWNLOAD_BASE
        return f"{base}/{repo}/releases/download/{tag}/{asset_name}"

    @staticmethod
    def asset_matches(mod: ModEntry, asset_name: str) -> bool:
        lowered_name = asset_name.lower()
        if Path(asset_name).suffix.lower() not in {".dll", ".zip"}:
            return False

        explicit_name = (mod.download.asset_name or "").strip()
        if explicit_name:
            return lowered_name == explicit_name.lower()

        patterns = [pattern.strip() for pattern in mod.download.asset_patterns if pattern.strip()]
        if patterns:
            return any(fnmatch.fnmatch(lowered_name, pattern.lower()) for pattern in patterns)

        file_name = (mod.file_name or "").strip()
        if file_name and lowered_name == file_name.lower():
            return True

        stem_candidates = {
            mod.id.lower(),
            mod.name.lower().replace(" ", ""),
            Path(file_name).stem.lower() if file_name else "",
        }
        normalized_asset = lowered_name.replace("-", "").replace("_", "").replace(" ", "")
        return any(candidate and candidate in normalized_asset for candidate in stem_candidates)

    @staticmethod
    def resolve_repo_path(catalog_location: str | None, repo_path: str) -> str | None:
        if not catalog_location:
            return None
        normalized_repo_path = repo_path.replace("\\", "/")
        if is_http_url(catalog_location):
            base = catalog_location.rsplit("/", 1)[0] + "/"
            return urljoin(base, normalized_repo_path)
        return str((Path(catalog_location).resolve().parent / repo_path).resolve())

    def _read_json(self, location: str) -> dict[str, object]:
        if is_http_url(location):
            response = self.session.get(location, timeout=15)
            response.raise_for_status()
            return response.json()
        return json.loads(Path(location).read_text(encoding="utf-8"))

    @staticmethod
    def _parse_catalog(data: dict[str, object], source_name: str, source_url: str | None) -> Catalog:
        repository = data.get("repository", {})
        if not isinstance(repository, dict):
            raise ValueError("仓库元数据格式错误。")

        metadata = CatalogMetadata(
            name=str(repository.get("name", "未命名仓库")),
            game_name=str(repository.get("game_name", "")),
            game_app_id=int(repository.get("game_app_id", 0)),
            version=str(repository.get("version", "未标注")),
            updated_at=str(repository.get("updated_at")) if repository.get("updated_at") else None,
        )

        mods: list[ModEntry] = []
        for item in data.get("mods", []):
            if not isinstance(item, dict):
                continue
            download_data = item.get("download", {})
            if not isinstance(download_data, dict):
                download_data = {}
            mods.append(
                ModEntry(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    version=str(item.get("version", "未标注")),
                    description=str(item.get("description", "")),
                    file_name=str(item.get("file_name")) if item.get("file_name") else None,
                    install_to=str(item.get("install_to", "Mods")),
                    download=DownloadDefinition(
                        type=str(download_data.get("type", "file")),
                        url=str(download_data.get("url")) if download_data.get("url") else None,
                        mirrors=[str(entry) for entry in download_data.get("mirrors", [])],
                        repo_path=str(download_data.get("repo_path")) if download_data.get("repo_path") else None,
                        repo=str(download_data.get("repo")) if download_data.get("repo") else None,
                        tag=str(download_data.get("tag", "latest")),
                        asset_name=str(download_data.get("asset_name")) if download_data.get("asset_name") else None,
                        asset_patterns=[str(entry) for entry in download_data.get("asset_patterns", [])],
                    ),
                )
            )

        return Catalog(
            metadata=metadata,
            mods=mods,
            source_name=source_name,
            source_url=source_url,
        )
