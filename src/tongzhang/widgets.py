"""Reusable desktop controls and non-blocking HTTP transport."""

import json
import httpx
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
    QAbstractItemView,
    QTextEdit,
)


class Signals(QObject):
    done = Signal(object, object)


class RequestTask(QRunnable):
    def __init__(self, method, url, token, body, params):
        super().__init__()
        self.signals = Signals()
        self.method, self.url, self.token = method, url, token
        self.body, self.params = body, params

    def run(self):
        try:
            response = httpx.request(
                self.method,
                self.url,
                json=self.body,
                params=self.params,
                headers={"Authorization": "Bearer " + self.token} if self.token else {},
                timeout=15,
            )
            data = response.json()
            if response.is_error:
                detail = data.get("detail", "请求失败")
                if not isinstance(detail, str):
                    detail = "输入格式不正确，请检查所填内容"
                self.signals.done.emit(None, detail)
            else:
                self.signals.done.emit(data, None)
        except Exception as exc:
            self.signals.done.emit(None, "无法连接服务，请确认服务已启动。\n" + str(exc))


class Client(QObject):
    busy = Signal(bool)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.base = "http://127.0.0.1:8765"
        self.token = ""
        self.pending = set()

    def request(self, method, path, callback, body=None, params=None):
        task = RequestTask(method, self.base + path, self.token, body, params)
        self.pending.add(task)
        self.busy.emit(True)

        def finished(data, error):
            self.pending.discard(task)
            self.busy.emit(bool(self.pending))
            if error:
                self.error.emit(error)
            else:
                callback(data)

        task.signals.done.connect(finished)
        QThreadPool.globalInstance().start(task)


def currency(cents):
    sign = "-" if int(cents) < 0 else ""
    absolute = abs(int(cents))
    return f"{sign}{absolute // 100:,}.{absolute % 100:02d}"


def amount_text(cents):
    return currency(cents).replace(",", "")


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setAlternatingRowColors(True)
    widget.verticalHeader().hide()
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return widget


def fill(widget, data):
    widget.setRowCount(len(data))
    for r, values in enumerate(data):
        for col, value in enumerate(values):
            widget.setItem(r, col, QTableWidgetItem(str(value)))


def show_json(parent, title, data):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(820, 600)
    layout = QVBoxLayout(dialog)
    editor = QTextEdit()
    editor.setReadOnly(True)
    editor.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
    layout.addWidget(editor)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


class LoginDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.result_data = None
        self.setWindowTitle("登录 · 同账")
        self.setMinimumWidth(420)
        form = QFormLayout(self)
        heading = QLabel("同账\n让每一笔收支有据可查")
        heading.setObjectName("hero")
        form.addRow(heading)
        self.server = QLineEdit(client.base)
        self.username = QLineEdit("manager")
        self.password = QLineEdit("Demo123!")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("服务地址", self.server)
        form.addRow("账号", self.username)
        form.addRow("密码", self.password)
        form.addRow(QLabel("演示账号：manager / alice / bob / root\n演示密码：Demo123!"))
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("登录")
        self.buttons.accepted.connect(self.login)
        self.buttons.rejected.connect(self.reject)
        client.busy.connect(self.buttons.setDisabled)
        form.addRow(self.buttons)

    def login(self):
        self.client.base = self.server.text().rstrip("/")
        self.client.request(
            "POST",
            "/login",
            self.logged_in,
            {"username": self.username.text(), "password": self.password.text()},
        )

    def logged_in(self, data):
        self.client.token = data["token"]
        self.result_data = data
        self.accept()


def confirm(parent, message):
    return QMessageBox.question(parent, "确认操作", message) == QMessageBox.StandardButton.Yes
