from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

from ..constants import LOCAL_CATALOG_RELATIVE_PATH, USER_CONFIG_DIR_NAME


def get_application_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[3]


def get_local_catalog_path() -> Path:
    root = get_application_root()
    return root.joinpath(*LOCAL_CATALOG_RELATIVE_PATH)


def get_user_config_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / USER_CONFIG_DIR_NAME
    return Path.home() / "AppData" / "Local" / USER_CONFIG_DIR_NAME


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_join(root: Path, relative_path: str) -> Path:
    parts = [part for part in PurePosixPath(relative_path).parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError(f"不允许越级路径: {relative_path}")

    candidate = root
    for part in parts:
        candidate = candidate / part

    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_root != resolved_candidate and resolved_root not in resolved_candidate.parents:
        raise ValueError(f"目标路径越界: {relative_path}")
    return candidate


def human_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def open_text_file(path: Path) -> None:
    try:
        subprocess.Popen(["notepad.exe", str(path)])
        return
    except OSError:
        pass

    os.startfile(path)
