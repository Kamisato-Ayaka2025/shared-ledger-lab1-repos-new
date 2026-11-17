"""Run the packaged client/server journey in a fresh, retained evidence directory."""

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import httpx

root = Path(__file__).resolve().parents[1]
exe = root / "dist/Tongzhang/Tongzhang.exe"
output = root.parent / "HW/HW3/检查" / ("EXE完整验收-" + time.strftime("%Y%m%d-%H%M%S"))
output.mkdir(parents=True)
env = dict(os.environ, LOCALAPPDATA=str(output / "data"))
env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
for key in ("PYTHONPATH", "PYTHONHOME", "QT_QPA_PLATFORM", "QT_PLUGIN_PATH"):
    env.pop(key, None)
with socket.socket() as probe:
    assert probe.connect_ex(("127.0.0.1", 8765)) != 0, (
        "Port 8765 occupied: refuse to touch another database"
    )
server = None
client = None


def start_server():
    process = subprocess.Popen(
        [str(exe), "--server"], env=env, creationflags=subprocess.CREATE_NO_WINDOW
    )
    for _ in range(80):
        assert process.poll() is None, "server exited"
        try:
            if (
                httpx.get("http://127.0.0.1:8765/health", timeout=0.5, trust_env=False).status_code
                == 200
            ):
                return process
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    process.terminate()
    raise AssertionError("server startup timeout")


try:
    print(str(output), flush=True)
    server = start_server()
    client = subprocess.Popen([str(exe), "--e2e-ui", str(output / "journey")], env=env)
    assert client.wait(timeout=600) == 0, "packaged journey failed"
    steps = json.loads((output / "journey/result.json").read_text(encoding="utf-8"))
    assert len(steps) == 12 and all(step["passed"] for step in steps)
    server.terminate()
    server.wait(timeout=10)
    server = start_server()
    client = subprocess.Popen([str(exe), "--e2e-resume", str(output / "restart")], env=env)
    assert client.wait(timeout=120) == 0, "restart UI checks failed"
    resumed = json.loads((output / "restart/result.json").read_text(encoding="utf-8"))
    assert len(resumed) == 1 and resumed[0]["passed"]
    result = {
        "passed": True,
        "executable": str(exe),
        "sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
        "steps": steps + resumed,
        "method": "Frozen Qt widgets driven by QTest; actual HTTP to separate frozen server; no direct business-service calls; service restarted for persistence verification",
    }
    (output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("PACKAGED END-TO-END PASSED: 13 checkpoints", flush=True)
except Exception:
    import traceback

    (output / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    raise
finally:
    for process in (client, server):
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
