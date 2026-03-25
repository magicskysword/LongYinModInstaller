from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk

try:
    from .ui.main_window import MainWindow
except ImportError:
    package_root = Path(__file__).resolve().parents[1]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from longyin_mod_installer.ui.main_window import MainWindow


def main() -> None:
    ctk.set_appearance_mode("light")
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
