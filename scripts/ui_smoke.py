"""Seed demo data, render the workbench and key dialogs for visual review."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import threading
import time
import uuid
from datetime import date
from pathlib import Path

import uvicorn
from PySide6.QtWidgets import QApplication

from tongzhang.api import create_app
from tongzhang.desktop import STYLE, Window, configure_fonts
from tongzhang.forms import (
    BudgetDialog,
    EntryDetailDialog,
    EntryDialog,
    LogDetailDialog,
    SnapshotDialog,
)
from tongzhang.widgets import Client, LoginDialog

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "HW" / "HW3" / "检查" / "界面优化-优化后"


def seed(service):
    """Create a small but realistic ledger so the screenshots are not empty."""
    token = service.login("manager", "Demo123!")["token"]
    ledger = service.create_ledger(token, "同账 · 项目协作账本")["id"]
    people = {user["username"]: user["id"] for user in service.bootstrap(token)["users"]}
    alice = service.login("alice", "Demo123!")["token"]
    invitation = service.invite(token, ledger, people["alice"])
    service.invitation_action(alice, invitation["id"], "accept")
    categories = service.context(token, ledger)["categories"]
    expense = next(item["id"] for item in categories if item["direction"] == "EXPENSE")
    income = next(item["id"] for item in categories if item["direction"] == "INCOME")
    today = date.today().isoformat()

    def submit(direction, amount, category, note, who="alice"):
        actor = alice if who == "alice" else token
        return service.submit(
            actor,
            ledger,
            {
                "direction": direction,
                "amount": amount,
                "category_id": category,
                "occurred": today,
                "note": note,
                "participants": [{"user_id": people[who], "amount": amount}],
            },
            str(uuid.uuid4()),
        )

    lunch = submit("EXPENSE", "2150", expense, "团队午餐")
    service.entry_action(token, lunch["id"], "approve", lunch["version"])
    project = submit("INCOME", "1200", income, "项目收入")
    service.entry_action(token, project["id"], "approve", project["version"])
    office = submit("EXPENSE", "300", expense, "办公用品")
    bus = submit("EXPENSE", "90", expense, "交通补录")
    service.entry_action(token, bus["id"], "reject", bus["version"], "金额与发票不符")
    service.set_budget(token, ledger, date.today().strftime("%Y-%m"), "5000", 0, "初始预算")
    service.settle(token, ledger, date.today().replace(day=1).isoformat(), today)
    return ledger, token, people, office


def capture(widget, name):
    widget.grab().save(str(OUT / name))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    folder = tempfile.TemporaryDirectory()
    api = create_app(Path(folder.name) / "ui.db", demo=True)
    service = api.state.service
    ledger, token, people, office = seed(service)
    server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=18765, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)

    app = QApplication([])
    configure_fonts(app)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    client = Client()
    client.base = "http://127.0.0.1:18765"
    client.token = token
    errors = []
    client.error.connect(errors.append)
    window = Window(client)
    window.show()
    for _ in range(2000):
        app.processEvents()
        time.sleep(0.01)
        if window.context_data and not client.pending and window.logs and window.snapshots:
            break
    assert window.context_data.get("manager"), errors
    assert not errors, errors

    pending = next(
        index for index, item in enumerate(window.entries) if item["status"] == "PENDING"
    )
    window.entry_table.selectRow(pending)
    app.processEvents()
    capture(window, "01_账目.png")

    window.tabs.setCurrentIndex(1)
    app.processEvents()
    capture(window, "02_成员.png")

    window.tabs.setCurrentIndex(2)
    app.processEvents()
    capture(window, "03_财务.png")
    window.tabs.setCurrentIndex(3)
    app.processEvents()
    capture(window, "04_日志.png")

    context = window.context_data
    form = EntryDialog(client, ledger, context, lambda: None, window, user_id=people["manager"])
    form.amount.setText("300.00")
    form.split_evenly()
    form.note.setText("办公用品采购")
    form.show()
    app.processEvents()
    capture(form, "05_新增账目.png")
    form.close()

    detail = EntryDetailDialog(window, service.detail(token, office["id"]))
    detail.show()
    app.processEvents()
    capture(detail, "06_账目详情.png")
    detail.close()

    budget = BudgetDialog(client, ledger, window.budgets, lambda: None, window)
    budget.show()
    app.processEvents()
    capture(budget, "07_设置预算.png")
    budget.close()

    snapshot = SnapshotDialog(window, window.snapshots[0])
    snapshot.show()
    app.processEvents()
    capture(snapshot, "08_结算快照.png")
    snapshot.close()

    log = LogDetailDialog(window, next(item for item in window.logs if item["action"] == "approve"))
    log.show()
    app.processEvents()
    capture(log, "09_日志详情.png")
    log.close()

    login = LoginDialog(Client())
    login.show()
    app.processEvents()
    capture(login, "10_登录.png")
    login.close()

    (ROOT / "HW" / "HW3" / "检查" / "工作台.png").unlink(missing_ok=True)
    (ROOT / "HW" / "HW3" / "检查" / "工作台.png").write_bytes((OUT / "01_账目.png").read_bytes())
    (ROOT / "HW" / "HW3" / "检查" / "预算统计.png").write_bytes((OUT / "03_财务.png").read_bytes())
    window.close()
    server.should_exit = True
    thread.join(timeout=5)
    folder.cleanup()
    print("Rendered workbench and dialogs to", OUT)


if __name__ == "__main__":
    main()
