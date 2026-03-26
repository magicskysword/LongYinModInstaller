# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

root = Path.cwd()
datas = collect_data_files("customtkinter")
dnd_datas, dnd_binaries, dnd_hiddenimports = collect_all("tkinterdnd2")
datas += [
    (str(root / "MelonLoader.x64.zip"), "."),
    (str(root / "Dependencies.zip"), "."),
]
datas += dnd_datas

a = Analysis(
    ["launcher.py"],
    pathex=[str(root / "src")],
    binaries=dnd_binaries,
    datas=datas,
    hiddenimports=[
        "darkdetect",
        "tkinter.filedialog",
        "tkinter.messagebox",
    ] + dnd_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="LongYinModInstaller",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
