from pathlib import Path
import json
import zipfile

from longyin_mod_installer.models import Catalog, CatalogMetadata, DownloadDefinition, ModEntry
from longyin_mod_installer.services.catalog import CatalogService
from longyin_mod_installer.services.mods import ModManager


def test_install_zip_tracks_manifest_and_uninstalls_cleanly(tmp_path: Path) -> None:
    game_dir = tmp_path / "Game"
    (game_dir / "Mods").mkdir(parents=True)
    local_catalog = tmp_path / "mod_repository" / "mods.json"
    local_catalog.parent.mkdir(parents=True)
    local_catalog.write_text("{}", encoding="utf-8")

    zip_path = tmp_path / "package.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("LongYinTalentTweaks.dll", b"dll".decode("latin1"))
        archive.writestr("modSample/Info.json", "{}")

    mod = ModEntry(
        id="sample-zip",
        name="Sample Zip Mod",
        version="1.0.0",
        description="",
        file_name=None,
        install_to="Mods",
        download=DownloadDefinition(type="file", repo_path=str(zip_path)),
    )
    catalog = Catalog(
        metadata=CatalogMetadata(
            name="Test",
            game_name="龙胤立志传",
            game_app_id=3202030,
            version="1.0.0",
        ),
        mods=[mod],
        source_name="Local",
        source_url=str(local_catalog),
    )

    manager = ModManager(CatalogService(local_catalog_path=local_catalog))
    installed_path = manager.install_mod(game_dir, catalog, [], [], mod)

    assert installed_path.exists()
    assert (game_dir / "Mods" / "LongYinTalentTweaks.dll").exists()
    assert (game_dir / "Mods" / "ModsOfLong" / "modSample").exists()

    manager.uninstall_mod(game_dir, mod.id)

    assert not (game_dir / "Mods" / "LongYinTalentTweaks.dll").exists()
    assert not (game_dir / "Mods" / "ModsOfLong" / "modSample").exists()


def test_install_local_dll_package_creates_manifest_and_can_uninstall(tmp_path: Path) -> None:
    game_dir = tmp_path / "Game"
    (game_dir / "Mods").mkdir(parents=True)
    dll_path = tmp_path / "LocalExample.dll"
    dll_path.write_bytes(b"example")

    manager = ModManager(CatalogService(local_catalog_path=tmp_path / "mod_repository" / "mods.json"))
    installed_path = manager.install_local_package(game_dir, dll_path)

    assert installed_path.exists()
    installed = manager.scan_installed_mods(game_dir)
    assert any(item.display_name == "LocalExample" for item in installed)

    manager.uninstall_mod(game_dir, "local-package-localexample")
    assert not installed_path.exists()


def test_scan_installed_mods_includes_mods_of_long_display_name(tmp_path: Path) -> None:
    game_dir = tmp_path / "Game"
    mod_dir = game_dir / "Mods" / "ModsOfLong" / "modTestPack"
    mod_dir.mkdir(parents=True)
    (mod_dir / "Info.json").write_text(json.dumps({"Name": "测试数据包"}, ensure_ascii=False), encoding="utf-8")
    (mod_dir / "Data").mkdir()
    (mod_dir / "Data" / "Sample.csv").write_text("id,name\n1,test", encoding="utf-8")

    manager = ModManager(CatalogService(local_catalog_path=tmp_path / "mod_repository" / "mods.json"))
    installed = manager.scan_installed_mods(game_dir)

    assert any(item.display_name == "测试数据包" and item.artifact_name == "modTestPack" for item in installed)
