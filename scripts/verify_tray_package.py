"""Check the frozen tray exit also releases its isolated backend."""

import json
import os
from pathlib import Path
import socket
import subprocess
import time
import sys

root = Path(__file__).resolve().parents[1]
exe = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / "dist/Tongzhang/Tongzhang.exe"
folder = root.parent / "HW/HW3/检查" / ("托盘退出-" + time.strftime("%Y%m%d-%H%M%S"))
folder.mkdir(parents=True)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
env = dict(os.environ, LOCALAPPDATA=str(folder), TONGZHANG_PORT=str(port))
for key in ("QT_QPA_PLATFORM", "QT_PLUGIN_PATH", "PYTHONHOME", "PYTHONPATH"):
    env.pop(key, None)
result = folder / "result.json"
process = subprocess.Popen([str(exe), "--verify-tray", str(result)], env=env)
try:
    assert process.wait(timeout=90) == 0
    steps = json.loads(result.read_text(encoding="utf-8"))
    assert len(steps) == 3
    registry = json.loads(
        (folder / "Tongzhang" / f"runtime-{port}.json").read_text(encoding="utf-8")
    )
    assert registry["clients"] == [] and "server" not in registry
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", port)) != 0
    print("PASS: frozen login, tray hide/restore/exit, client exit, backend stopped", flush=True)
    print(str(folder), flush=True)
finally:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=10)
