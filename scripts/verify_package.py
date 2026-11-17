"""Verify the frozen application creates a Qt window, not an error dialog."""

import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
exe = root / "dist/Tongzhang/Tongzhang.exe"
assert not (exe.parent / "_internal/icuuc.dll").exists(), "Conflicting ICU DLL bundled"
with tempfile.TemporaryDirectory() as temp:
    screenshot = Path(temp) / "login.png"
    env = dict(os.environ)
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    for key in ("QT_QPA_PLATFORM", "QT_PLUGIN_PATH", "PYTHONPATH", "PYTHONHOME"):
        env.pop(key, None)
    process = subprocess.Popen(
        [str(exe), "--smoke-ui", str(screenshot)],
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        code = process.wait(timeout=30)
        assert code == 0, f"Application exited with {code}"
        assert screenshot.exists() and screenshot.stat().st_size > 1000
        target = root.parent / "HW/HW3/检查/打包登录窗口.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(screenshot.read_bytes())
        print("Frozen application created login window and exited successfully")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
