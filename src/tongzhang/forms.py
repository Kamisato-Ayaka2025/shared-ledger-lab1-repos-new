"""Dialogs: entry form, read-only detail views, budget and invitation management."""

import json
import uuid
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .widgets import (
    DANGER,
    EXPENSE,
    INCOME,
    INK,
    MUTED,
    OK,
    STATUS,
    STATUS_COLORS,
    WARN,
    Card,
    Cell,
    action_label,
    amount_text,
    beijing,
    cents_of,
    confirm,
    date_field,
    direction_label,
    fill,
    fit_table,
    month_field,
    month_text,
    new_button,
    short_id,
    size_to_content,
    table,
    yuan,
)

HEADINGS = {
    None: ("新增账目", "填写金额并分配成员后提交，新记录会进入待审核。"),
    "edit": ("修改待审账目", "保存后记录仍处于待审核状态。"),
    "resubmit": ("驳回重交", "修改被驳回的账目后重新提交审核。"),
    "correct": ("更正已审核账目", "原记录将撤回，并生成一条待审核的新记录。"),
}


def dialog_buttons(dialog, save_text="保存"):
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.button(QDialogButtonBox.StandardButton.Save).setText(save_text)
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
    buttons.button(QDialogButtonBox.StandardButton.Save).setProperty("primary", True)
    for standard in ("Save", "Cancel"):
        buttons.button(getattr(QDialogButtonBox.StandardButton, standard)).setCursor(
            Qt.CursorShape.PointingHandCursor
        )
    return buttons


class EntryDialog(QDialog):
    """Entry form that keeps valid input when validation fails."""

    def __init__(
        self,
        client,
        ledger_id,
        context,
        on_done,
        parent=None,
        entry=None,
        action=None,
        user_id="",
    ):
        super().__init__(parent)
        self.client, self.ledger_id, self.context = client, ledger_id, context
        self.on_done, self.entry, self.action = on_done, entry, action
        self.user_id = user_id
        self.request_key = str(uuid.uuid4())
        heading, subtitle = HEADINGS.get(action, HEADINGS[None])
        self.setWindowTitle(heading)
        self.setMinimumWidth(580)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        title = QLabel(heading)
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        note = QLabel(subtitle)
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.direction = QComboBox()
        self.direction.addItem("支出", "EXPENSE")
        self.direction.addItem("收入", "INCOME")
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("例如 120.50")
        self.category = QComboBox()
        self.occurred = date_field()
        self.note = QLineEdit()
        self.note.setPlaceholderText("可选，例如用途说明")
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("请说明修改原因")
        form.addRow("收支方向", self.direction)
        form.addRow("金额（元）", self.amount)
        form.addRow("类别", self.category)
        form.addRow("业务日期", self.occurred)
        form.addRow("备注", self.note)
        if entry:
            form.addRow("修改原因", self.reason)
        layout.addLayout(form)

        allocation = Card("成员分配", "合计须等于金额")
        helpers = QHBoxLayout()
        helpers.setSpacing(6)
        helpers.addWidget(new_button("记在我名下", self.all_to_me, ghost=True))
        helpers.addWidget(new_button("平均分配", self.split_evenly, ghost=True))
        helpers.addWidget(new_button("清空", self.clear_allocations, ghost=True))
        helpers.addStretch()
        allocation.add_layout(helpers)
        self.members = [m for m in context["members"] if m["active"]]
        self.allocations = QTableWidget(0, 2)
        self.allocations.setHorizontalHeaderLabels(["成员", "分配金额（元）"])
        self.allocations.horizontalHeaderItem(1).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.allocations.verticalHeader().hide()
        self.allocations.setShowGrid(False)
        self.allocations.setAlternatingRowColors(True)
        self.allocations.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.allocations.verticalHeader().setDefaultSectionSize(32)
        header = self.allocations.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.allocations.setColumnWidth(1, 170)
        self.allocations.setRowCount(len(self.members))
        for index, member in enumerate(self.members):
            name = member["name"] + ("（我）" if member["user_id"] == self.user_id else "")
            item = QTableWidgetItem(name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.allocations.setItem(index, 0, item)
            self.allocations.setItem(index, 1, QTableWidgetItem(""))
            self.allocations.item(index, 1).setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        self.allocations.setMinimumHeight(120)
        fit_table(self.allocations, len(self.members))
        allocation.add(self.allocations)
        self.allocation_hint = QLabel("")
        self.allocation_hint.setObjectName("muted")
        allocation.add(self.allocation_hint)
        layout.addWidget(allocation, 1)

        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color:{DANGER};")
        layout.addWidget(self.error)

        self.buttons = dialog_buttons(self, "保存")
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        client.busy.connect(self.buttons.setDisabled)
        layout.addWidget(self.buttons)

        self.direction.currentIndexChanged.connect(self.categories)
        self.amount.textChanged.connect(self.update_allocation_hint)
        self.allocations.itemChanged.connect(self.update_allocation_hint)
        self.categories()
        if entry:
            self.direction.setCurrentIndex(self.direction.findData(entry["direction"]))
            self.category.setCurrentIndex(self.category.findData(entry["category_id"]))
            self.amount.setText(amount_text(entry["amount"]))
            self.occurred.setDate(QDate.fromString(entry["occurred"], "yyyy-MM-dd"))
            self.note.setText(entry["note"])
            allocations = {p["user_id"]: p["amount"] for p in entry["participants"]}
            for index, member in enumerate(self.members):
                if member["user_id"] in allocations:
                    self.allocations.item(index, 1).setText(
                        amount_text(allocations[member["user_id"]])
                    )
        self.update_allocation_hint()
        size_to_content(self, 580)
        self.amount.setFocus()

    def categories(self):
        self.category.clear()
        for item in self.context["categories"]:
            if item["direction"] == self.direction.currentData():
                self.category.addItem(item["name"], item["id"])

    def clear_allocations(self):
        for index in range(len(self.members)):
            self.allocations.item(index, 1).setText("")

    def all_to_me(self):
        amount = cents_of(self.amount.text())
        if amount is None:
            self.amount.setFocus()
            return
        self.clear_allocations()
        for index, member in enumerate(self.members):
            if member["user_id"] == self.user_id:
                self.allocations.item(index, 1).setText(amount_text(amount))
                return

    def split_evenly(self):
        amount = cents_of(self.amount.text())
        if amount is None or not self.members:
            self.amount.setFocus()
            return
        self.clear_allocations()
        base, remainder = divmod(amount, len(self.members))
        for index, _member in enumerate(self.members):
            value = base + (1 if index < remainder else 0)
            if value:
                self.allocations.item(index, 1).setText(amount_text(value))

    def allocation_total(self):
        total = 0
        for index in range(len(self.members)):
            text = self.allocations.item(index, 1).text().strip()
            if not text:
                continue
            value = cents_of(text)
            if value is None:
                return None
            total += value
        return total

    def update_allocation_hint(self):
        amount = cents_of(self.amount.text())
        total = self.allocation_total()
        if total is None:
            self.allocation_hint.setText("分配金额需为数字，例如 100 或 100.50。")
            self.allocation_hint.setStyleSheet(f"color:{WARN};")
        elif amount is None or amount <= 0:
            self.allocation_hint.setText("填写金额后，可用上方快捷按钮分配。")
            self.allocation_hint.setStyleSheet(f"color:{MUTED};")
        elif total == 0:
            self.allocation_hint.setText("尚未分配金额，保存前需完成分配。")
            self.allocation_hint.setStyleSheet(f"color:{WARN};")
        elif total == amount:
            self.allocation_hint.setText(f"已分配 {yuan(total)}，与金额一致。")
            self.allocation_hint.setStyleSheet(f"color:{OK};")
        elif total < amount:
            self.allocation_hint.setText(f"已分配 {yuan(total)}，还差 {yuan(amount - total)}。")
            self.allocation_hint.setStyleSheet(f"color:{WARN};")
        else:
            self.allocation_hint.setText(f"已分配 {yuan(total)}，超出 {yuan(total - amount)}。")
            self.allocation_hint.setStyleSheet(f"color:{DANGER};")

    def save(self):
        amount = cents_of(self.amount.text())
        if amount is None or amount <= 0:
            self.error.setText("请填写大于零的金额，例如 120.50。")
            self.amount.setFocus()
            return
        participants = []
        for index, member in enumerate(self.members):
            value = self.allocations.item(index, 1).text().strip()
            if value:
                participants.append({"user_id": member["user_id"], "amount": value})
        if not participants:
            self.error.setText("请至少为一位成员填写分配金额。")
            return
        total = self.allocation_total()
        if total != amount:
            self.error.setText("成员分配金额合计必须等于账目金额。")
            return
        self.error.setText("")
        data = {
            "direction": self.direction.currentData(),
            "amount": self.amount.text().strip(),
            "category_id": self.category.currentData(),
            "occurred": self.occurred.date().toString("yyyy-MM-dd"),
            "note": self.note.text(),
            "participants": participants,
        }
        if self.entry:
            path = "/entries/" + self.entry["id"]
            body = {
                "data": data,
                "action": self.action,
                "version": self.entry["version"],
                "reason": self.reason.text(),
            }
        else:
            path = f"/ledgers/{self.ledger_id}/entries"
            body = {"data": data, "key": self.request_key}
        self.client.request("POST", path, self.saved, body)

    def saved(self, data):
        self.on_done()
        self.accept()


def status_chip(status):
    label = QLabel(STATUS.get(status, status))
    label.setStyleSheet(
        f"color:{STATUS_COLORS.get(status, MUTED)};"
        "background:rgba(0,0,0,0);"
        "font-weight:600;"
        "font-size:13px;"
    )
    return label


def entry_rows(item):
    return [
        ("方向", direction_label(item.get("direction"))),
        ("金额", yuan(item.get("amount", 0))),
        ("状态", STATUS.get(item.get("status"), str(item.get("status", "")))),
        ("业务日期", str(item.get("occurred", ""))),
        ("备注", str(item.get("note", ""))),
    ]


class EntryDetailDialog(QDialog):
    """Human readable entry detail instead of a raw JSON dump."""

    def __init__(self, parent, item):
        super().__init__(parent)
        self.setWindowTitle("账目详情")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        head = QHBoxLayout()
        heading = QLabel(f"{direction_label(item['direction'])} {yuan(item['amount'])}")
        heading.setObjectName("dialogTitle")
        head.addWidget(heading)
        head.addWidget(status_chip(item["status"]))
        head.addStretch()
        hint = QLabel(f"版本 {item['version']} · 提交人 {item['submitter']}")
        hint.setObjectName("muted")
        head.addWidget(hint)
        layout.addLayout(head)

        meta = QFormLayout()
        meta.setSpacing(8)
        meta.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        meta.addRow("类别", QLabel(str(item["category"])))
        meta.addRow("业务日期", QLabel(str(item["occurred"])))
        meta.addRow("备注", QLabel(str(item["note"]) or "（无）"))
        layout.addLayout(meta)

        allocation = Card("成员分配")
        self.allocation_table = table(
            ["成员", "金额"],
            [0, 160],
            aligns=[None, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter],
        )
        fill(
            self.allocation_table,
            [
                [p["name"], Cell(yuan(p["amount"]), align=Qt.AlignmentFlag.AlignRight)]
                for p in item["participants"]
            ],
        )
        fit_table(self.allocation_table, len(item["participants"]))
        allocation.add(self.allocation_table)
        layout.addWidget(allocation)

        history = Card("历史版本")
        self.history_table = table(
            ["版本", "金额", "时间", "操作人", "原因"], [60, 110, 150, 100, 0]
        )
        rows = []
        for revision in item.get("history", []):
            try:
                snapshot = json.loads(revision["data"])
            except (TypeError, ValueError):
                snapshot = {}
            rows.append(
                [
                    str(revision["version"]),
                    yuan(snapshot.get("amount", 0)),
                    beijing(revision["created"]),
                    str(revision["actor"]),
                    str(revision["reason"]),
                ]
            )
        fill(self.history_table, rows)
        fit_table(self.history_table, len(rows), 190)
        history.add(self.history_table)
        layout.addWidget(history)

        reviews = Card("审核记录")
        review_rows = [
            [
                beijing(review["created"]),
                str(review["actor"]),
                STATUS.get(review["decision"], str(review["decision"])),
                str(review["reason"]),
            ]
            for review in item.get("reviews", [])
        ]
        if review_rows:
            self.review_table = table(["时间", "审核人", "结果", "原因"], [150, 110, 90, 0])
            fill(self.review_table, review_rows)
            fit_table(self.review_table, len(review_rows), 150)
            reviews.add(self.review_table)
        else:
            reviews.add(self.muted_text("该记录暂无审核操作。"))
        layout.addWidget(reviews)
        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        size_to_content(self, 700)

    def muted_text(self, text):
        label = QLabel(text)
        label.setObjectName("muted")
        return label


class SnapshotDialog(QDialog):
    """Readable settlement snapshot instead of raw JSON."""

    def __init__(self, parent, snapshot):
        super().__init__(parent)
        try:
            data = json.loads(snapshot["data"])
        except (TypeError, ValueError):
            data = {}
        self.setWindowTitle("结算快照来源")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        heading = QLabel(f"结算区间 {snapshot['start']} ～ {snapshot['end']}")
        heading.setObjectName("dialogTitle")
        layout.addWidget(heading)
        hint = QLabel(
            f"保存于 {beijing(snapshot['created'])} · 来源账本版本 {snapshot['revision']} · "
            + ("来源已变化，快照数值保持不变" if snapshot.get("stale") else "当前")
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        summary = QHBoxLayout()
        summary.setSpacing(24)
        for title, value, color in (
            ("收入", yuan(data.get("income", 0)), INCOME),
            ("支出", yuan(data.get("expense", 0)), EXPENSE),
            ("盈亏", yuan(data.get("profit", 0)), INK),
        ):
            block = QVBoxLayout()
            block.setSpacing(2)
            caption = QLabel(title)
            caption.setObjectName("muted")
            amount = QLabel(value)
            amount.setStyleSheet(f"font-size:18px;font-weight:700;color:{color};")
            block.addWidget(caption)
            block.addWidget(amount)
            summary.addLayout(block)
        summary.addStretch()
        layout.addLayout(summary)

        card = Card("纳入统计的已审核记录")
        self.items_table = table(["日期", "方向", "金额", "类别", "备注"], [100, 60, 110, 90, 0])
        items = data.get("items", [])
        fill(
            self.items_table,
            [
                [
                    str(item.get("occurred", "")),
                    direction_label(item.get("direction")),
                    Cell(yuan(item.get("amount", 0)), align=Qt.AlignmentFlag.AlignRight),
                    str(item.get("category", "")),
                    str(item.get("note", "")),
                ]
                for item in items
            ],
        )
        fit_table(self.items_table, len(items), 280)
        card.add(self.items_table)
        layout.addWidget(card)
        layout.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        size_to_content(self, 720, 700)


LOG_LABELS = {
    "name": "账本名称",
    "target": "对象",
    "amount": "期初预算",
    "reason": "原因",
    "start": "开始日期",
    "end": "结束日期",
    "status": "状态",
    "custodian": "接管人",
    "previous_admin": "原管理员",
    "result_id": "生成记录",
    "ledger": "账本",
    "invitation": "邀请",
}


def plain_value(key, value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if key in ("custodian", "previous_admin", "target", "result_id", "ledger"):
        return short_id(value)
    if key == "amount" and isinstance(value, int):
        return yuan(value)
    if key == "status":
        return action_label(STATUS.get(str(value), str(value)))
    if isinstance(value, (dict, list)):
        return ""
    return str(value)


class LogDetailDialog(QDialog):
    """Readable audit detail: field level before/after instead of raw JSON."""

    def __init__(self, parent, entry):
        super().__init__(parent)
        try:
            data = json.loads(entry.get("data") or "{}")
        except (TypeError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {"数据": data}
        self.setWindowTitle("操作详情")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        heading = QLabel(action_label(entry["action"]))
        heading.setObjectName("dialogTitle")
        layout.addWidget(heading)
        meta = QLabel(
            f"{beijing(entry['created'])} · 操作者 {entry['actor']} · 对象 {short_id(entry['target'])}"
        )
        meta.setObjectName("muted")
        layout.addWidget(meta)
        reason = data.get("reason")
        if reason:
            note = QLabel(f"原因：{reason}")
            note.setObjectName("muted")
            note.setWordWrap(True)
            layout.addWidget(note)

        before, after = data.get("before"), data.get("after")
        card = Card("变更前后")
        self.compare_table = table(["项目", "修改前", "修改后"], [120, 0, 0])
        if isinstance(before, dict) and isinstance(after, dict):
            rows = [
                [old[0], old[1], Cell(new[1], bold=old[1] != new[1])]
                for old, new in zip(entry_rows(before), entry_rows(after))
            ]
        else:
            rows = []
            for key, value in data.items():
                if key in ("before", "after", "reason"):
                    continue
                label = LOG_LABELS.get(key, key)
                text = plain_value(key, value)
                if label and text:
                    rows.append([label, text, ""])
        fill(self.compare_table, rows)
        fit_table(self.compare_table, len(rows), 260)
        card.add(self.compare_table)
        layout.addWidget(card)
        layout.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        size_to_content(self, 660, 700)


class BudgetDialog(QDialog):
    """One dialog for month, amount and reason; replaces three chained prompts."""

    def __init__(self, client, ledger_id, budgets, on_done, parent=None):
        super().__init__(parent)
        self.client, self.ledger_id, self.budgets = client, ledger_id, budgets
        self.on_done = on_done
        self.setWindowTitle("设置月度预算")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        heading = QLabel("设置月度预算")
        heading.setObjectName("dialogTitle")
        layout.addWidget(heading)
        subtitle = QLabel("期初预算用于计算可用预算：期初预算 + 收入 - 支出。")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.month = month_field(date.today().strftime("%Y-%m"))
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("例如 5000")
        self.reason = QLineEdit("调整月度预算")
        self.reason.setPlaceholderText("请填写变更原因")
        form.addRow("预算月份", self.month)
        form.addRow("期初预算（元）", self.amount)
        form.addRow("变更原因", self.reason)
        layout.addLayout(form)
        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color:{DANGER};")
        layout.addWidget(self.error)
        self.buttons = dialog_buttons(self, "保存")
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        client.busy.connect(self.buttons.setDisabled)
        layout.addWidget(self.buttons)
        self.month.dateChanged.connect(self.sync_hint)
        self.sync_hint()
        self.amount.setFocus()

    def current_budget(self):
        month = month_text(self.month)
        return next((b for b in self.budgets if b["month"] == month), None)

    def sync_hint(self):
        existing = self.current_budget()
        if existing:
            self.hint.setText(
                f"该月已有期初预算 {yuan(existing['amount'])}，可用预算 {yuan(existing['available'])}，"
                f"版本 {existing['version']}。"
            )
            if not self.amount.text():
                self.amount.setText(amount_text(existing["amount"]))
        else:
            self.hint.setText("该月尚未设置预算。")
        self.error.setText("")

    def save(self):
        amount = cents_of(self.amount.text())
        if amount is None or amount < 0:
            self.error.setText("请填写有效的期初预算金额，例如 5000。")
            return
        reason = self.reason.text().strip()
        if not reason:
            self.error.setText("请填写变更原因。")
            return
        existing = self.current_budget()
        self.client.request(
            "POST",
            f"/ledgers/{self.ledger_id}/budget",
            self.saved,
            {
                "month": month_text(self.month),
                "amount": self.amount.text().strip(),
                "reason": reason,
                "version": existing["version"] if existing else 0,
            },
        )

    def saved(self, data):
        self.on_done()
        self.accept()


class InvitationDialog(QDialog):
    """Incoming invitations and pending sent invitations in one place."""

    def __init__(self, client, ledger_id, on_change, parent=None):
        super().__init__(parent)
        self.client, self.ledger_id, self.on_change = client, ledger_id, on_change
        self.mine = []
        self.sent = []
        self.setWindowTitle("邀请管理")
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        heading = QLabel("邀请管理")
        heading.setObjectName("dialogTitle")
        layout.addWidget(heading)

        incoming = Card("我收到的邀请", "确认后即加入对应账本，邀请七天内有效。")
        self.accept_button = incoming.add_button("接受邀请", self.accept_selected, primary=True)
        self.mine_table = table(["账本", "邀请人", "到期时间"], [0, 120, 150])
        self.mine_table.doubleClicked.connect(self.accept_selected)
        incoming.add(self.mine_table, 1)
        layout.addWidget(incoming, 1)

        outgoing = Card("本账本待处理的邀请", "撤销后受邀人将无法凭此邀请加入。")
        self.cancel_button = outgoing.add_button("撤销邀请", self.cancel_selected, danger=True)
        self.sent_table = table(["受邀人", "发出时间", "到期时间"], [0, 150, 150])
        outgoing.add(self.sent_table, 1)
        self.outgoing = outgoing
        layout.addWidget(outgoing, 1)

        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        layout.addWidget(self.hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.load()

    def load(self):
        self.client.request("GET", "/bootstrap", self.got_mine)
        if self.ledger_id:
            self.client.request(
                "GET", f"/ledgers/{self.ledger_id}/records/invitations", self.got_sent
            )

    def got_mine(self, data):
        self.mine = data.get("invitations", [])
        fill(
            self.mine_table,
            [[i["ledger_name"], i["inviter"], beijing(i["expires"])] for i in self.mine],
        )
        if self.mine:
            self.mine_table.selectRow(0)
        self.sync()

    def got_sent(self, data):
        self.sent = [item for item in data if item["status"] == "PENDING"]
        fill(
            self.sent_table,
            [[i["target"], beijing(i["created"]), beijing(i["expires"])] for i in self.sent],
        )
        if self.sent:
            self.sent_table.selectRow(0)
        self.sync()

    def sync(self):
        self.accept_button.setEnabled(bool(self.mine))
        self.cancel_button.setEnabled(bool(self.sent))
        if not self.ledger_id:
            self.outgoing.setVisible(False)
        total = len(self.mine)
        self.hint.setText(f"共有 {total} 条待处理邀请。" if total else "暂无待处理的邀请。")

    def accept_selected(self, *args):
        index = self.mine_table.currentRow()
        if index < 0 or index >= len(self.mine):
            return
        invitation = self.mine[index]
        self.client.request(
            "POST", "/invitations/" + invitation["id"], self.handled, {"action": "accept"}
        )

    def accept_first(self):
        self.mine_table.selectRow(0)
        self.accept_selected()

    def cancel_selected(self):
        index = self.sent_table.currentRow()
        if index < 0 or index >= len(self.sent):
            return
        if not confirm(self, "确认撤销该邀请？"):
            return
        invitation = self.sent[index]
        self.client.request(
            "POST", "/invitations/" + invitation["id"], self.handled, {"action": "cancel"}
        )

    def handled(self, data):
        self.on_change()
        self.load()
