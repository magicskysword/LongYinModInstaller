from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False

from ..constants import APP_NAME, APP_SUBTITLE, MODS_DIRECTORY_NAME, TARGET_APP_ID
from ..models import Catalog, InstalledMod, ModEntry
from ..services.catalog import CatalogService
from ..services.melonloader import MelonLoaderInstaller
from ..services.mods import ModManager
from ..services.settings import SettingsService
from ..services.steam import SteamService
from ..utils.runtime import get_local_catalog_path, human_size, open_text_file

COLORS = {
    "bg": "#F5F0EA",
    "card": "#FFFFFF",
    "card_border": "#E2DDD6",
    "accent": "#1A6B5C",
    "accent_hover": "#145A4D",
    "accent_light": "#E0F0EC",
    "danger": "#C0553A",
    "danger_hover": "#A04530",
    "text": "#1E2D33",
    "text_secondary": "#5F6E76",
    "text_tertiary": "#8E9BA2",
    "input_bg": "#F0EBE4",
    "log_bg": "#1C2529",
    "log_text": "#D8E2E6",
    "badge_managed": "#D6EDE8",
    "badge_managed_text": "#1A6B5C",
    "badge_unknown": "#F5E0D4",
    "badge_unknown_text": "#C0553A",
    "btn_secondary": "#EBE6DF",
    "btn_secondary_hover": "#DED7CE",
    "separator": "#E2DDD6",
}

if HAS_DND:
    class DnDCTk(ctk.CTk, TkinterDnD.DnDWrapper):
        pass
else:
    class DnDCTk(ctk.CTk):
        pass


class MainWindow(DnDCTk):
    def __init__(self) -> None:
        super().__init__()
        if HAS_DND:
            self.TkdndVersion = TkinterDnD._require(self)
        self.title(APP_NAME)
        self.geometry("780x900")
        self.minsize(640, 700)
        self.configure(fg_color=COLORS["bg"])

        self.settings_service = SettingsService()
        self.steam_service = SteamService()
        self.catalog_service = CatalogService()
        self.melonloader_installer = MelonLoaderInstaller()
        self.mod_manager = ModManager(self.catalog_service)

        self.settings = self.settings_service.load()
        self.catalog: Catalog | None = None
        self.installed_mods: list[InstalledMod] = []
        self.action_buttons: list[ctk.CTkButton] = []

        self.title_font = ctk.CTkFont(family="Microsoft YaHei UI", size=22, weight="bold")
        self.heading_font = ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold")
        self.body_font = ctk.CTkFont(family="Microsoft YaHei UI", size=13)
        self.small_font = ctk.CTkFont(family="Microsoft YaHei UI", size=11)
        self.mono_font = ctk.CTkFont(family="Consolas", size=11)

        self.game_dir_var = ctk.StringVar(value=self.settings.game_directory or "尚未检测")
        self.drop_hint_var = ctk.StringVar(
            value="拖拽 DLL / ZIP 到这里安装，或点击选择文件" if HAS_DND else "点击这里选择 DLL / ZIP 进行安装"
        )

        self._build_ui()
        self.after(100, self._bootstrap_async)

    # ── UI Construction ──────────────────────────────────────

    def _build_ui(self) -> None:
        outer = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["text_tertiary"],
            scrollbar_button_hover_color=COLORS["accent"],
        )
        outer.pack(fill="both", expand=True, padx=0, pady=0)
        outer.grid_columnconfigure(0, weight=1)
        self._content = outer

        self._build_header(outer)
        self._build_game_section(outer)
        self._build_separator(outer)
        self._build_mods_section(outer)
        self._build_separator(outer)
        self._build_log_section(outer)

    def _build_header(self, parent: ctk.CTkFrame) -> None:
        hdr = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=16)
        hdr.pack(fill="x", padx=20, pady=(20, 0))

        top = ctk.CTkFrame(hdr, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(20, 0))
        ctk.CTkLabel(
            top, text=APP_NAME,
            font=self.title_font, text_color=COLORS["text"],
        ).pack(side="left")
        ctk.CTkLabel(
            top, text=f"AppID {TARGET_APP_ID}",
            font=self.small_font, text_color=COLORS["accent"],
            fg_color=COLORS["accent_light"], corner_radius=8, padx=10, pady=4,
        ).pack(side="right")

        ctk.CTkLabel(
            hdr, text=APP_SUBTITLE,
            font=self.small_font, text_color=COLORS["text_secondary"],
        ).pack(anchor="w", padx=24, pady=(6, 18))

    def _build_game_section(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=16)
        card.pack(fill="x", padx=20, pady=(12, 0))

        ctk.CTkLabel(
            card, text="游戏目录", font=self.heading_font, text_color=COLORS["text"],
        ).pack(anchor="w", padx=24, pady=(18, 8))

        entry_row = ctk.CTkFrame(card, fg_color="transparent")
        entry_row.pack(fill="x", padx=24)
        self.game_dir_entry = ctk.CTkEntry(
            entry_row, textvariable=self.game_dir_var,
            font=self.body_font, corner_radius=10,
            fg_color=COLORS["input_bg"], text_color=COLORS["text"],
            border_width=0, state="readonly", height=36,
        )
        self.game_dir_entry.pack(fill="x")

        status_row = ctk.CTkFrame(card, fg_color="transparent")
        status_row.pack(fill="x", padx=24, pady=(8, 0))
        self.game_status_label = ctk.CTkLabel(
            status_row, text="正在等待检测",
            font=self.small_font, text_color=COLORS["text_secondary"], anchor="w",
        )
        self.game_status_label.pack(anchor="w")
        self.melon_status_label = ctk.CTkLabel(
            status_row, text="MelonLoader 状态待检测",
            font=self.small_font, text_color=COLORS["text_tertiary"], anchor="w",
        )
        self.melon_status_label.pack(anchor="w", pady=(2, 0))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(14, 18))
        for text, cmd, fg, hover, tc in [
            ("自动识别", self._detect_game_directory_async, COLORS["accent"], COLORS["accent_hover"], "#FFFFFF"),
            ("手动选择", self._choose_game_directory, COLORS["btn_secondary"], COLORS["btn_secondary_hover"], COLORS["text"]),
            ("打开目录", self._open_game_directory, COLORS["btn_secondary"], COLORS["btn_secondary_hover"], COLORS["text"]),
            ("安装 MelonLoader", self._install_melonloader_async, COLORS["danger"], COLORS["danger_hover"], "#FFFFFF"),
        ]:
            b = ctk.CTkButton(
                btn_row, text=text, command=cmd,
                fg_color=fg, hover_color=hover, text_color=tc,
                corner_radius=10, height=34, font=self.body_font,
            )
            b.pack(side="left", padx=(0, 8))
            self.action_buttons.append(b)

    def _build_mods_section(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=16)
        card.pack(fill="x", padx=20, pady=(0,))

        self._build_drop_zone(card)

        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.pack(fill="x", padx=24, pady=(18, 0))
        ctk.CTkLabel(
            header_row, text="Mod 管理", font=self.heading_font, text_color=COLORS["text"],
        ).pack(side="left")

        self.catalog_info_label = ctk.CTkLabel(
            header_row, text="",
            font=self.small_font, text_color=COLORS["text_tertiary"],
        )
        self.catalog_info_label.pack(side="right")

        self.mods_container = ctk.CTkFrame(card, fg_color="transparent")
        self.mods_container.pack(fill="x", padx=24, pady=(10, 0))

        self.mods_empty_label = ctk.CTkLabel(
            self.mods_container, text="正在加载…",
            font=self.body_font, text_color=COLORS["text_tertiary"],
        )
        self.mods_empty_label.pack(anchor="w", pady=10)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(14, 18))
        for text, cmd, fg, hover, tc in [
            ("刷新", self._refresh_all, COLORS["btn_secondary"], COLORS["btn_secondary_hover"], COLORS["text"]),
            ("打开 Mods 目录", self._open_mods_directory, COLORS["btn_secondary"], COLORS["btn_secondary_hover"], COLORS["text"]),
            ("下载源配置", self._open_sources_file, COLORS["btn_secondary"], COLORS["btn_secondary_hover"], COLORS["text"]),
            ("打开本地仓库", self._open_local_repository, COLORS["btn_secondary"], COLORS["btn_secondary_hover"], COLORS["text"]),
        ]:
            b = ctk.CTkButton(
                btn_row, text=text, command=cmd,
                fg_color=fg, hover_color=hover, text_color=tc,
                corner_radius=10, height=34, font=self.body_font,
            )
            b.pack(side="left", padx=(0, 8))
            self.action_buttons.append(b)

    def _build_drop_zone(self, parent: ctk.CTkFrame) -> None:
        self.drop_zone = ctk.CTkFrame(
            parent,
            fg_color=COLORS["accent_light"],
            corner_radius=14,
            border_width=2,
            border_color=COLORS["accent"],
        )
        self.drop_zone.pack(fill="x", padx=24, pady=(20, 0))

        self.drop_zone_title = ctk.CTkLabel(
            self.drop_zone,
            text="快速安装",
            font=self.heading_font,
            text_color=COLORS["accent"],
        )
        self.drop_zone_title.pack(anchor="center", pady=(14, 4))

        self.drop_zone_hint = ctk.CTkLabel(
            self.drop_zone,
            textvariable=self.drop_hint_var,
            font=self.body_font,
            text_color=COLORS["text"],
        )
        self.drop_zone_hint.pack(anchor="center", pady=(0, 4))

        self.drop_zone_subhint = ctk.CTkLabel(
            self.drop_zone,
            text="ZIP 会自动拆分 DLL 与 ModsOfLong/mod* 数据目录",
            font=self.small_font,
            text_color=COLORS["text_secondary"],
        )
        self.drop_zone_subhint.pack(anchor="center", pady=(0, 14))

        for widget in (self.drop_zone, self.drop_zone_title, self.drop_zone_hint, self.drop_zone_subhint):
            widget.bind("<Button-1>", lambda _event: self._choose_local_packages())

        if HAS_DND:
            self._register_drop_target(self.drop_zone)
            self._register_drop_target(self.drop_zone_title)
            self._register_drop_target(self.drop_zone_hint)
            self._register_drop_target(self.drop_zone_subhint)

    def _register_drop_target(self, widget) -> None:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<DropEnter>>", self._on_drop_enter)
        widget.dnd_bind("<<DropLeave>>", self._on_drop_leave)
        widget.dnd_bind("<<Drop>>", self._on_drop)

    def _build_log_section(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=16)
        card.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkLabel(
            card, text="运行日志", font=self.heading_font, text_color=COLORS["text"],
        ).pack(anchor="w", padx=24, pady=(18, 8))

        self.log_box = ctk.CTkTextbox(
            card, fg_color=COLORS["log_bg"], text_color=COLORS["log_text"],
            corner_radius=12, font=self.mono_font, wrap="word", height=160,
        )
        self.log_box.pack(fill="x", padx=24, pady=(0, 18))
        self.log_box.insert("end", "准备就绪。\n")
        self.log_box.configure(state="disabled")

    def _build_separator(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkFrame(parent, fg_color=COLORS["separator"], height=1).pack(
            fill="x", padx=40, pady=12,
        )

    # ── Mod List Rendering ───────────────────────────────────

    def _render_mod_list(self) -> None:
        for child in self.mods_container.winfo_children():
            child.destroy()

        if not self.catalog or not self.catalog.mods:
            ctk.CTkLabel(
                self.mods_container, text="仓库中没有可用的 Mod。",
                font=self.body_font, text_color=COLORS["text_tertiary"],
            ).pack(anchor="w", pady=10)
            return

        extra_installed = []

        for i, mod in enumerate(self.catalog.mods):
            installed = self._find_installed_for_catalog_mod(mod)
            self._render_catalog_mod_row(mod, installed)
            if i < len(self.catalog.mods) - 1:
                ctk.CTkFrame(
                    self.mods_container, fg_color=COLORS["separator"], height=1,
                ).pack(fill="x", padx=8)

        catalog_file_names = {(m.file_name or "").lower() for m in self.catalog.mods}
        catalog_mod_ids = {m.id for m in self.catalog.mods}
        for mod in self.installed_mods:
            if mod.mod_id and mod.mod_id in catalog_mod_ids:
                continue
            if mod.mod_id is None and mod.artifact_name.lower() in catalog_file_names:
                continue
            extra_installed.append(mod)

        if extra_installed:
            ctk.CTkFrame(
                self.mods_container, fg_color=COLORS["separator"], height=2,
            ).pack(fill="x", padx=8, pady=(8, 4))
            ctk.CTkLabel(
                self.mods_container, text="其他已安装（未收录）",
                font=self.small_font, text_color=COLORS["text_tertiary"],
            ).pack(anchor="w", padx=4, pady=(2, 4))
            for i, mod in enumerate(extra_installed):
                self._render_extra_installed_row(mod, is_last=(i == len(extra_installed) - 1))
                if i < len(extra_installed) - 1:
                    ctk.CTkFrame(
                        self.mods_container, fg_color=COLORS["separator"], height=1,
                    ).pack(fill="x", padx=8)

    def _render_catalog_mod_row(self, mod: ModEntry, installed: InstalledMod | None) -> None:
        row = ctk.CTkFrame(self.mods_container, fg_color="transparent")
        row.pack(fill="x", pady=4)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        name_row = ctk.CTkFrame(info, fg_color="transparent")
        name_row.pack(fill="x")
        ctk.CTkLabel(
            name_row, text=mod.name,
            font=self.body_font, text_color=COLORS["text"],
        ).pack(side="left")
        ctk.CTkLabel(
            name_row, text=f"v{mod.version}",
            font=self.small_font, text_color=COLORS["text_tertiary"],
        ).pack(side="left", padx=(8, 0))

        if mod.description:
            ctk.CTkLabel(
                info, text=mod.description,
                font=self.small_font, text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(anchor="w", pady=(2, 0))

        if installed:
            meta = f"{installed.artifact_name}  ·  {human_size(installed.size_bytes)}  ·  {installed.modified_at.strftime('%Y-%m-%d %H:%M')}"
            ctk.CTkLabel(
                info, text=meta,
                font=self.small_font, text_color=COLORS["text_tertiary"], anchor="w",
            ).pack(anchor="w", pady=(2, 0))

        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.pack(side="right", padx=(12, 0))

        if installed:
            ctk.CTkLabel(
                btn_frame, text="● 已安装",
                font=self.small_font, text_color=COLORS["accent"],
            ).pack(side="left", padx=(0, 8))
            btn = ctk.CTkButton(
                btn_frame, text="卸载", width=60, height=30,
                font=self.small_font,
                fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                text_color="#FFFFFF", corner_radius=8,
                command=lambda installed_mod=installed, m=mod: self._uninstall_mod_async(
                    installed_mod.identifier,
                    m.name,
                ),
            )
            btn.pack(side="left")
            self.action_buttons.append(btn)
        else:
            btn = ctk.CTkButton(
                btn_frame, text="安装", width=60, height=30,
                font=self.small_font,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                text_color="#FFFFFF", corner_radius=8,
                command=lambda m=mod: self._install_single_mod_async(m),
            )
            btn.pack(side="left")
            self.action_buttons.append(btn)

    def _render_extra_installed_row(self, mod: InstalledMod, is_last: bool) -> None:
        row = ctk.CTkFrame(self.mods_container, fg_color="transparent")
        row.pack(fill="x", pady=4)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        name_row = ctk.CTkFrame(info, fg_color="transparent")
        name_row.pack(fill="x")
        ctk.CTkLabel(
            name_row, text=mod.display_name,
            font=self.body_font, text_color=COLORS["text"],
        ).pack(side="left")
        ctk.CTkLabel(
            name_row, text="未收录",
            font=self.small_font, text_color=COLORS["badge_unknown_text"],
            fg_color=COLORS["badge_unknown"], corner_radius=6, padx=8, pady=2,
        ).pack(side="left", padx=(8, 0))

        meta = f"{mod.artifact_name}  ·  {human_size(mod.size_bytes)}  ·  {mod.modified_at.strftime('%Y-%m-%d %H:%M')}"
        ctk.CTkLabel(
            info, text=meta,
            font=self.small_font, text_color=COLORS["text_tertiary"], anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        btn = ctk.CTkButton(
            row, text="卸载", width=60, height=30,
            font=self.small_font,
            fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
            text_color="#FFFFFF", corner_radius=8,
            command=lambda m=mod: self._uninstall_mod_async(m.identifier, m.display_name),
        )
        btn.pack(side="right", padx=(12, 0))
        self.action_buttons.append(btn)

    def _find_installed_for_catalog_mod(self, mod: ModEntry) -> InstalledMod | None:
        for installed in self.installed_mods:
            if installed.mod_id == mod.id:
                return installed
        if not mod.file_name:
            return None
        lower = mod.file_name.lower()
        for installed in self.installed_mods:
            if installed.artifact_name.lower() == lower:
                return installed
        return None

    def _set_drop_zone_active(self, active: bool) -> None:
        if active:
            self.drop_zone.configure(fg_color=COLORS["card"], border_color=COLORS["danger"])
            self.drop_zone_title.configure(text_color=COLORS["danger"])
        else:
            self.drop_zone.configure(fg_color=COLORS["accent_light"], border_color=COLORS["accent"])
            self.drop_zone_title.configure(text_color=COLORS["accent"])

    def _find_installed(self, file_name: str | None) -> InstalledMod | None:
        if not file_name:
            return None
        lower = file_name.lower()
        for mod in self.installed_mods:
            if mod.artifact_name.lower() == lower:
                return mod
        return None

    # ── Bootstrap & Async Tasks ──────────────────────────────

    def _bootstrap_async(self) -> None:
        self._run_task("初始化环境", self._bootstrap_worker, self._after_bootstrap)

    def _bootstrap_worker(self) -> tuple[Path | None, Catalog]:
        settings = self.settings_service.load()
        game_dir = Path(settings.game_directory) if settings.game_directory else None
        if not game_dir or not self.steam_service.is_valid_game_directory(game_dir):
            try:
                game_dir = self.steam_service.find_game_directory()
                settings.game_directory = str(game_dir)
                self.settings_service.save(settings)
            except FileNotFoundError:
                game_dir = None
        catalog = self.catalog_service.load_catalog(settings.catalog_sources, log=self._thread_log)
        self.settings = settings
        return game_dir, catalog

    def _after_bootstrap(self, result: tuple[Path | None, Catalog]) -> None:
        game_dir, catalog = result
        if game_dir:
            self.settings.game_directory = str(game_dir)
            self.game_dir_var.set(str(game_dir))
        self.catalog = catalog
        self._refresh_status_labels()
        self._scan_installed_mods()
        self._apply_catalog(catalog)

    def _refresh_status_labels(self) -> None:
        game_dir = self._current_game_directory()
        if game_dir and self.steam_service.is_valid_game_directory(game_dir):
            self.game_status_label.configure(text="✓ 已识别有效游戏目录")
        elif game_dir:
            self.game_status_label.configure(text="⚠ 当前路径不是有效的游戏根目录")
        else:
            self.game_status_label.configure(text="尚未检测到游戏目录")
        self.melon_status_label.configure(text=self.melonloader_installer.describe_status(game_dir))

    def _apply_catalog(self, catalog: Catalog) -> None:
        updated = catalog.metadata.updated_at or "未标注"
        self.catalog_info_label.configure(
            text=f"{catalog.source_name}  ·  v{catalog.metadata.version}  ·  {updated}"
        )
        self._render_mod_list()

    def _scan_installed_mods(self) -> None:
        game_dir = self._current_game_directory()
        if game_dir and game_dir.exists():
            self.installed_mods = self.mod_manager.scan_installed_mods(game_dir, self.catalog)
        else:
            self.installed_mods = []

    # ── Actions ──────────────────────────────────────────────

    def _refresh_all(self) -> None:
        self._run_task("刷新", self._refresh_worker, self._after_refresh)

    def _refresh_worker(self) -> Catalog:
        self.settings = self.settings_service.load()
        return self.catalog_service.load_catalog(self.settings.catalog_sources, log=self._thread_log)

    def _after_refresh(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self._scan_installed_mods()
        self._apply_catalog(catalog)
        self._refresh_status_labels()

    def _detect_game_directory_async(self) -> None:
        self._run_task("自动识别游戏目录", self.steam_service.find_game_directory, self._after_detect_game_directory)

    def _after_detect_game_directory(self, game_dir: Path) -> None:
        self.settings.game_directory = str(game_dir)
        self.settings_service.save(self.settings)
        self.game_dir_var.set(str(game_dir))
        self._append_log(f"已更新游戏目录：{game_dir}")
        self._refresh_status_labels()
        self._scan_installed_mods()
        self._render_mod_list()

    def _choose_game_directory(self) -> None:
        selected = filedialog.askdirectory(
            title="选择龙胤立志传游戏目录",
            initialdir=self.settings.game_directory or None,
        )
        if not selected:
            return
        path = Path(selected)
        if not self.steam_service.is_valid_game_directory(path):
            messagebox.showerror("目录无效", "所选目录中没有找到游戏主程序。")
            return
        self.settings.game_directory = str(path)
        self.settings_service.save(self.settings)
        self.game_dir_var.set(str(path))
        self._append_log(f"已手动指定游戏目录：{path}")
        self._refresh_status_labels()
        self._scan_installed_mods()
        self._render_mod_list()

    def _install_melonloader_async(self) -> None:
        try:
            game_dir = self._require_game_directory()
        except Exception as exc:
            self._show_error("安装 MelonLoader", exc)
            return
        self._run_task(
            "安装 MelonLoader",
            lambda: self.melonloader_installer.install(game_dir, log=self._thread_log),
            lambda _: self._after_install_melonloader(),
        )

    def _after_install_melonloader(self) -> None:
        self._refresh_status_labels()
        messagebox.showinfo("完成", "MelonLoader 已安装或修复完成。")

    def _install_single_mod_async(self, mod: ModEntry) -> None:
        try:
            game_dir = self._require_game_directory()
            catalog = self._require_catalog()
        except Exception as exc:
            self._show_error(f"安装 {mod.name}", exc)
            return
        self._run_task(
            f"安装 {mod.name}",
            lambda: self.mod_manager.install_mod(
                game_dir,
                catalog,
                self.settings.catalog_sources,
                self.settings.release_sources,
                mod,
                log=self._thread_log,
            ),
            lambda _: self._after_mod_change(),
        )

    def _choose_local_packages(self) -> None:
        selected = filedialog.askopenfilenames(
            title="选择要安装的 Mod 包",
            filetypes=[
                ("Mod 文件", "*.dll *.zip"),
                ("DLL 文件", "*.dll"),
                ("ZIP 压缩包", "*.zip"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return
        self._install_local_packages_async([Path(item) for item in selected])

    def _install_local_packages_async(self, package_paths: list[Path]) -> None:
        try:
            game_dir = self._require_game_directory()
        except Exception as exc:
            self._show_error("安装本地包", exc)
            return

        normalized_paths = []
        for path in package_paths:
            suffix = path.suffix.lower()
            if suffix not in {".dll", ".zip"}:
                continue
            normalized_paths.append(path)

        if not normalized_paths:
            self._show_error("安装本地包", ValueError("没有可安装的 .dll 或 .zip 文件。"))
            return

        self._run_task(
            f"安装本地包 ({len(normalized_paths)} 个)",
            lambda: [
                self.mod_manager.install_local_package(game_dir, path, log=self._thread_log)
                for path in normalized_paths
            ],
            lambda paths: self._after_local_package_install(paths),
        )

    def _after_local_package_install(self, installed_paths: list[Path]) -> None:
        self._append_log(f"本地导入完成，共安装 {len(installed_paths)} 个包。")
        self._after_mod_change()

    def _uninstall_mod_async(self, dll_name: str, display_name: str) -> None:
        try:
            game_dir = self._require_game_directory()
        except Exception as exc:
            self._show_error(f"卸载 {display_name}", exc)
            return
        self._run_task(
            f"卸载 {display_name}",
            lambda: self.mod_manager.uninstall_mod(game_dir, dll_name, log=self._thread_log),
            lambda _: self._after_mod_change(),
        )

    def _after_mod_change(self) -> None:
        self._scan_installed_mods()
        self._render_mod_list()

    # ── Open Actions ─────────────────────────────────────────

    def _open_game_directory(self) -> None:
        try:
            game_dir = self._require_game_directory()
        except Exception as exc:
            self._show_error("打开游戏目录", exc)
            return
        os.startfile(game_dir)

    def _open_mods_directory(self) -> None:
        try:
            game_dir = self._require_game_directory()
        except Exception as exc:
            self._show_error("打开 Mods 目录", exc)
            return
        mods_dir = game_dir / MODS_DIRECTORY_NAME
        mods_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(mods_dir)

    def _open_local_repository(self) -> None:
        os.startfile(get_local_catalog_path().parent)

    def _open_sources_file(self) -> None:
        open_text_file(self.settings_service.sources_path)

    def _on_drop_enter(self, _event):
        self._set_drop_zone_active(True)
        return "copy"

    def _on_drop_leave(self, _event):
        self._set_drop_zone_active(False)
        return "copy"

    def _on_drop(self, event):
        self._set_drop_zone_active(False)
        paths = self._parse_drop_paths(str(getattr(event, "data", "")))
        if paths:
            self._install_local_packages_async(paths)
        return "copy"

    def _parse_drop_paths(self, raw_data: str) -> list[Path]:
        try:
            entries = self.tk.splitlist(raw_data)
        except Exception:
            entries = [raw_data]

        paths: list[Path] = []
        for entry in entries:
            cleaned = entry.strip()
            if cleaned.startswith("{") and cleaned.endswith("}"):
                cleaned = cleaned[1:-1]
            if not cleaned:
                continue
            path = Path(cleaned)
            if path.exists():
                paths.append(path)
        return paths

    # ── Task Runner ──────────────────────────────────────────

    def _run_task(self, label: str, worker, on_success) -> None:
        self._set_buttons_state("disabled")
        self._append_log(f"{label}…")

        def task() -> None:
            try:
                result = worker()
            except Exception as exc:
                self.after(0, lambda: self._handle_task_error(label, exc))
                return
            self.after(0, lambda: self._handle_task_success(label, result, on_success))

        threading.Thread(target=task, daemon=True).start()

    def _handle_task_success(self, label: str, result: object, on_success) -> None:
        self._set_buttons_state("normal")
        self._append_log(f"{label}完成。")
        on_success(result)

    def _handle_task_error(self, label: str, exc: Exception) -> None:
        self._set_buttons_state("normal")
        self._append_log(f"{label}失败：{exc}")
        messagebox.showerror("操作失败", f"{label}失败：\n{exc}")

    def _show_error(self, title: str, exc: Exception) -> None:
        self._append_log(f"{title}失败：{exc}")
        messagebox.showerror("操作失败", f"{title}失败：\n{exc}")

    def _set_buttons_state(self, state: str) -> None:
        for button in self.action_buttons:
            try:
                button.configure(state=state)
            except Exception:
                pass

    def _current_game_directory(self) -> Path | None:
        if not self.settings.game_directory:
            return None
        return Path(self.settings.game_directory)

    def _require_game_directory(self) -> Path:
        game_dir = self._current_game_directory()
        if not game_dir or not self.steam_service.is_valid_game_directory(game_dir):
            raise ValueError("请先指定有效的游戏目录。")
        return game_dir

    def _require_catalog(self) -> Catalog:
        if not self.catalog:
            raise ValueError("请先加载 Mod 仓库。")
        return self.catalog

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _thread_log(self, message: str) -> None:
        self.after(0, lambda: self._append_log(message))
