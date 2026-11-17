"""One-click local launcher; a second client reuses the running service."""

import os
import subprocess
import sys
import time
from pathlib import Path
import httpx


def service_port():
    """Allow an isolated instance for tests; production uses 8765."""
    return int(os.environ.get("TONGZHANG_PORT", "8765"))


def service_base():
    return "http://127.0.0.1:" + str(service_port())


def launch():
    if "--e2e-resume" in sys.argv:
        from e2e_driver import main

        main(sys.argv[sys.argv.index("--e2e-resume") + 1], resume=True)
        return
    if "--e2e-ui" in sys.argv:
        from e2e_driver import main

        main(sys.argv[sys.argv.index("--e2e-ui") + 1])
        return
    if "--smoke-ui" in sys.argv:
        from PySide6.QtWidgets import QApplication
        from tongzhang.widgets import Client, LoginDialog
        from tongzhang.desktop import configure_fonts, STYLE

        app = QApplication([])
        configure_fonts(app)
        app.setStyleSheet(STYLE)
        dialog = LoginDialog(Client())
        dialog.show()
        app.processEvents()
        target = Path(sys.argv[sys.argv.index("--smoke-ui") + 1])
        dialog.grab().save(str(target))
        dialog.close()
        return
    if "--server" in sys.argv:
        from tongzhang.api import create_app
        import uvicorn

        folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Tongzhang"
        folder.mkdir(parents=True, exist_ok=True)
        import logging

        logging.basicConfig(
            filename=folder / "server.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            encoding="utf-8",
        )
        uvicorn.run(
            create_app(folder / "demo.db", demo=True),
            host="127.0.0.1",
            port=service_port(),
            log_config=None,
        )
        return

    def healthy():
        try:
            result = httpx.get(service_base() + "/health", timeout=0.5)
            return result.status_code == 200 and result.json().get("version") == "0.1.0"
        except (httpx.HTTPError, ValueError):
            return False

    def start_service():
        command = [sys.executable]
        if not getattr(sys, "frozen", False):
            command.append(str(Path(__file__).resolve()))
        command.append("--server")
        folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Tongzhang"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "startup.log").open("a", encoding="utf-8") as log:
            child = subprocess.Popen(
                command,
                stdout=log,
                stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        for _ in range(40):
            if healthy():
                break
            time.sleep(0.25)
        return child

    from tongzhang.runtime import RuntimeLease

    folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Tongzhang"
    lease = RuntimeLease(folder, service_port())
    lease.acquire(healthy, start_service, sys.executable)
    try:
        if "--verify-tray" in sys.argv:
            from tray_driver import main

            main(sys.argv[sys.argv.index("--verify-tray") + 1])
        else:
            from tongzhang.desktop import main

            main()
    finally:
        lease.release()


if __name__ == "__main__":
    launch()
