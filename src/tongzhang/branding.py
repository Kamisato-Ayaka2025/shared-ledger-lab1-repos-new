"""Shared identity for tray, application windows and the Windows executable."""

from pathlib import Path
import sys
from PySide6.QtGui import QIcon


def application_icon():
    return QIcon(str(Path(__file__).parent / "assets" / "tongzhang.ico"))


def configure_identity(app):
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Tongzhang.Desktop")
    app.setApplicationName("同账")
    app.setWindowIcon(application_icon())
