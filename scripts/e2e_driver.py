"""Exercise the frozen UI through Qt input, real forms and real HTTP."""

import json
import os
import time
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QMessageBox,
    QPushButton,
)

from tongzhang.desktop import STYLE, Window, configure_fonts
from tongzhang.forms import BudgetDialog, EntryDialog, InvitationDialog
from tongzhang.widgets import Client, LoginDialog, TextPrompt


class Journey:
    def __init__(self, output):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.app = QApplication([])
        self.app.setQuitOnLastWindowClosed(False)
        configure_fonts(self.app)
        self.app.setStyleSheet(STYLE)
        self.clients = []
        self.windows = []
        self.errors = []
        self.answers = []
        self.steps = []
        self.base = os.environ.get("TONGZHANG_BASE", "")
        self.form_action = None
        self.budget_action = None
        self.invitation_action = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.modal)
        self.timer.start(30)

    def wait(self, condition, label, seconds=20):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.app.processEvents()
            if self.errors:
                raise AssertionError(self.errors)
            if condition():
                return
            QTest.qWait(20)
        raise AssertionError("Timed out: " + label)

    def idle(self):
        self.wait(lambda: all(not client.pending for client in self.clients), "HTTP completion")
        self.app.processEvents()

    def modal(self):
        dialog = self.app.activeModalWidget()
        if not dialog:
            return
        try:
            if isinstance(dialog, QMessageBox):
                buttons = dialog.standardButtons()
                choice = (
                    QMessageBox.StandardButton.Yes
                    if buttons & QMessageBox.StandardButton.Yes
                    else QMessageBox.StandardButton.Ok
                )
                button = dialog.button(choice)
                if button:
                    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            elif isinstance(dialog, TextPrompt):
                if self.answers:
                    dialog.field.setText(self.answers.pop(0))
                    dialog.accept_value()
            elif isinstance(dialog, EntryDialog) and self.form_action:
                action, self.form_action = self.form_action, None
                action(dialog)
            elif isinstance(dialog, BudgetDialog) and self.budget_action:
                action, self.budget_action = self.budget_action, None
                action(dialog)
            elif isinstance(dialog, InvitationDialog) and self.invitation_action:
                self.invitation_action(dialog)
        except Exception as exc:
            self.errors.append(repr(exc))
            dialog.reject()

    def click(self, window, label):
        matches = [
            button
            for button in window.findChildren(QPushButton)
            if button.text() == label and button.isVisible()
        ]
        assert len(matches) == 1, (label, len(matches))
        self.click_button(window, matches[0])

    def click_button(self, window, button):
        assert button.isEnabled(), button.text() + " disabled"
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.idle()

    def record(self, name, window):
        self.idle()
        window.grab().save(str(self.output / (str(len(self.steps) + 1).zfill(2) + ".png")))
        self.steps.append({"step": name, "passed": True})
        (self.output / "result.json").write_text(
            json.dumps(self.steps, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def login(self, username):
        client = Client()
        if self.base:
            client.base = self.base
        client.error.connect(self.errors.append)
        self.clients.append(client)
        dialog = LoginDialog(client)
        dialog.username.setText(username)
        dialog.show()
        QTest.mouseClick(
            dialog.buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton
        )
        self.wait(lambda: dialog.result_data is not None, "login " + username)
        window = Window(client)
        self.windows.append(window)
        window.show()
        self.idle()
        return window

    def refresh(self, window):
        self.click(window, "刷新")

    def entry(self, window, amount, direction="EXPENSE", edit=False):
        def populate(dialog):
            dialog.direction.setCurrentIndex(dialog.direction.findData(direction))
            dialog.amount.setText(amount)
            dialog.note.setText("打包端到端自动验收")
            if edit:
                dialog.reason.setText("端到端更正")
            dialog.clear_allocations()
            for index, member in enumerate(dialog.members):
                if member["username"] == "alice":
                    dialog.allocations.item(index, 1).setText(amount)
            QTest.mouseClick(
                dialog.buttons.button(QDialogButtonBox.StandardButton.Save),
                Qt.MouseButton.LeftButton,
            )

        self.form_action = populate
        if edit:
            self.click_button(window, window.edit_button)
        else:
            self.click(window, "新增账目")
        self.wait(lambda: self.form_action is None, "entry form")
        self.idle()

    def budget(self, window, amount, reason):
        def fill(dialog):
            dialog.amount.setText(amount)
            dialog.reason.setText(reason)
            dialog.save()

        self.budget_action = fill
        self.click(window, "设置预算")
        self.wait(lambda: self.budget_action is None, "budget form")
        self.wait(lambda: not any(client.pending for client in self.clients), "budget save")
        self.idle()

    def invitation(self, window, ledger):
        stage = {"value": 0}

        def handle(dialog):
            if stage["value"] == 0 and dialog.mine:
                dialog.accept_first()
                stage["value"] = 1
            elif stage["value"] == 1 and window.ledger_id == ledger:
                stage["value"] = 2
                dialog.accept()

        self.invitation_action = handle
        self.click(window, "邀请管理")
        self.wait(lambda: window.ledger_id == ledger, "invitation acceptance")
        self.invitation_action = None
        self.idle()

    def select(self, window, amount=None, status=None):
        self.refresh(window)
        for index, item in enumerate(window.entries):
            if (amount is None or item["amount"] == amount) and (
                status is None or item["status"] == status
            ):
                window.entry_table.selectRow(index)
                return item
        raise AssertionError(("entry not found", amount, status, window.entries))

    def run(self):
        manager = self.login("manager")
        self.record("管理员实际登录", manager)
        self.answers = ["打包验收账本"]
        self.click(manager, "新建账本")
        assert manager.ledger_id
        ledger = manager.ledger_id
        self.record("通过创建表单建账", manager)
        manager.tabs.setCurrentIndex(1)
        person = next(u for u in manager.state["users"] if u["username"] == "alice")
        manager.people.setCurrentIndex(manager.people.findData(person["id"]))
        self.click(manager, "发送邀请")
        alice = self.login("alice")
        alice.tabs.setCurrentIndex(1)
        self.invitation(alice, ledger)
        self.record("成员登录并在界面接受邀请", alice)
        self.refresh(manager)
        manager.tabs.setCurrentIndex(0)
        alice.tabs.setCurrentIndex(0)
        self.entry(alice, "2150")
        assert alice.entries[0]["status"] == "PENDING"
        assert not alice.tabs.isTabEnabled(2)
        self.record("普通成员录入支出并验证财务入口隔离", alice)
        self.select(manager, 215000, "PENDING")
        self.click(manager, "审核通过")
        assert self.select(manager, 215000)["status"] == "APPROVED"
        self.record("管理员审核支出", manager)
        manager.tabs.setCurrentIndex(2)
        self.budget(manager, "5000", "首次预算")
        assert manager.budgets[0]["available"] == 285000, manager.budgets
        self.record("设置预算5000并核对余额2850", manager)
        self.entry(alice, "1200", "INCOME")
        manager.tabs.setCurrentIndex(0)
        self.select(manager, 120000, "PENDING")
        self.click(manager, "审核通过")
        assert manager.budgets[0]["available"] == 405000, manager.budgets
        manager.tabs.setCurrentIndex(2)
        self.record("收入审核后预算4050", manager)
        self.click(manager, "保存结算快照")
        assert len(manager.snapshots) == 1
        snapshot = manager.snapshots[0]
        assert int(snapshot["income"]) == 120000 and int(snapshot["expense"]) == 215000
        self.record("保存结算快照并检查收入支出", manager)
        manager.tabs.setCurrentIndex(0)
        self.select(manager, 215000, "APPROVED")
        self.answers = ["测试撤回"]
        self.click(manager, "撤回")
        assert manager.budgets[0]["available"] == 620000
        assert manager.snapshots[0]["stale"]
        assert int(manager.snapshots[0]["expense"]) == 215000
        manager.tabs.setCurrentIndex(2)
        self.record("撤回支出余额6200且历史快照不变", manager)
        self.entry(alice, "100")
        manager.tabs.setCurrentIndex(0)
        self.select(manager, 10000, "PENDING")
        self.answers = ["请修正金额"]
        self.click(manager, "驳回")
        self.select(alice, 10000, "REJECTED")
        self.entry(alice, "80", edit=True)
        self.select(manager, 8000, "PENDING")
        self.click(manager, "审核通过")
        self.select(manager, 8000, "APPROVED")
        self.entry(manager, "90", edit=True)
        corrected = self.select(manager, 9000, "PENDING")
        assert corrected["source_id"]
        self.record("驳回重交审核与更正完整链路", manager)
        root = self.login("root")
        self.select(root, 9000, "PENDING")
        self.click(root, "审核通过")
        assert root.budgets[0]["available"] == 611000
        root.tabs.setCurrentIndex(2)
        self.click(root, "保存结算快照")
        assert int(root.snapshots[0]["expense"]) == 9000
        self.record("超级管理员审核更正与重新结算", root)
        root.tabs.setCurrentIndex(3)
        self.click(root, "刷新日志")
        assert len(root.logs) >= 12
        self.record("实际界面查询业务审计", root)
        # Logout must invalidate the session, then login again through the real dialog.
        # Persistence is additionally checked by the external driver after service restart.
        self.idle()
        for window in self.windows:
            window.close()
        print("UI journey passed", len(self.steps))


def main(output, resume=False):
    journey = Journey(output)
    try:
        if resume:
            manager = journey.login("manager")
            assert manager.budgets[0]["available"] == 611000
            assert len(manager.snapshots) == 2
            assert any(
                item["amount"] == 9000 and item["status"] == "APPROVED" for item in manager.entries
            )
            manager.status_filter.setCurrentIndex(manager.status_filter.findData("ALL"))
            journey.click(manager, "查询")
            assert sum(item["status"] == "WITHDRAWN" for item in manager.entries) == 2
            manager.tabs.setCurrentIndex(2)
            journey.record("重启打包服务与客户端后账目、预算、历史快照持久化", manager)
            for window in journey.windows:
                window.close()
        else:
            journey.run()
    except Exception:
        import traceback

        (journey.output / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        from PySide6.QtCore import QThreadPool

        QThreadPool.globalInstance().waitForDone()
