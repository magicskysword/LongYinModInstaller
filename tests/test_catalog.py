from pathlib import Path

from longyin_mod_installer.models import (
    Catalog,
    CatalogMetadata,
    CatalogSource,
    DownloadDefinition,
    ModEntry,
    ReleaseSource,
)
from longyin_mod_installer.services.catalog import CatalogService


def test_build_file_download_candidates_includes_remote_and_local(tmp_path: Path) -> None:
    local_catalog = tmp_path / "mod_repository" / "mods.json"
    local_catalog.parent.mkdir(parents=True)
    local_catalog.write_text("{}", encoding="utf-8")

    service = CatalogService(local_catalog_path=local_catalog)
    mod = ModEntry(
        id="example",
        name="Example",
        version="1.0.0",
        description="",
        file_name="Example.dll",
        install_to="Mods",
        download=DownloadDefinition(type="file", repo_path="files/Example.dll"),
    )
    catalog = Catalog(
        metadata=CatalogMetadata(
            name="Example",
            game_name="龙胤立志传",
            game_app_id=3202030,
            version="1.0.0",
        ),
        mods=[mod],
        source_name="GitHub Raw",
        source_url="https://raw.githubusercontent.com/user/repo/main/mod_repository/mods.json",
    )

    candidates = service.build_file_download_candidates(
        mod,
        catalog,
        [
            CatalogSource(
                name="Mirror",
                catalog_url="https://cdn.jsdelivr.net/gh/user/repo@main/mod_repository/mods.json",
                enabled=True,
            )
        ],
    )

    assert "https://raw.githubusercontent.com/user/repo/main/mod_repository/files/Example.dll" in candidates
    assert "https://cdn.jsdelivr.net/gh/user/repo@main/mod_repository/files/Example.dll" in candidates
    assert str((local_catalog.parent / "files" / "Example.dll").resolve()) in candidates


def test_build_release_urls_from_configured_source() -> None:
    source = ReleaseSource(
        name="Mirror",
        api_base="https://gh-api.example.com",
        download_base="https://gh-download.example.com",
        enabled=True,
    )

    assert (
        CatalogService.build_release_api_url(source, "owner/repo", "latest")
        == "https://gh-api.example.com/repos/owner/repo/releases/latest"
    )
    assert (
        CatalogService.build_release_api_url(source, "owner/repo", "v1.2.3")
        == "https://gh-api.example.com/repos/owner/repo/releases/tags/v1.2.3"
    )
    assert (
        CatalogService.build_release_download_url(source, "owner/repo", "v1.2.3", "Example.zip")
        == "https://gh-download.example.com/owner/repo/releases/download/v1.2.3/Example.zip"
    )


def test_asset_matches_file_name_and_patterns() -> None:
    mod = ModEntry(
        id="the-book-of-long",
        name="The Book Of Long",
        version="1.0.0",
        description="",
        file_name="TheBookOfLong.dll",
        install_to="Mods",
        download=DownloadDefinition(type="repo_release", repo="owner/repo"),
    )
    assert CatalogService.asset_matches(mod, "TheBookOfLong.dll")

    patterned_mod = ModEntry(
        id="data-pack",
        name="Data Pack",
        version="1.0.0",
        description="",
        file_name=None,
        install_to="Mods",
        download=DownloadDefinition(
            type="repo_release",
            repo="owner/repo",
            asset_patterns=["*datapack*.zip"],
        ),
    )
    assert CatalogService.asset_matches(patterned_mod, "LongYinDataPack.zip")
