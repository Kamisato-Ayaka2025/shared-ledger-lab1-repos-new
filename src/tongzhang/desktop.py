"""The desktop workbench, built with native Qt widgets."""

import sys
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .forms import (
    BudgetDialog,
    EntryDetailDialog,
    EntryDialog,
    InvitationDialog,
    LogDetailDialog,
    SnapshotDialog,
)
from .widgets import (
    ACCENT,
    DANGER,
    EXPENSE,
    INCOME,
    INK,
    MUTED,
    OK,
    STATUS,
    STATUS_COLORS,
    STYLE,
    WARN,
    Card,
    Cell,
    ChoicePrompt,
    Client,
    LoginDialog,
    StatCard,
    TextPrompt,
    action_label,
    beijing,
    configure_fonts,
    confirm,
    date_field,
    date_text,
    direction_label,
    fill,
    new_button,
    short_id,
    table,
    yuan,
)

ACTION_LABELS = {"approve": "审核通过", "reject": "驳回", "withdraw": "撤回"}
EDIT_LABELS = {"edit": "修改待审", "correct": "更正", "resubmit": "驳回重交"}


class Window(QMainWindow):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.user_id = ""
        self.state = {}
        self.context_data = {}
        self.entries = []
        self.budgets = []
        self.snapshots = []
        self.logs = []
        self.filtered_logs = []
        self.pending_action = None
        self.setWindowTitle("同账 · 多人共享记账")
        self.resize(1280, 850)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.build_header())
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(26, 16, 26, 12)
        body_layout.setSpacing(0)
        outer.addWidget(body, 1)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        body_layout.addWidget(self.tabs, 1)
        self.build_entries()
        self.build_members()
        self.build_finance()
        self.build_audit()
        self.ledgers.currentIndexChanged.connect(self.load_ledger)
        self.statusBar().showMessage("就绪 · 所有金额均为人民币")
        client.busy.connect(self.show_busy)
        self.refresh()

    # ------------------------------------------------------------------ shell

    def build_header(self):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(64)
        row = QHBoxLayout(header)
        row.setContentsMargins(26, 0, 20, 0)
        row.setSpacing(10)
        brand = QLabel("同账")
        brand.setObjectName("brand")
        row.addWidget(brand)
        tagline = QLabel("多人共享记账")
        tagline.setObjectName("brandTag")
        row.addWidget(tagline)
        row.addStretch()
        self.button("刷新", self.refresh, row, ghost=True)
        self.ledgers = QComboBox()
        self.ledgers.setMinimumWidth(210)
        self.ledgers.setMaximumWidth(300)
        self.ledgers.setFixedHeight(36)
        row.addWidget(self.ledgers)
        self.create_button = self.button("新建账本", self.create_ledger, row)
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(26)
        row.addWidget(divider)
        self.identity = QLabel()
        self.identity.setObjectName("identity")
        self.identity.setFixedHeight(26)
        row.addWidget(self.identity)
        self.button("切换账号", self.switch_user, row, ghost=True)
        return header

    def button(self, text, callback, layout, primary=False, danger=False, ghost=False):
        button = new_button(text, callback, primary, danger, ghost)
        layout.addWidget(button)
        return button

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(12)
        self.tabs.addTab(widget, name)
        return layout

    def show_busy(self, busy):
        if busy:
            self.statusBar().showMessage("正在处理…")
        else:
            self.statusBar().showMessage("就绪 · 所有金额均为人民币")

    @property
    def ledger_id(self):
        return self.ledgers.currentData()

    def notice(self, label, text):
        label.setText(text)
        label.setVisible(bool(text))

    # ----------------------------------------------------------------- entries

    def build_entries(self):
        layout = self.page("账目")
        self.entry_notice = QLabel("")
        self.entry_notice.setObjectName("notice")
        self.entry_notice.setWordWrap(True)
        self.entry_notice.setVisible(False)
        layout.addWidget(self.entry_notice)

        filters = Card()
        row = QHBoxLayout()
        row.setSpacing(8)
        self.status_filter = QComboBox()
        self.status_filter.setMinimumWidth(150)
        self.status_filter.addItem("有效流程（隐藏撤回）", "")
        for key, label in STATUS.items():
            self.status_filter.addItem(label, key)
        self.status_filter.addItem("所有状态", "ALL")
        self.category_filter = QComboBox()
        self.category_filter.setMinimumWidth(110)
        self.member_filter = QComboBox()
        self.member_filter.setMinimumWidth(110)
        self.start = date_field(allow_empty=True)
        self.end = date_field(allow_empty=True)
        row.addWidget(self.status_filter)
        row.addWidget(self.category_filter)
        row.addWidget(self.member_filter)
        row.addSpacing(4)
        row.addWidget(self.muted("日期"))
        row.addWidget(self.start)
        row.addWidget(self.muted("至"))
        row.addWidget(self.end)
        row.addStretch()
        row.addWidget(new_button("重置", self.reset_filters, ghost=True))
        row.addWidget(new_button("查询", self.load_entries))
        self.more_button = new_button("更多筛选", self.toggle_filters, ghost=True)
        row.addWidget(self.more_button)
        filters.add_layout(row)
        self.extra_filters = QWidget()
        extra = QHBoxLayout(self.extra_filters)
        extra.setContentsMargins(0, 0, 0, 0)
        extra.setSpacing(8)
        self.minimum = QLineEdit()
        self.minimum.setPlaceholderText("最低金额（元）")
        self.minimum.setMaximumWidth(180)
        self.maximum = QLineEdit()
        self.maximum.setPlaceholderText("最高金额（元）")
        self.maximum.setMaximumWidth(180)
        extra.addWidget(self.minimum)
        extra.addWidget(self.maximum)
        extra.addStretch()
        self.extra_filters.setVisible(False)
        filters.add(self.extra_filters)
        layout.addWidget(filters)

        self.entry_card = Card("账目明细")
        self.new_button = self.entry_card.add_button("新增账目", self.new_entry, primary=True)
        self.entry_table = table(
            ["日期", "方向", "金额", "类别", "提交人", "状态", "备注"],
            widths=[100, 70, 120, 100, 90, 80, 0],
            aligns=[None, None, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter],
        )
        self.entry_table.itemSelectionChanged.connect(self.selection_changed)
        self.entry_table.doubleClicked.connect(self.entry_detail)
        self.entry_card.add(self.entry_table, 1)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.entry_count = self.muted("共 0 笔")
        self.entry_hint = self.muted("")
        footer.addWidget(self.entry_count)
        footer.addWidget(self.entry_hint)
        footer.addStretch()
        self.detail_button = new_button("详情", self.entry_detail)
        self.edit_button = new_button("修改", self.edit_entry)
        self.withdraw_button = new_button(
            "撤回", lambda: self.entry_action("withdraw"), danger=True
        )
        self.reject_button = new_button("驳回", lambda: self.entry_action("reject"), danger=True)
        self.approve_button = new_button(
            "审核通过", lambda: self.entry_action("approve"), primary=True
        )
        for widget in (
            self.detail_button,
            self.edit_button,
            self.withdraw_button,
            self.reject_button,
            self.approve_button,
        ):
            footer.addWidget(widget)
        self.entry_card.add_layout(footer)
        layout.addWidget(self.entry_card, 1)
        self.refresh_entry_actions()

    def muted(self, text):
        label = QLabel(text)
        label.setObjectName("muted")
        return label

    def toggle_filters(self):
        visible = not self.extra_filters.isVisible()
        self.extra_filters.setVisible(visible)
        self.more_button.setText("收起筛选" if visible else "更多筛选")

    def reset_filters(self):
        self.status_filter.setCurrentIndex(0)
        self.category_filter.setCurrentIndex(0)
        self.member_filter.setCurrentIndex(0)
        self.start.setDate(self.start.minimumDate())
        self.end.setDate(self.end.minimumDate())
        self.minimum.clear()
        self.maximum.clear()
        self.load_entries()

    # --------------------------------------------------------------- members

    def build_members(self):
        layout = self.page("成员")
        self.member_notice = QLabel("")
        self.member_notice.setObjectName("notice")
        self.member_notice.setWordWrap(True)
        self.member_notice.setVisible(False)
        layout.addWidget(self.member_notice)
        invite = Card("邀请成员", "受邀人确认后加入账本，邀请七天内有效。")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.people = QComboBox()
        self.people.setMinimumWidth(230)
        row.addWidget(self.people)
        self.invite_button = new_button("发送邀请", self.invite, primary=True)
        row.addWidget(self.invite_button)
        row.addStretch()
        row.addWidget(new_button("邀请管理", self.invitation_manager))
        invite.add_layout(row)
        layout.addWidget(invite)
        card = Card("成员列表")
        self.member_table = table(
            ["成员", "账号", "角色", "状态", "加入时间"], [0, 130, 120, 90, 160]
        )
        self.member_table.itemSelectionChanged.connect(self.member_selection_changed)
        card.add(self.member_table, 1)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addWidget(new_button("自主退出", lambda: self.member_action("leave"), danger=True))
        self.remove_button = new_button(
            "移除成员", lambda: self.member_action("remove"), danger=True
        )
        footer.addWidget(self.remove_button)
        self.transfer_button = new_button("设为账本管理员", lambda: self.member_action("transfer"))
        footer.addWidget(self.transfer_button)
        footer.addStretch()
        card.add_layout(footer)
        hint = self.muted("退出或移除不删除历史记录；管理员须先由超级管理员完成移交。")
        card.add(hint)
        layout.addWidget(card, 1)
        self.member_selection_changed()

    def member_selection_changed(self):
        selected = self.member_table.currentRow() >= 0
        self.remove_button.setEnabled(selected)
        self.transfer_button.setEnabled(selected and bool(self.state.get("user", {}).get("super")))

    # --------------------------------------------------------------- finance

    def build_finance(self):
        layout = self.page("财务")
        bar = Card()
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.muted("统计区间"))
        today = date.today()
        self.finance_start = date_field(today.replace(day=1).isoformat())
        self.finance_end = date_field(today.isoformat())
        row.addWidget(self.finance_start)
        row.addWidget(self.muted("至"))
        row.addWidget(self.finance_end)
        row.addStretch()
        row.addWidget(new_button("计算", self.load_finance))
        row.addWidget(new_button("保存结算快照", self.settle, primary=True))
        bar.add_layout(row)
        layout.addWidget(bar)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.stat_income = StatCard("本期收入")
        self.stat_expense = StatCard("本期支出")
        self.stat_profit = StatCard("本期盈亏")
        self.stat_budget = StatCard("本月可用预算")
        for card in (self.stat_income, self.stat_expense, self.stat_profit, self.stat_budget):
            stats.addWidget(card, 1)
        layout.addLayout(stats)

        upper = QHBoxLayout()
        upper.setSpacing(12)
        category_card = Card("类别统计")
        self.category_stats = table(["类别", "收入", "支出"], [0, 140, 140])
        category_card.add(self.category_stats, 1)
        upper.addWidget(category_card, 1)
        member_card = Card("成员统计")
        self.member_stats = table(["成员", "收入", "支出"], [0, 140, 140])
        member_card.add(self.member_stats, 1)
        upper.addWidget(member_card, 1)
        layout.addLayout(upper, 1)

        lower = QHBoxLayout()
        lower.setSpacing(12)
        budget_card = Card("月度预算")
        budget_card.add_button("设置预算", self.budget)
        self.budget_table = table(["月份", "期初预算", "可用预算", "版本"], [0, 120, 120, 60])
        budget_card.add(self.budget_table, 1)
        lower.addWidget(budget_card, 1)
        snapshot_card = Card("结算快照")
        snapshot_card.add_button("查看来源", self.snapshot_detail)
        self.snapshot_table = table(
            ["保存时间", "统计区间", "收入", "支出", "状态"], [140, 0, 80, 80, 95]
        )
        snapshot_card.add(self.snapshot_table, 1)
        lower.addWidget(snapshot_card, 1)
        layout.addLayout(lower, 1)
        layout.addWidget(
            self.muted(
                "仅已审核记录计入；可用预算＝期初预算＋收入－支出；结算只保存历史，不清零、不锁账。"
            )
        )

    # ------------------------------------------------------------------ audit

    def build_audit(self):
        layout = self.page("日志")
        card = Card("操作日志", "时间已转换为北京时间")
        self.log_filter = QLineEdit()
        self.log_filter.setPlaceholderText("筛选操作者、动作或对象")
        self.log_filter.setMinimumWidth(240)
        self.log_filter.textChanged.connect(self.show_logs)
        card.head.insertWidget(2, self.log_filter)
        card.add_button("刷新日志", self.load_logs)
        card.add_button("查看详情", self.log_detail)
        self.log_table = table(["时间", "操作者", "动作", "对象"], [160, 120, 130, 0])
        card.add(self.log_table, 1)
        layout.addWidget(card, 1)

    # ------------------------------------------------------------------ state

    def refresh(self):
        self.client.request("GET", "/bootstrap", self.bootstrapped)

    def bootstrapped(self, data):
        previous = self.ledger_id
        self.state = data
        self.user_id = data["user"]["id"]
        name = data["user"]["name"]
        if data["user"]["super"] and name != "超级管理员":
            name += " · 超级管理员"
        self.identity.setText(name)
        self.create_button.setEnabled(bool(data["user"]["super"] or data["user"]["creator"]))
        self.ledgers.blockSignals(True)
        self.ledgers.clear()
        for item in data["ledgers"]:
            self.ledgers.addItem(item["name"], item["id"])
        if self.ledgers.findData(previous) >= 0:
            self.ledgers.setCurrentIndex(self.ledgers.findData(previous))
        self.ledgers.blockSignals(False)
        pending = len(data.get("invitations", []))
        self.notice(
            self.member_notice,
            f"你有 {pending} 条待处理邀请，可在「邀请管理」中接受。" if pending else "",
        )
        self.load_ledger()
        if not data["ledgers"]:
            self.notice(
                self.entry_notice,
                "尚未加入账本。有建账资格的用户可在右上角「新建账本」；"
                "受邀成员可在「成员 → 邀请管理」中接受邀请。",
            )

    def clear_views(self):
        self.entries = []
        self.context_data = {}
        for widget in (
            self.entry_table,
            self.member_table,
            self.category_stats,
            self.member_stats,
            self.budget_table,
            self.snapshot_table,
            self.log_table,
        ):
            fill(widget, [])
        self.entry_count.setText("共 0 笔")
        self.entry_hint.setText("")
        for card in (self.stat_income, self.stat_expense, self.stat_profit, self.stat_budget):
            card.show_value("—", MUTED)
        self.people.clear()

    def load_ledger(self):
        self.clear_views()
        for index in (2, 3):
            self.tabs.setTabEnabled(index, False)
        self.notice(self.entry_notice, "")
        if self.ledger_id:
            expected = self.ledger_id
            self.client.request(
                "GET",
                f"/ledgers/{expected}/context",
                lambda data: self.got_context(data) if expected == self.ledger_id else None,
            )
        else:
            self.refresh_entry_actions()

    def got_context(self, data):
        self.context_data = data
        manager = bool(data["manager"])
        self.tabs.setTabEnabled(2, manager)
        self.tabs.setTabEnabled(3, manager)
        for combo in (self.category_filter, self.member_filter):
            combo.blockSignals(True)
            combo.clear()
        self.category_filter.addItem("全部类别", "")
        for category in data["categories"]:
            self.category_filter.addItem(category["name"], category["id"])
        self.member_filter.addItem("全部成员", "")
        for member in data["members"]:
            self.member_filter.addItem(member["name"], member["user_id"])
        for combo in (self.category_filter, self.member_filter):
            combo.blockSignals(False)
        fill(
            self.member_table,
            [
                [
                    m["name"],
                    m["username"],
                    Cell(
                        "账本管理员" if m["user_id"] == data["ledger"]["admin_id"] else "成员",
                        ACCENT if m["user_id"] == data["ledger"]["admin_id"] else INK,
                    ),
                    "在账本" if m["active"] else "已退出",
                    beijing(m["joined"]),
                ]
                for m in data["members"]
            ],
        )
        self.fill_people(data["members"])
        self.load_entries()
        self.refresh_entry_actions()
        if manager:
            self.load_finance()
            self.load_logs()

    def fill_people(self, members):
        active = {m["user_id"] for m in members if m["active"]}
        self.people.clear()
        for person in self.state.get("users", []):
            if person["id"] not in active:
                self.people.addItem(f"{person['name']}（{person['username']}）", person["id"])
        self.invite_button.setEnabled(self.people.count() > 0 and bool(self.ledger_id))

    # ---------------------------------------------------------------- entries

    def load_entries(self):
        if not self.ledger_id:
            return
        params = {
            "status": self.status_filter.currentData(),
            "start": date_text(self.start),
            "end": date_text(self.end),
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
        rows = []
        for item in data:
            income = item["direction"] == "INCOME"
            color = INCOME if income else INK
            rows.append(
                [
                    item["occurred"],
                    Cell(direction_label(item["direction"]), INCOME if income else EXPENSE),
                    Cell(
                        ("+" if income else "-") + yuan(item["amount"]),
                        color,
                        bold=True,
                        align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    ),
                    item["category"],
                    item["submitter"],
                    Cell(STATUS[item["status"]], STATUS_COLORS[item["status"]]),
                    item["note"],
                ]
            )
        fill(self.entry_table, rows)
        self.entry_count.setText(f"共 {len(data)} 笔")
        self.refresh_entry_actions()

    def selected_entry(self, quiet=False):
        index = self.entry_table.currentRow()
        if index < 0 or index >= len(self.entries):
            if not quiet:
                QMessageBox.information(self, "选择记录", "请先选择一条账目。")
            return None
        return self.entries[index]

    def selection_changed(self):
        self.refresh_entry_actions()

    def refresh_entry_actions(self):
        item = self.selected_entry(quiet=True)
        manager = bool(self.context_data.get("manager"))
        me = self.user_id
        approve = reject = withdraw = edit = detail = False
        self.pending_action = None
        hint = "选择一条记录后可查看详情或执行操作。"
        if item:
            detail = True
            status = item["status"]
            own = me in (item["submitter_id"], item["editor_id"])
            if status == "PENDING":
                approve = reject = manager and not own
                withdraw = manager
                edit = manager
                self.pending_action = "edit" if edit else None
                hint = "待审核：可通过、驳回，或由管理员修改后重新提交。"
                if manager and own:
                    hint = "待审核：本人提交的记录不能自行审核，可由另一位管理员处理。"
            elif status == "APPROVED":
                withdraw = manager
                edit = manager
                self.pending_action = "correct" if edit else None
                hint = "已审核：更正会撤回原记录并生成一条待审核新记录。"
            elif status == "REJECTED":
                edit = me in (item["submitter_id"], item["custodian_id"])
                self.pending_action = "resubmit" if edit else None
                hint = "已驳回：原提交人可修改后重新提交。"
            elif status == "WITHDRAWN":
                hint = "已撤回：终态记录，仅可查看详情。"
        self.detail_button.setEnabled(detail)
        self.edit_button.setEnabled(edit)
        self.edit_button.setText(EDIT_LABELS.get(self.pending_action, "修改"))
        self.withdraw_button.setEnabled(withdraw)
        self.reject_button.setEnabled(reject)
        self.approve_button.setEnabled(approve)
        self.entry_hint.setText(hint)

    def new_entry(self):
        if not self.context_data:
            return
        EntryDialog(
            self.client,
            self.ledger_id,
            self.context_data,
            self.load_ledger,
            self,
            user_id=self.user_id,
        ).exec()

    def edit_entry(self):
        item = self.selected_entry()
        if not item or not self.pending_action:
            return
        action = self.pending_action
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
                user_id=self.user_id,
            ).exec(),
        )

    def entry_detail(self, *args):
        item = self.selected_entry()
        if item:
            self.client.request(
                "GET",
                "/entries/" + item["id"],
                lambda data: EntryDetailDialog(self, data).exec(),
            )

    def entry_action(self, action):
        item = self.selected_entry()
        if not item:
            return
        reason = ""
        if action != "approve":
            reason = TextPrompt.ask(
                self,
                "填写原因",
                {"withdraw": "撤回原因", "reject": "驳回原因"}.get(action, "操作原因"),
                placeholder="请简要说明原因",
            )
            if reason is None:
                return
        if not confirm(
            self, f"确认对 {yuan(item['amount'])} 的记录执行「{ACTION_LABELS[action]}」？"
        ):
            return
        self.client.request(
            "POST",
            "/entries/" + item["id"],
            lambda _: self.load_ledger(),
            {"action": action, "version": item["version"], "reason": reason},
        )

    # ---------------------------------------------------------------- members

    def create_ledger(self):
        name = TextPrompt.ask(self, "新建账本", "账本名称", placeholder="例如：项目协作账本")
        if name:
            self.client.request("POST", "/ledgers", lambda _: self.refresh(), {"name": name})

    def invite(self):
        if not self.ledger_id or not self.people.currentData():
            return
        target = self.people.currentData()
        self.client.request(
            "POST",
            f"/ledgers/{self.ledger_id}/invite",
            lambda _: self.invitation_sent(),
            {"target": target},
        )

    def invitation_sent(self):
        QMessageBox.information(self, "邀请已发送", "请受邀人登录后在「邀请管理」中确认加入。")
        self.load_ledger()

    def invitation_manager(self):
        InvitationDialog(self.client, self.ledger_id, self.refresh, self).exec()

    def member_action(self, action):
        if not self.context_data:
            return
        if action == "leave":
            target = self.user_id
        else:
            index = self.member_table.currentRow()
            if index < 0:
                return
            target = self.context_data["members"][index]["user_id"]
        custodian = None
        if action != "transfer":
            custodian = self.choose_custodian()
            if custodian is None:
                return
        if confirm(self, "确认变更成员权限？变更立即生效，历史记录保留。"):
            self.client.request(
                "POST",
                f"/ledgers/{self.ledger_id}/members",
                lambda _: self.refresh(),
                {"target": target, "action": action, "custodian": custodian},
            )

    def choose_custodian(self):
        people = [user for user in self.state.get("users", []) if user["super"]]
        if not people:
            return None
        if len(people) == 1:
            return people[0]["id"]
        options = [(f"{user['name']}（{user['username']}）", user["id"]) for user in people]
        return ChoicePrompt.ask(
            self,
            "选择历史接管人",
            "退出后历史记录仍归属原提交人，由所选超级管理员接管后续处理。",
            options,
        )

    # ---------------------------------------------------------------- finance

    def load_finance(self):
        if not self.ledger_id:
            return
        expected = self.ledger_id
        start = self.finance_start.date().toString("yyyy-MM-dd")
        end = self.finance_end.date().toString("yyyy-MM-dd")
        self.client.request(
            "GET",
            f"/ledgers/{expected}/finance",
            lambda data: self.got_finance(data) if expected == self.ledger_id else None,
            params={"start": start, "end": end},
        )
        self.client.request(
            "GET",
            f"/ledgers/{expected}/records/snapshots",
            lambda data: self.got_snapshots(data) if expected == self.ledger_id else None,
        )

    def got_finance(self, data):
        self.stat_income.show_value(yuan(data["income"]), INCOME)
        self.stat_expense.show_value(yuan(data["expense"]), EXPENSE)
        self.stat_profit.show_value(yuan(data["profit"]), OK if data["profit"] >= 0 else DANGER)
        month = date.today().strftime("%Y-%m")
        budget = next((b for b in data["budgets"] if b["month"] == month), None)
        if budget:
            self.stat_budget.show_value(
                yuan(budget["available"]), OK if budget["available"] >= 0 else DANGER
            )
        else:
            self.stat_budget.show_value("未设置", MUTED)
        fill(
            self.category_stats,
            [
                [
                    name,
                    Cell(yuan(values["income"]), INCOME),
                    Cell(yuan(values["expense"]), EXPENSE),
                ]
                for name, values in data["categories"].items()
            ],
        )
        fill(
            self.member_stats,
            [
                [
                    values["name"],
                    Cell(yuan(values["income"]), INCOME),
                    Cell(yuan(values["expense"]), EXPENSE),
                ]
                for values in data["members"].values()
            ],
        )
        self.budgets = data["budgets"]
        rows = []
        for item in self.budgets:
            available = item["available"]
            rows.append(
                [
                    item["month"],
                    yuan(item["amount"]),
                    Cell(
                        yuan(available) + ("  超预算" if available < 0 else ""),
                        DANGER if available < 0 else OK,
                    ),
                    str(item["version"]),
                ]
            )
        fill(self.budget_table, rows)

    def got_snapshots(self, data):
        self.snapshots = data

        def span(item):
            start, end = item["start"], item["end"]
            if start[:4] == end[:4]:
                return start[5:] + " ～ " + end[5:]
            return start + " ～ " + end

        fill(
            self.snapshot_table,
            [
                [
                    beijing(item["created"]),
                    span(item),
                    yuan(int(item["income"])),
                    yuan(int(item["expense"])),
                    Cell(
                        "来源已变化" if item["stale"] else "当前",
                        WARN if item["stale"] else OK,
                    ),
                ]
                for item in data
            ],
        )

    def budget(self):
        if not self.ledger_id:
            return
        BudgetDialog(self.client, self.ledger_id, self.budgets, self.load_finance, self).exec()

    def settle(self):
        if self.ledger_id and confirm(self, "保存当前区间的结算快照？此操作不会清零或转账。"):
            start = self.finance_start.date().toString("yyyy-MM-dd")
            end = self.finance_end.date().toString("yyyy-MM-dd")
            self.client.request(
                "POST",
                f"/ledgers/{self.ledger_id}/settle",
                lambda _: self.load_finance(),
                {"start": start, "end": end},
            )

    def snapshot_detail(self):
        index = self.snapshot_table.currentRow()
        if index < 0 or index >= len(self.snapshots):
            QMessageBox.information(self, "选择快照", "请先在列表中选择一份结算快照。")
            return
        SnapshotDialog(self, self.snapshots[index]).exec()

    # ------------------------------------------------------------------ audit

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
        query = self.log_filter.text().strip().lower()
        self.filtered_logs = [
            item
            for item in self.logs
            if not query
            or query
            in " ".join(str(item[key]) for key in ("actor", "action", "target", "created")).lower()
        ]
        fill(
            self.log_table,
            [
                [
                    beijing(item["created"]),
                    item["actor"],
                    action_label(item["action"]),
                    short_id(item["target"]),
                ]
                for item in self.filtered_logs
            ],
        )

    def log_detail(self):
        index = self.log_table.currentRow()
        if index < 0 or index >= len(self.filtered_logs):
            QMessageBox.information(self, "选择日志", "请先选择一条操作日志。")
            return
        LogDetailDialog(self, self.filtered_logs[index]).exec()

    # ------------------------------------------------------------------ login

    def switch_user(self):
        if not confirm(self, "退出当前账号并切换登录？"):
            return

        def logged_out(_):
            self.client.token = ""
            self.hide()
            login = LoginDialog(self.client, self)
            if login.exec() == QDialog.DialogCode.Accepted:
                self.clear_views()
                self.refresh()
                self.show()
            else:
                self.close()

        self.client.request("POST", "/logout", logged_out)


def main():
    app = QApplication(sys.argv)
    configure_fonts(app)
    app.setStyleSheet(STYLE)
    from PySide6.QtCore import QThreadPool

    app.aboutToQuit.connect(lambda: QThreadPool.globalInstance().waitForDone())
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
