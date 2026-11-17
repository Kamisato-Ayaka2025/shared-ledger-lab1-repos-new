import subprocess
import sys
from PySide6.QtWidgets import QWidget, QSystemTrayIcon
from tongzhang.runtime import RuntimeLease, identity
from tongzhang.tray import TrayController
import psutil


def test_close_restore_and_quit(qtbot, monkeypatch, qapp):
    previous = qapp.quitOnLastWindowClosed()
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: True)
    window = QWidget()
    qtbot.addWidget(window)
    calls = []
    tray = TrayController(window, lambda: calls.append("quit"))
    monkeypatch.setattr(tray.tray, "showMessage", lambda *args: None)
    window.show()
    window.close()
    assert not window.isVisible()
    assert tray.tray.isVisible()
    assert not calls
    tray.show_action.trigger()
    assert window.isVisible()
    tray.quit_action.trigger()
    assert calls == ["quit"]
    assert not tray.tray.isVisible()
    window.close()
    qapp.setQuitOnLastWindowClosed(previous)


def sleeper():
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def test_only_last_client_stops_server(tmp_path):
    server = sleeper()
    other = sleeper()
    first = RuntimeLease(tmp_path, 12345)
    second = RuntimeLease(tmp_path, 12345)
    second.me = identity(psutil.Process(other.pid))
    try:
        first.acquire(lambda: False, lambda: server, sys.executable)
        second.acquire(lambda: True, lambda: None, sys.executable)
        first.release()
        assert server.poll() is None
        second.release()
        server.wait(timeout=5)
        assert server.poll() is not None
    finally:
        for process in (server, other):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


def test_cancel_before_login_releases_server(tmp_path):
    server = sleeper()
    lease = RuntimeLease(tmp_path, 12346)
    lease.acquire(lambda: False, lambda: server, sys.executable)
    lease.release()
    server.wait(timeout=5)
    assert server.poll() is not None
