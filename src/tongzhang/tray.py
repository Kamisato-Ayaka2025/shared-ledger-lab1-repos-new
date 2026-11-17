"""System tray keeps the desktop reachable after closing its window."""

from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap, QFont
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TrayController(QObject):
    def __init__(self, window, quit_callback=None):
        super().__init__(window)
        self.window = window
        self.quitting = False
        self.notified = False
        self.quit_callback = quit_callback or QApplication.instance().quit
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("#187662"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Microsoft YaHei", 32, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), 0x84, "同")
        painter.end()
        self.tray = QSystemTrayIcon(QIcon(pixmap), self)
        self.tray.setToolTip("同账 · 双击显示主窗口")
        self.menu = QMenu(window)
        self.show_action = QAction("显示主窗口", self)
        self.show_action.triggered.connect(self.restore)
        self.menu.addAction(self.show_action)
        self.menu.addSeparator()
        self.quit_action = QAction("彻底退出", self)
        self.quit_action.triggered.connect(self.quit)
        self.menu.addAction(self.quit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.activated)
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        if self.available:
            QApplication.instance().setQuitOnLastWindowClosed(False)
            self.window.installEventFilter(self)
            self.tray.show()

    def eventFilter(self, watched, event):
        if watched is self.window and event.type() == QEvent.Type.Close and not self.quitting:
            event.ignore()
            self.window.hide()
            if not self.notified:
                self.tray.showMessage(
                    "同账仍在运行", "双击托盘图标恢复窗口；右键选择“彻底退出”关闭软件。"
                )
                self.notified = True
            return True
        return super().eventFilter(watched, event)

    def restore(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self.restore()

    def quit(self):
        self.quitting = True
        self.tray.hide()
        self.quit_callback()
