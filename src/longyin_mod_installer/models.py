from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class CatalogSource:
    name: str
    catalog_url: str
    enabled: bool = True


@dataclass(slots=True)
class ReleaseSource:
    name: str
    api_base: str
    download_base: str
    enabled: bool = True


@dataclass(slots=True)
class DownloadDefinition:
    type: str = "file"
    url: str | None = None
    mirrors: list[str] = field(default_factory=list)
    repo_path: str | None = None
    repo: str | None = None
    tag: str = "latest"
    asset_name: str | None = None
    asset_patterns: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ModEntry:
    id: str
    name: str
    version: str
    description: str
    file_name: str | None
    install_to: str
    download: DownloadDefinition


@dataclass(slots=True)
class CatalogMetadata:
    name: str
    game_name: str
    game_app_id: int
    version: str
    updated_at: str | None = None


@dataclass(slots=True)
class Catalog:
    metadata: CatalogMetadata
    mods: list[ModEntry]
    source_name: str
    source_url: str | None = None


@dataclass(slots=True)
class AppSettings:
    game_directory: str = ""
    catalog_sources: list[CatalogSource] = field(default_factory=list)
    release_sources: list[ReleaseSource] = field(default_factory=list)


@dataclass(slots=True)
class InstallRecord:
    path: str
    record_type: str
    backup_path: str | None = None


@dataclass(slots=True)
class ManagedInstallManifest:
    mod_id: str
    mod_name: str
    version: str
    primary_name: str
    records: list[InstallRecord]
    installed_at: str


@dataclass(slots=True)
class InstalledMod:
    identifier: str
    display_name: str
    artifact_name: str
    path: str
    size_bytes: int
    modified_at: datetime
    managed_by_catalog: bool
    mod_id: str | None = None
