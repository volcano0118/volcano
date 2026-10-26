"""Kuromi desktop pet - entry point.

Run with ``pythonw main.py`` (or the packaged ``Kuromi.exe``).
"""

from __future__ import annotations

import ctypes
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from ui.config import resource_path
from ui.pet import KuromiPet


def main() -> int:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Kuromi.DesktopPet"
        )
    except Exception:  # noqa: BLE001 - cosmetic only, Windows specific
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("KuromiPet")

    icon = resource_path("kuromi.ico")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    pet = KuromiPet()
    pet.show()
    pet.raise_()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
