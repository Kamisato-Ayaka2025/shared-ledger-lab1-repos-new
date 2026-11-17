"""One-click local launcher; a second client reuses the running service."""

import os
import subprocess
import sys
import time
from pathlib import Path
import httpx


def launch():
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
            create_app(folder / "demo.db", demo=True), host="127.0.0.1", port=8765, log_config=None
        )
        return

    def healthy():
        try:
            result = httpx.get("http://127.0.0.1:8765/health", timeout=0.5)
            return result.status_code == 200 and result.json().get("version") == "0.1.0"
        except (httpx.HTTPError, ValueError):
            return False

    if not healthy():
        command = [sys.executable]
        if not getattr(sys, "frozen", False):
            command.append(str(Path(__file__).resolve()))
        command.append("--server")
        folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Tongzhang"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "startup.log").open("a", encoding="utf-8") as log:
            subprocess.Popen(
                command,
                stdout=log,
                stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        for _ in range(40):
            if healthy():
                break
            time.sleep(0.25)
    from tongzhang.desktop import main

    main()


if __name__ == "__main__":
    launch()
