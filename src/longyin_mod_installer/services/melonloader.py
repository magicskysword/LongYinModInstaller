from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from ..constants import GAME_EXECUTABLE, MELONLOADER_ARCHIVE_NAME
from ..utils.runtime import ensure_directory, get_application_root, get_user_config_dir


class MelonLoaderInstaller:
    def __init__(self) -> None:
        self.archive_path = get_application_root() / MELONLOADER_ARCHIVE_NAME
        self.cache_dir = ensure_directory(get_user_config_dir() / "cache")

    def is_installed(self, game_dir: Path) -> bool:
        return (game_dir / "MelonLoader").exists() and (game_dir / "version.dll").exists()

    def describe_status(self, game_dir: Path | None) -> str:
        if not game_dir:
            return "未指定游戏目录"
        if not game_dir.exists():
            return "游戏目录不存在"
        if not (game_dir / GAME_EXECUTABLE).exists():
            return "目录内未找到游戏主程序"
        if self.is_installed(game_dir):
            return "已检测到 MelonLoader"
        partial = [
            path.name
            for path in (game_dir / "MelonLoader", game_dir / "version.dll")
            if path.exists()
        ]
        if partial:
            return f"检测到部分文件：{', '.join(partial)}"
        return "尚未安装 MelonLoader"

    def install(self, game_dir: Path, log: callable | None = None) -> None:
        if not self.archive_path.exists():
            raise FileNotFoundError(f"缺少安装包：{self.archive_path}")
        if not (game_dir / GAME_EXECUTABLE).exists():
            raise FileNotFoundError(f"目标目录中未找到 {GAME_EXECUTABLE}")

        with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_dir:
            temp_path = Path(temp_dir)
            if log:
                log("正在解压 MelonLoader 安装包。")
            with zipfile.ZipFile(self.archive_path) as archive:
                archive.extractall(temp_path)

            if log:
                log("正在复制 MelonLoader 文件到游戏目录。")
            self._copy_contents(temp_path, game_dir)

        if log:
            log("MelonLoader 安装完成。")

    def _copy_contents(self, source_root: Path, destination_root: Path) -> None:
        for item in source_root.iterdir():
            target = destination_root / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
