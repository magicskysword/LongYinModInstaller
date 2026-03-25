import json
from pathlib import Path

from longyin_mod_installer.constants import SETTINGS_FILE_NAME, SOURCES_FILE_NAME, SOURCES_TEMPLATE_FILE_NAME
from longyin_mod_installer.services.settings import SettingsService
from longyin_mod_installer.utils.runtime import get_local_catalog_path


def test_catalog_sources_example_matches_default_payload() -> None:
    root = Path(__file__).resolve().parents[1]
    example_path = root / SOURCES_TEMPLATE_FILE_NAME

    assert json.loads(example_path.read_text(encoding="utf-8")) == SettingsService._default_sources_payload()


def test_settings_service_uses_executable_directory_for_sources_when_frozen(monkeypatch, tmp_path: Path) -> None:
    import longyin_mod_installer.services.settings as settings_module

    config_dir = tmp_path / "config"
    deploy_dir = tmp_path / "dist"

    monkeypatch.setattr(settings_module, "is_frozen_app", lambda: True)
    monkeypatch.setattr(settings_module, "get_distribution_root", lambda: deploy_dir)
    monkeypatch.setattr(settings_module, "get_user_config_dir", lambda: config_dir)

    service = settings_module.SettingsService()

    assert service.settings_path == config_dir / SETTINGS_FILE_NAME
    assert service.sources_path == deploy_dir / SOURCES_FILE_NAME
    assert service.sources_template_path == deploy_dir / SOURCES_TEMPLATE_FILE_NAME


def test_get_local_catalog_path_uses_executable_directory_when_frozen(monkeypatch, tmp_path: Path) -> None:
    import longyin_mod_installer.utils.runtime as runtime_module

    exe_path = tmp_path / "dist" / "LongYinModInstaller.exe"
    exe_path.parent.mkdir(parents=True)
    exe_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(runtime_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_module.sys, "executable", str(exe_path), raising=False)

    assert get_local_catalog_path() == exe_path.parent / "mod_repository" / "mods.json"
