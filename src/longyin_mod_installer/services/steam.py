from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constants import GAME_EXECUTABLE, TARGET_APP_ID, TARGET_GAME_NAME
from .keyvalues import parse_keyvalues

try:
    import winreg
except ImportError:  # pragma: no cover
    winreg = None  # type: ignore[assignment]


class SteamService:
    def find_game_directory(
        self,
        app_id: int = TARGET_APP_ID,
        game_name: str = TARGET_GAME_NAME,
    ) -> Path:
        steam_root = self.find_steam_root()
        if not steam_root:
            raise FileNotFoundError("未找到 Steam 安装目录。")

        for library in self.iter_library_paths(steam_root):
            manifest_path = library / "steamapps" / f"appmanifest_{app_id}.acf"
            if manifest_path.exists():
                return self._resolve_install_dir(library, manifest_path)

        for library in self.iter_library_paths(steam_root):
            for manifest_path in (library / "steamapps").glob("appmanifest_*.acf"):
                manifest = self.read_manifest(manifest_path)
                name = str(manifest.get("name", ""))
                if name == game_name:
                    return self._resolve_install_dir(library, manifest_path)

        raise FileNotFoundError(f"未在 Steam 库中找到 {game_name}。")

    def find_steam_root(self) -> Path | None:
        if winreg is not None:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                    steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
                    candidate = Path(str(steam_path))
                    if candidate.exists():
                        return candidate
            except OSError:
                pass

        for candidate in (
            Path(r"C:\Program Files (x86)\Steam"),
            Path(r"C:\Program Files\Steam"),
        ):
            if candidate.exists():
                return candidate
        return None

    def iter_library_paths(self, steam_root: Path) -> list[Path]:
        library_file = steam_root / "steamapps" / "libraryfolders.vdf"
        if not library_file.exists():
            return [steam_root]

        parsed = parse_keyvalues(library_file.read_text(encoding="utf-8"))
        payload = parsed.get("libraryfolders", parsed)
        libraries: list[Path] = []
        if isinstance(payload, dict):
            for key, value in payload.items():
                if not str(key).isdigit():
                    continue
                raw_path = value.get("path") if isinstance(value, dict) else value
                if not raw_path:
                    continue
                path = Path(str(raw_path))
                if path.exists():
                    libraries.append(path)

        if steam_root not in libraries:
            libraries.insert(0, steam_root)
        return libraries

    def read_manifest(self, manifest_path: Path) -> dict[str, Any]:
        parsed = parse_keyvalues(manifest_path.read_text(encoding="utf-8"))
        payload = parsed.get("AppState", parsed)
        if not isinstance(payload, dict):
            raise ValueError(f"无法解析 manifest: {manifest_path}")
        return payload

    def is_valid_game_directory(self, path: Path) -> bool:
        return path.exists() and path.is_dir() and (path / GAME_EXECUTABLE).exists()

    def _resolve_install_dir(self, library: Path, manifest_path: Path) -> Path:
        manifest = self.read_manifest(manifest_path)
        install_dir = manifest.get("installdir")
        if not install_dir:
            raise ValueError(f"manifest 中缺少 installdir: {manifest_path}")

        game_dir = library / "steamapps" / "common" / str(install_dir)
        if not self.is_valid_game_directory(game_dir):
            raise FileNotFoundError(f"识别到的游戏目录无效: {game_dir}")
        return game_dir
