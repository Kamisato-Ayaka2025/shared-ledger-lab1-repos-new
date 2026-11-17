"""Frozen tray lifecycle smoke test using the normal launcher lease."""

import json
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QSystemTrayIcon
from tongzhang.widgets import Client, LoginDialog, configure_fonts, STYLE
from tongzhang.desktop import Window
from tongzhang.tray import TrayController


def main(output):
    app = QApplication([])
    configure_fonts(app)
    app.setStyleSheet(STYLE)
    errors = []
    client = Client()
    client.error.connect(errors.append)
    login = LoginDialog(client)
    QTimer.singleShot(
        100,
        lambda: QTest.mouseClick(
            login.buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton
        ),
    )
    assert login.exec() == QDialog.DialogCode.Accepted, errors
    window = Window(client)
    tray = TrayController(window)
    window.show()
    results = []

    def verify():
        if client.pending:
            QTimer.singleShot(100, verify)
            return
        try:
            assert not errors, errors
            assert QSystemTrayIcon.isSystemTrayAvailable()
            window.close()
            assert not window.isVisible() and tray.tray.isVisible()
            results.append("close hides window and keeps tray")
            tray.show_action.trigger()
            assert window.isVisible()
            results.append("tray restores window")
            tray.quit_action.trigger()
            assert not tray.tray.isVisible()
            results.append("tray exit requested application quit")
            Path(output).write_text(json.dumps(results), encoding="utf-8")
        finally:
            app.quit()

    QTimer.singleShot(100, verify)
    app.exec()
