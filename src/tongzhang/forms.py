"""Entry form preserves valid input when validation fails."""

import uuid
from datetime import date
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QDialogButtonBox,
    QLabel,
    QHeaderView,
)
from PySide6.QtCore import Qt
from .widgets import amount_text


class EntryDialog(QDialog):
    def __init__(self, client, ledger_id, context, refresh, parent=None, entry=None, action=None):
        super().__init__(parent)
        self.client, self.ledger_id, self.context = client, ledger_id, context
        self.refresh, self.entry, self.action = refresh, entry, action
        self.request_key = str(uuid.uuid4())
        self.setWindowTitle("新增收支" if not entry else "编辑账目 · " + action)
        self.resize(620, 660)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.direction = QComboBox()
        self.direction.addItem("支出", "EXPENSE")
        self.direction.addItem("收入", "INCOME")
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("例如 120.50")
        self.category = QComboBox()
        self.occurred = QLineEdit(date.today().isoformat())
        self.note = QTextEdit()
        self.note.setMaximumHeight(80)
        self.reason = QLineEdit()
        form.addRow("收支方向", self.direction)
        form.addRow("金额（元）", self.amount)
        form.addRow("类别", self.category)
        form.addRow("业务日期", self.occurred)
        form.addRow("备注", self.note)
        if entry:
            form.addRow("修改原因", self.reason)
        layout.addLayout(form)
        layout.addWidget(QLabel("涉及成员分配（填写金额表示参与；合计须等于总金额）"))
        self.allocations = QTableWidget(0, 2)
        self.allocations.setHorizontalHeaderLabels(["成员", "分配金额（元）"])
        self.allocations.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.members = [m for m in context["members"] if m["active"]]
        self.allocations.setRowCount(len(self.members))
        for index, member in enumerate(self.members):
            item = QTableWidgetItem(member["name"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.allocations.setItem(index, 0, item)
            self.allocations.setItem(index, 1, QTableWidgetItem(""))
        layout.addWidget(self.allocations)
        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color:#bd3c32")
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        client.busy.connect(self.buttons.setDisabled)
        layout.addWidget(self.buttons)
        self.direction.currentIndexChanged.connect(self.categories)
        self.categories()
        if entry:
            self.direction.setCurrentIndex(self.direction.findData(entry["direction"]))
            self.category.setCurrentIndex(self.category.findData(entry["category_id"]))
            self.amount.setText(amount_text(entry["amount"]))
            self.occurred.setText(entry["occurred"])
            self.note.setPlainText(entry["note"])
            allocations = {p["user_id"]: p["amount"] for p in entry["participants"]}
            for index, member in enumerate(self.members):
                if member["user_id"] in allocations:
                    self.allocations.item(index, 1).setText(
                        amount_text(allocations[member["user_id"]])
                    )

    def categories(self):
        self.category.clear()
        for item in self.context["categories"]:
            if item["direction"] == self.direction.currentData():
                self.category.addItem(item["name"], item["id"])

    def save(self):
        participants = []
        for index, member in enumerate(self.members):
            value = self.allocations.item(index, 1).text().strip()
            if value:
                participants.append({"user_id": member["user_id"], "amount": value})
        if not participants:
            self.error.setText("请至少为一位成员填写分配金额。")
            return
        data = {
            "direction": self.direction.currentData(),
            "amount": self.amount.text(),
            "category_id": self.category.currentData(),
            "occurred": self.occurred.text(),
            "note": self.note.toPlainText(),
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
        self.refresh()
        self.accept()
