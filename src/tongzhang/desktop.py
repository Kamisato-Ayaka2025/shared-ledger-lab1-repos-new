"""The desktop workbench, built with native Qt widgets."""

import sys
from datetime import date
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QTabWidget,
    QInputDialog,
    QMessageBox,
    QDialog,
    QSplitter,
)
from PySide6.QtCore import Qt
from .widgets import Client, LoginDialog, table, fill, currency, show_json, confirm
from .forms import EntryDialog

STATUS = {"PENDING": "待审核", "APPROVED": "已审核", "REJECTED": "已驳回", "WITHDRAWN": "已撤回"}
STYLE = """
QMainWindow,QDialog { background:#f3f6f5; }
QWidget { font-family:'Microsoft YaHei'; font-size:13px; color:#203b36; }
QLabel#hero { font-size:25px; font-weight:700; padding:12px; color:#166655; }
QLabel#summary { background:#e1efe9; border-radius:8px; padding:18px; font-size:18px; }
QPushButton { background:#187662; color:white; border:0; border-radius:5px; padding:9px 15px; }
QPushButton:hover { background:#245f53; }
QPushButton:disabled { background:#a9bdb7; }
QLineEdit,QComboBox,QTextEdit { background:white; border:1px solid #c8d8d1; border-radius:4px; padding:7px; }
QTableWidget { background:white; alternate-background-color:#f1f7f4; gridline-color:#e1e9e5; border:1px solid #d5e0db; }
QHeaderView::section { background:#e3ede8; border:0; padding:9px; font-weight:600; }
QTabBar::tab { padding:12px 18px; background:#e2ebe7; }
QTabBar::tab:selected { background:#187662; color:white; }
"""


class Window(QMainWindow):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.state = {}
        self.context_data = {}
        self.entries = []
        self.budgets = []
        self.snapshots = []
        self.logs = []
        self.setWindowTitle("同账 · 多人共享记账")
        self.resize(1280, 850)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        top = QHBoxLayout()
        heading = QLabel("同账")
        heading.setObjectName("hero")
        top.addWidget(heading)
        self.identity = QLabel()
        top.addWidget(self.identity)
        top.addStretch()
        self.ledgers = QComboBox()
        self.ledgers.setMinimumWidth(220)
        top.addWidget(self.ledgers)
        self.create_button = self.button("创建账本", self.create_ledger, top)
        self.button("刷新", self.refresh, top)
        self.button("切换账号", self.switch_user, top)
        layout.addLayout(top)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.build_entries()
        self.build_members()
        self.build_finance()
        self.build_audit()
        self.ledgers.currentIndexChanged.connect(self.load_ledger)
        client.busy.connect(
            lambda busy: self.statusBar().showMessage(
                "正在处理…" if busy else "就绪 · 所有金额均为人民币"
            )
        )
        self.refresh()

    def button(self, label, callback, layout):
        button = QPushButton(label)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.tabs.addTab(widget, name)
        return layout

    @property
    def ledger_id(self):
        return self.ledgers.currentData()

    def build_entries(self):
        layout = self.page("收支与审核")
        filters = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItem("有效流程（隐藏撤回）", "")
        for key, label in STATUS.items():
            self.status_filter.addItem(label, key)
        self.status_filter.addItem("所有状态", "ALL")
        self.start = QLineEdit()
        self.start.setPlaceholderText("开始 YYYY-MM-DD")
        self.end = QLineEdit()
        self.end.setPlaceholderText("结束 YYYY-MM-DD")
        self.minimum = QLineEdit()
        self.minimum.setPlaceholderText("最低金额")
        self.maximum = QLineEdit()
        self.maximum.setPlaceholderText("最高金额")
        for widget in (self.status_filter, self.start, self.end, self.minimum, self.maximum):
            filters.addWidget(widget)
        self.button("查询", self.load_entries, filters)
        layout.addLayout(filters)
        second = QHBoxLayout()
        self.category_filter = QComboBox()
        self.member_filter = QComboBox()
        second.addWidget(self.category_filter)
        second.addWidget(self.member_filter)
        self.button("新增收支", self.new_entry, second)
        self.button("详情与历史", self.entry_detail, second)
        self.button("驳回重交", lambda: self.edit_entry("resubmit"), second)
        layout.addLayout(second)
        self.entry_table = table(
            ["日期", "方向", "金额（元）", "类别", "提交人", "状态", "版本", "备注"]
        )
        self.entry_table.doubleClicked.connect(self.entry_detail)
        layout.addWidget(self.entry_table)
        actions = QHBoxLayout()
        self.management_buttons = []
        for label, action in [("审核通过", "approve"), ("驳回", "reject"), ("撤回", "withdraw")]:
            self.management_buttons.append(
                self.button(label, lambda checked=False, a=action: self.entry_action(a), actions)
            )
        self.management_buttons.append(
            self.button("修改待审", lambda: self.edit_entry("edit"), actions)
        )
        self.management_buttons.append(
            self.button("更正已审核", lambda: self.edit_entry("correct"), actions)
        )
        actions.addStretch()
        layout.addLayout(actions)

    def build_members(self):
        layout = self.page("成员与邀请")
        bar = QHBoxLayout()
        self.people = QComboBox()
        bar.addWidget(self.people)
        self.button("邀请加入当前账本", self.invite, bar)
        self.button("我的待处理邀请", self.my_invitations, bar)
        self.button("查看账本邀请", self.ledger_invitations, bar)
        layout.addLayout(bar)
        self.member_table = table(["成员", "账号", "状态", "加入时间", "退出时间"])
        layout.addWidget(self.member_table)
        actions = QHBoxLayout()
        self.button("自主退出", lambda: self.member_action("leave"), actions)
        self.remove_button = self.button(
            "移除选中成员", lambda: self.member_action("remove"), actions
        )
        self.transfer_button = self.button(
            "设为账本管理员", lambda: self.member_action("transfer"), actions
        )
        layout.addLayout(actions)
        layout.addWidget(
            QLabel(
                "退出不删除历史。管理员须先由超级管理员完成移交；历史管理责任交给指定超级管理员。"
            )
        )

    def build_finance(self):
        layout = self.page("预算 · 统计 · 结算")
        bar = QHBoxLayout()
        today = date.today()
        self.finance_start = QLineEdit(today.replace(day=1).isoformat())
        self.finance_end = QLineEdit(today.isoformat())
        bar.addWidget(QLabel("统计区间"))
        bar.addWidget(self.finance_start)
        bar.addWidget(self.finance_end)
        self.button("计算", self.load_finance, bar)
        self.button("保存结算快照", self.settle, bar)
        layout.addLayout(bar)
        self.summary = QLabel("请选择账本")
        self.summary.setObjectName("summary")
        layout.addWidget(self.summary)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.category_stats = table(["类别", "收入", "支出"])
        self.member_stats = table(["成员", "收入", "支出"])
        split.addWidget(self.category_stats)
        split.addWidget(self.member_stats)
        layout.addWidget(split)
        self.budget_table = table(["预算月份", "期初预算", "可用预算", "版本"])
        self.snapshot_table = table(["创建时间", "区间", "收入", "支出", "状态"])
        lower = QSplitter(Qt.Orientation.Horizontal)
        lower.addWidget(self.budget_table)
        lower.addWidget(self.snapshot_table)
        layout.addWidget(lower)
        actions = QHBoxLayout()
        self.button("设置月度预算", self.budget, actions)
        self.button("查看快照来源明细", self.snapshot_detail, actions)
        layout.addLayout(actions)
        layout.addWidget(
            QLabel(
                "仅已审核记录计入；结算保存历史，不清零、不锁账、不转账。可用预算为负时提示超预算。"
            )
        )

    def build_audit(self):
        layout = self.page("操作日志")
        bar = QHBoxLayout()
        self.log_filter = QLineEdit()
        self.log_filter.setPlaceholderText("筛选操作者、动作、目标或时间")
        self.log_filter.textChanged.connect(self.show_logs)
        bar.addWidget(self.log_filter)
        self.button("刷新日志", self.load_logs, bar)
        self.button("查看变更前后值", self.log_detail, bar)
        layout.addLayout(bar)
        self.log_table = table(["时间（UTC）", "操作者", "动作", "目标"])
        layout.addWidget(self.log_table)

    def refresh(self):
        self.client.request("GET", "/bootstrap", self.bootstrapped)

    def bootstrapped(self, data):
        previous = self.ledger_id
        self.state = data
        self.identity.setText(
            data["user"]["name"] + (" · 超级管理员" if data["user"]["super"] else "")
        )
        self.create_button.setEnabled(bool(data["user"]["super"] or data["user"]["creator"]))
        self.transfer_button.setEnabled(bool(data["user"]["super"]))
        self.ledgers.blockSignals(True)
        self.ledgers.clear()
        for item in data["ledgers"]:
            self.ledgers.addItem(item["name"], item["id"])
        if self.ledgers.findData(previous) >= 0:
            self.ledgers.setCurrentIndex(self.ledgers.findData(previous))
        self.ledgers.blockSignals(False)
        self.people.clear()
        for person in data["users"]:
            self.people.addItem(f"{person['name']} ({person['username']})", person["id"])
        self.load_ledger()
        if not data["ledgers"]:
            self.statusBar().showMessage(
                "尚未加入账本：管理员可创建；成员可从“我的待处理邀请”接受邀请。"
            )

    def load_ledger(self):
        self.entries = []
        self.context_data = {}
        fill(self.entry_table, [])
        fill(self.member_table, [])
        fill(self.category_stats, [])
        fill(self.member_stats, [])
        fill(self.budget_table, [])
        fill(self.snapshot_table, [])
        fill(self.log_table, [])
        for index in (2, 3):
            self.tabs.setTabEnabled(index, False)
        if self.ledger_id:
            expected = self.ledger_id
            self.client.request(
                "GET",
                f"/ledgers/{expected}/context",
                lambda data: self.got_context(data) if expected == self.ledger_id else None,
            )

    def got_context(self, data):
        self.context_data = data
        for button in self.management_buttons + [self.remove_button]:
            button.setEnabled(data["manager"])
        self.tabs.setTabEnabled(2, data["manager"])
        self.tabs.setTabEnabled(3, data["manager"])
        self.category_filter.clear()
        self.category_filter.addItem("全部类别", "")
        for category in data["categories"]:
            self.category_filter.addItem(category["name"], category["id"])
        self.member_filter.clear()
        self.member_filter.addItem("全部成员", "")
        for member in data["members"]:
            self.member_filter.addItem(member["name"], member["user_id"])
        fill(
            self.member_table,
            [
                [
                    m["name"],
                    m["username"],
                    "在账本" if m["active"] else "已退出",
                    m["joined"][:19],
                    (m["left_at"] or "")[:19],
                ]
                for m in data["members"]
            ],
        )
        self.load_entries()
        if data["manager"]:
            self.load_finance()
            self.load_logs()

    def load_entries(self):
        if not self.ledger_id:
            return
        params = {
            "status": self.status_filter.currentData(),
            "start": self.start.text(),
            "end": self.end.text(),
            "minimum": self.minimum.text(),
            "maximum": self.maximum.text(),
            "category_id": self.category_filter.currentData(),
            "user_id": self.member_filter.currentData(),
        }
        expected = self.ledger_id
        self.client.request(
            "GET",
            f"/ledgers/{expected}/entries",
            lambda data: self.got_entries(data) if expected == self.ledger_id else None,
            params={k: v for k, v in params.items() if v},
        )

    def got_entries(self, data):
        self.entries = data
        fill(
            self.entry_table,
            [
                [
                    e["occurred"],
                    "收入" if e["direction"] == "INCOME" else "支出",
                    currency(e["amount"]),
                    e["category"],
                    e["submitter"],
                    STATUS[e["status"]],
                    e["version"],
                    e["note"],
                ]
                for e in data
            ],
        )

    def selected_entry(self):
        index = self.entry_table.currentRow()
        if index < 0 or index >= len(self.entries):
            QMessageBox.information(self, "选择记录", "请先选择一条账目。")
            return None
        return self.entries[index]

    def new_entry(self):
        if not self.context_data:
            return
        EntryDialog(self.client, self.ledger_id, self.context_data, self.load_ledger, self).exec()

    def edit_entry(self, action):
        item = self.selected_entry()
        if item:
            self.client.request(
                "GET",
                "/entries/" + item["id"],
                lambda detail: EntryDialog(
                    self.client,
                    self.ledger_id,
                    self.context_data,
                    self.load_ledger,
                    self,
                    detail,
                    action,
                ).exec(),
            )

    def entry_detail(self, *args):
        item = self.selected_entry()
        if item:
            self.client.request(
                "GET",
                "/entries/" + item["id"],
                lambda data: show_json(self, "账目详情与历史（金额单位：分）", data),
            )

    def entry_action(self, action):
        item = self.selected_entry()
        if not item:
            return
        reason = ""
        if action != "approve":
            reason, ok = QInputDialog.getText(self, "填写原因", "操作原因：")
            if not ok:
                return
        if not confirm(self, f"确认对 {currency(item['amount'])} 元的记录执行此操作？"):
            return
        self.client.request(
            "POST",
            "/entries/" + item["id"],
            lambda _: self.load_ledger(),
            {"action": action, "version": item["version"], "reason": reason},
        )

    def create_ledger(self):
        name, ok = QInputDialog.getText(self, "创建账本", "账本名称：")
        if ok:
            self.client.request("POST", "/ledgers", lambda _: self.refresh(), {"name": name})

    def invite(self):
        if self.ledger_id:
            self.client.request(
                "POST",
                f"/ledgers/{self.ledger_id}/invite",
                lambda _: QMessageBox.information(
                    self, "邀请已发送", "请受邀人登录后在“我的待处理邀请”中确认。"
                ),
                {"target": self.people.currentData()},
            )

    def my_invitations(self):
        def received(data):
            invitations = data["invitations"]
            if not invitations:
                QMessageBox.information(self, "邀请", "暂无待处理邀请。")
                return
            labels = [
                f"{i['ledger_name']} · 邀请人 {i['inviter']} · {i['id'][:8]}" for i in invitations
            ]
            chosen, ok = QInputDialog.getItem(
                self, "接受邀请", "选择要加入的账本：", labels, 0, False
            )
            if ok:
                self.client.request(
                    "POST",
                    "/invitations/" + invitations[labels.index(chosen)]["id"],
                    lambda _: self.refresh(),
                    {"action": "accept"},
                )

        self.client.request("GET", "/bootstrap", received)

    def ledger_invitations(self):
        if not self.ledger_id:
            return

        def received(data):
            pending = [i for i in data if i["status"] == "PENDING"]
            if not pending:
                QMessageBox.information(self, "邀请", "暂无可撤销邀请。")
                return
            labels = [f"{i['target']} · {i['expires'][:10]} · {i['id'][:8]}" for i in pending]
            choice, ok = QInputDialog.getItem(
                self, "账本邀请", "选择邀请以撤销：", labels, 0, False
            )
            if ok and confirm(self, "确认撤销邀请？"):
                self.client.request(
                    "POST",
                    "/invitations/" + pending[labels.index(choice)]["id"],
                    lambda _: self.refresh(),
                    {"action": "cancel"},
                )

        self.client.request("GET", f"/ledgers/{self.ledger_id}/records/invitations", received)

    def member_action(self, action):
        if not self.context_data:
            return
        if action == "leave":
            target = self.state["user"]["id"]
        else:
            index = self.member_table.currentRow()
            if index < 0:
                return
            target = self.context_data["members"][index]["user_id"]
        custodian = None
        if action != "transfer":
            people = [u for u in self.state["users"] if u["super"]]
            labels = [u["name"] for u in people]
            chosen, ok = QInputDialog.getItem(
                self, "历史接管", "选择超级管理员：", labels, 0, False
            )
            if not ok:
                return
            custodian = people[labels.index(chosen)]["id"]
        if confirm(self, "确认变更成员权限？变更立即生效，历史记录保留。"):
            self.client.request(
                "POST",
                f"/ledgers/{self.ledger_id}/members",
                lambda _: self.refresh(),
                {"target": target, "action": action, "custodian": custodian},
            )

    def load_finance(self):
        if not self.ledger_id:
            return
        expected = self.ledger_id
        self.client.request(
            "GET",
            f"/ledgers/{expected}/finance",
            lambda data: self.got_finance(data) if expected == self.ledger_id else None,
            params={"start": self.finance_start.text(), "end": self.finance_end.text()},
        )
        self.client.request(
            "GET",
            f"/ledgers/{expected}/records/snapshots",
            lambda data: self.got_snapshots(data) if expected == self.ledger_id else None,
        )

    def got_finance(self, data):
        self.summary.setText(
            f"收入  ¥{currency(data['income'])}     支出  ¥{currency(data['expense'])}     盈亏  ¥{currency(data['profit'])}"
        )
        fill(
            self.category_stats,
            [
                [name, currency(v["income"]), currency(v["expense"])]
                for name, v in data["categories"].items()
            ],
        )
        fill(
            self.member_stats,
            [
                [v["name"], currency(v["income"]), currency(v["expense"])]
                for v in data["members"].values()
            ],
        )
        self.budgets = data["budgets"]
        fill(
            self.budget_table,
            [
                [
                    b["month"],
                    currency(b["amount"]),
                    currency(b["available"]) + (" ⚠ 超预算" if b["available"] < 0 else ""),
                    b["version"],
                ]
                for b in self.budgets
            ],
        )

    def got_snapshots(self, data):
        self.snapshots = data
        fill(
            self.snapshot_table,
            [
                [
                    s["created"][:19],
                    s["start"] + " ～ " + s["end"],
                    currency(s["income"]),
                    currency(s["expense"]),
                    "来源已变化" if s["stale"] else "当前",
                ]
                for s in data
            ],
        )

    def budget(self):
        month, ok = QInputDialog.getText(
            self, "设置预算", "月份 YYYY-MM：", text=date.today().strftime("%Y-%m")
        )
        if not ok:
            return
        amount, ok = QInputDialog.getText(self, "设置预算", "期初预算（元）：")
        if not ok:
            return
        reason, ok = QInputDialog.getText(self, "设置预算", "变更原因：")
        if ok:
            version = next((b["version"] for b in self.budgets if b["month"] == month), 0)
            self.client.request(
                "POST",
                f"/ledgers/{self.ledger_id}/budget",
                lambda _: self.load_finance(),
                {"month": month, "amount": amount, "reason": reason, "version": version},
            )

    def settle(self):
        if self.ledger_id and confirm(self, "保存当前区间的结算快照？此操作不会清零或转账。"):
            self.client.request(
                "POST",
                f"/ledgers/{self.ledger_id}/settle",
                lambda _: self.load_finance(),
                {"start": self.finance_start.text(), "end": self.finance_end.text()},
            )

    def snapshot_detail(self):
        index = self.snapshot_table.currentRow()
        if index >= 0 and index < len(self.snapshots):
            import json

            show_json(
                self, "结算来源副本（金额单位：分）", json.loads(self.snapshots[index]["data"])
            )

    def load_logs(self):
        if self.ledger_id:
            expected = self.ledger_id
            self.client.request(
                "GET",
                f"/ledgers/{expected}/records/audit",
                lambda data: self.got_logs(data) if expected == self.ledger_id else None,
            )

    def got_logs(self, data):
        self.logs = data
        self.show_logs()

    def show_logs(self):
        query = self.log_filter.text().lower()
        self.filtered_logs = [
            item
            for item in self.logs
            if query
            in " ".join(str(item[k]) for k in ("actor", "action", "target", "created")).lower()
        ]
        fill(
            self.log_table,
            [[i["created"][:19], i["actor"], i["action"], i["target"]] for i in self.filtered_logs],
        )

    def log_detail(self):
        index = self.log_table.currentRow()
        if index >= 0 and index < len(self.filtered_logs):
            import json

            item = dict(self.filtered_logs[index])
            item["data"] = json.loads(item["data"])
            show_json(self, "只读操作日志", item)

    def switch_user(self):
        if not confirm(self, "退出当前账号并切换登录？"):
            return

        def logged_out(_):
            self.client.token = ""
            self.hide()
            login = LoginDialog(self.client, self)
            if login.exec() == QDialog.DialogCode.Accepted:
                self.refresh()
                self.show()
            else:
                self.close()

        self.client.request("POST", "/logout", logged_out)


def configure_fonts(app):
    from pathlib import Path
    from PySide6.QtGui import QFontDatabase, QFont

    font = Path("C:/Windows/Fonts/msyh.ttc")
    if font.exists():
        font_id = QFontDatabase.addApplicationFont(str(font))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))


def main():
    app = QApplication(sys.argv)
    configure_fonts(app)
    from PySide6.QtCore import QThreadPool

    app.aboutToQuit.connect(lambda: QThreadPool.globalInstance().waitForDone())
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    client = Client()
    client.error.connect(
        lambda message: QMessageBox.warning(QApplication.activeWindow(), "操作未完成", message)
    )
    login = LoginDialog(client)
    if login.exec() != QDialog.DialogCode.Accepted:
        return
    window = Window(client)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
