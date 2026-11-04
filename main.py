"""
BallotVision entry point.

Run this file to open the native Windows desktop prototype.
"""

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.core.constants import APP_NAME, APP_USER_MODEL_ID
from app.core.store import Store
from app.core.utils import asset_path, resource_root
from app.main_window import MainWindow
from app.widgets.logo import logo_icon


def set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


def load_stylesheet() -> str:
    qss_path = resource_root() / "app" / "styles" / "theme.qss"
    if not qss_path.exists():
        raise FileNotFoundError(f"BallotVision stylesheet was not found at {qss_path}")
    text = qss_path.read_text(encoding="utf-8")
    chevron = asset_path("icons", "chevron_down.png")
    if not chevron.exists():
        chevron = asset_path("icons", "chevron_down.svg")
    if chevron.exists():
        uri = chevron.resolve().as_uri()
        text = text.replace("url(__CHEVRON_DOWN__)", f'url("{uri}")')
        text = text.replace("__CHEVRON_DOWN__", uri)
    return text


def main() -> None:
    set_windows_app_id()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    icon = logo_icon(256)
    app.setWindowIcon(icon)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(load_stylesheet())

    store = Store()
    window = MainWindow(store)
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
