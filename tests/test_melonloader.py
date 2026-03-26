from __future__ import annotations

import zipfile
from pathlib import Path

from longyin_mod_installer.constants import GAME_EXECUTABLE
from longyin_mod_installer.services.melonloader import MelonLoaderInstaller


def _write_zip(archive_path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(archive_path, "w") as archive:
        for relative_path, content in files.items():
            archive.writestr(relative_path, content)


def test_install_merges_dependencies_into_melonloader(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / GAME_EXECUTABLE).write_text("exe")

    melonloader_archive = tmp_path / "MelonLoader.x64.zip"
    dependencies_archive = tmp_path / "Dependencies.zip"
    _write_zip(
        melonloader_archive,
        {
            "MelonLoader/base.txt": "melon",
            "version.dll": "version",
        },
    )
    _write_zip(
        dependencies_archive,
        {
            "Dependencies/SupportModules/Il2Cpp.dll": "il2cpp",
            "Dependencies/CompatibilityLayers/IPA.dll": "ipa",
        },
    )

    installer = MelonLoaderInstaller(
        archive_path=melonloader_archive,
        dependencies_archive_path=dependencies_archive,
        cache_dir=tmp_path / "cache",
    )

    installer.install(game_dir)

    assert (game_dir / "version.dll").read_text() == "version"
    assert (game_dir / "MelonLoader" / "base.txt").read_text() == "melon"
    assert (game_dir / "MelonLoader" / "Dependencies" / "SupportModules" / "Il2Cpp.dll").read_text() == "il2cpp"
    assert (game_dir / "MelonLoader" / "Dependencies" / "CompatibilityLayers" / "IPA.dll").read_text() == "ipa"


def test_uninstall_removes_melonloader_directory_and_version_dll(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    melonloader_dir = game_dir / "MelonLoader"
    melonloader_dir.mkdir(parents=True)
    (game_dir / GAME_EXECUTABLE).write_text("exe")
    (game_dir / "version.dll").write_text("version")
    (melonloader_dir / "base.txt").write_text("melon")
    (game_dir / "notice.txt").write_text("keep")

    installer = MelonLoaderInstaller(cache_dir=tmp_path / "cache")

    installer.uninstall(game_dir)

    assert not melonloader_dir.exists()
    assert not (game_dir / "version.dll").exists()
    assert (game_dir / "notice.txt").read_text() == "keep"
