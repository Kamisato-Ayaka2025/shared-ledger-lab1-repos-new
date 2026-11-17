"""Run the Qt journey locally against a real server, without packaging."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "tmp" / "e2e-local"
PORT = 18765
BASE = f"http://127.0.0.1:{PORT}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = OUT / "data"
    data.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT / "scripts")
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["TONGZHANG_BASE"] = BASE
    env.pop("PYTHONHOME", None)
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", PORT)) != 0, "port already in use"
    database = str(data / "journey.db").replace("\\", "/")
    code = (
        "from tongzhang.api import create_app\n"
        "import uvicorn\n"
        f"app = create_app(r'{database}', demo=True)\n"
        "uvicorn.run(app, host='127.0.0.1', port=%d, log_config=None)\n" % PORT
    )
    served = subprocess.Popen(
        [sys.executable, "-c", code],
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        for _ in range(120):
            assert served.poll() is None, "server exited"
            try:
                if httpx.get(BASE + "/health", timeout=0.5).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        target = str(OUT / "journey").replace("\\", "/")
        journey = subprocess.run(
            [sys.executable, "-c", f"from e2e_driver import main; main(r'{target}')"],
            env=env,
            cwd=ROOT / "scripts",
        )
        assert journey.returncode == 0, f"journey failed with {journey.returncode}"
        steps = json.loads((OUT / "journey/result.json").read_text(encoding="utf-8"))
        print("journey checkpoints:", len(steps))
        print("screenshots:", OUT / "journey")
    finally:
        served.terminate()
        served.wait(timeout=10)


if __name__ == "__main__":
    main()
