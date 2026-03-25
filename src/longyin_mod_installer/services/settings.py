from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..constants import (
    DEFAULT_GITHUB_API_BASE,
    DEFAULT_GITHUB_DOWNLOAD_BASE,
    SETTINGS_FILE_NAME,
    SOURCES_FILE_NAME,
    SOURCES_TEMPLATE_FILE_NAME,
)
from ..models import AppSettings, CatalogSource, ReleaseSource
from ..utils.runtime import (
    ensure_directory,
    get_application_root,
    get_distribution_root,
    get_user_config_dir,
    is_frozen_app,
)


class SettingsService:
    def __init__(self) -> None:
        self.config_dir = ensure_directory(get_user_config_dir())
        self.settings_path = self.config_dir / SETTINGS_FILE_NAME
        if is_frozen_app():
            self.sources_dir = ensure_directory(get_distribution_root())
            self.sources_path = self.sources_dir / SOURCES_FILE_NAME
            self.sources_template_path = self.sources_dir / SOURCES_TEMPLATE_FILE_NAME
        else:
            self.sources_dir = self.config_dir
            self.sources_path = self.sources_dir / SOURCES_FILE_NAME
            self.sources_template_path = get_application_root() / SOURCES_TEMPLATE_FILE_NAME

    def load(self) -> AppSettings:
        self._ensure_defaults()
        settings_data = self._load_json(self.settings_path, default={})
        sources_data = self._load_json(self.sources_path, default=self._default_sources_payload())
        sources = [
            CatalogSource(
                name=str(item.get("name", "未命名源")),
                catalog_url=str(item.get("catalog_url", "")),
                enabled=bool(item.get("enabled", True)),
            )
            for item in sources_data.get("sources", [])
        ]
        release_sources = [
            ReleaseSource(
                name=str(item.get("name", "未命名 Release 源")),
                api_base=str(item.get("api_base", DEFAULT_GITHUB_API_BASE)),
                download_base=str(item.get("download_base", DEFAULT_GITHUB_DOWNLOAD_BASE)),
                enabled=bool(item.get("enabled", True)),
            )
            for item in sources_data.get("release_sources", self._default_sources_payload()["release_sources"])
        ]
        return AppSettings(
            game_directory=str(settings_data.get("game_directory", "")),
            catalog_sources=sources,
            release_sources=release_sources,
        )

    def save(self, settings: AppSettings) -> None:
        self._ensure_defaults()
        payload = {
            "game_directory": settings.game_directory,
        }
        self.settings_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _ensure_defaults(self) -> None:
        ensure_directory(self.config_dir)
        if not self.settings_path.exists():
            self.settings_path.write_text(
                json.dumps(
                    {"game_directory": ""},
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        if not self.sources_path.exists():
            if self.sources_template_path.exists():
                shutil.copy2(self.sources_template_path, self.sources_path)
            else:
                self.sources_path.write_text(
                    json.dumps(self._default_sources_payload(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            return

        current = self._load_json(self.sources_path, default=self._default_sources_payload())
        changed = False
        if "sources" not in current:
            current["sources"] = self._default_sources_payload()["sources"]
            changed = True
        if "release_sources" not in current:
            current["release_sources"] = self._default_sources_payload()["release_sources"]
            changed = True
        if changed:
            self.sources_path.write_text(
                json.dumps(current, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    @staticmethod
    def _load_json(path: Path, default: dict[str, object]) -> dict[str, object]:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _default_sources_payload() -> dict[str, object]:
        return {
            "sources": [
                {
                    "name": "GitHub Raw",
                    "catalog_url": "https://raw.githubusercontent.com/magicskysword/LongYinModInstaller/master/mod_repository/mods.json",
                    "enabled": True,
                },
                {
                    "name": "jsDelivr 镜像",
                    "catalog_url": "https://cdn.jsdelivr.net/gh/magicskysword/LongYinModInstaller@master/mod_repository/mods.json",
                    "enabled": True,
                },
            ],
            "release_sources": [
                {
                    "name": "GitHub 镜像 gh-proxy",
                    "api_base": "https://gh-proxy.com/https://api.github.com",
                    "download_base": "https://gh-proxy.com/https://github.com",
                    "enabled": True
                },
                {
                    "name": "GitHub 镜像 gh-proxy v6",
                    "api_base": "https://v6.gh-proxy.org/https://api.github.com",
                    "download_base": "https://v6.gh-proxy.org/https://github.com",
                    "enabled": True
                },
                {
                    "name": "GitHub 镜像 mirror.ghproxy",
                    "api_base": "https://mirror.ghproxy.com/https://api.github.com",
                    "download_base": "https://mirror.ghproxy.com/https://github.com",
                    "enabled": True
                },
                {
                    "name": "GitHub 原址",
                    "api_base": DEFAULT_GITHUB_API_BASE,
                    "download_base": DEFAULT_GITHUB_DOWNLOAD_BASE,
                    "enabled": True,
                },
            ],
        }
