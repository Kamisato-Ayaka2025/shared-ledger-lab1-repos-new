"""Exercise real HTTP transport and render desktop for inspection."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import threading
import tempfile
import time
import uvicorn
from PySide6.QtWidgets import QApplication
from tongzhang.api import create_app
from tongzhang.desktop import Window, STYLE, configure_fonts
from tongzhang.widgets import Client

folder = tempfile.TemporaryDirectory()
app_api = create_app(Path(folder.name) / "ui.db", demo=True)
s = app_api.state.service
t = s.login("manager", "Demo123!")["token"]
ledger = s.create_ledger(t, "同账 · 项目协作账本")["id"]
s.set_budget(t, ledger, "2026-11", "5000", 0, "初始预算")
server = uvicorn.Server(uvicorn.Config(app_api, host="127.0.0.1", port=18765, log_level="error"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
for _ in range(100):
    if server.started:
        break
    time.sleep(0.05)
app = QApplication([])
configure_fonts(app)
app.setStyle("Fusion")
app.setStyleSheet(STYLE)
client = Client()
client.base = "http://127.0.0.1:18765"
client.token = t
errors = []
client.error.connect(errors.append)
window = Window(client)
window.show()
for _ in range(1500):
    app.processEvents()
    time.sleep(0.02)
    if window.context_data and not client.pending:
        break
assert window.context_data.get("manager"), errors
assert not client.pending, "HTTP tasks did not finish"
assert not errors, errors
out = Path(__file__).resolve().parents[2] / "HW" / "HW3" / "检查"
out.mkdir(parents=True, exist_ok=True)
window.grab().save(str(out / "工作台.png"))
window.tabs.setCurrentIndex(2)
app.processEvents()
window.grab().save(str(out / "预算统计.png"))
window.close()
server.should_exit = True
thread.join(timeout=5)
folder.cleanup()
print("Real HTTP desktop load and screenshots passed")
