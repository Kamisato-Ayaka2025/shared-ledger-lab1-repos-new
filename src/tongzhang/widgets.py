"""Shared desktop theme, reusable controls and non-blocking HTTP transport."""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx
from PySide6.QtCore import QDate, QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

ACCENT = "#0f766e"
INK = "#1f2d2a"
MUTED = "#7b8a86"
PAGE = "#f2f5f4"
OK = "#0b7a5c"
WARN = "#b45309"
DANGER = "#b23c2e"
INCOME = "#0b7a5c"
EXPENSE = "#465a55"

STATUS = {
    "PENDING": "待审核",
    "APPROVED": "已审核",
    "REJECTED": "已驳回",
    "WITHDRAWN": "已撤回",
}
STATUS_COLORS = {
    "PENDING": WARN,
    "APPROVED": OK,
    "REJECTED": DANGER,
    "WITHDRAWN": MUTED,
}
DIRECTIONS = {"INCOME": "收入", "EXPENSE": "支出"}
ACTION_TEXT = {
    "approve": "审核通过",
    "reject": "驳回",
    "withdraw": "撤回",
    "edit": "修改待审",
    "correct": "更正",
    "resubmit": "驳回重交",
    "ACCEPTED": "已接受",
    "CANCELLED": "已撤销",
}
BEIJING = timezone(timedelta(hours=8))
NO_DATE = QDate(2000, 1, 1)

STYLE = """
QWidget { font-family:'Microsoft YaHei'; font-size:13px; color:#1f2d2a; }
QMainWindow, QDialog { background:#f2f5f4; }
QLabel { background:transparent; }
QLabel#brand { font-size:20px; font-weight:700; color:#0f766e; }
QLabel#brandTag { color:#8a9893; font-size:12px; padding-top:5px; }
QLabel#loginBrand { font-size:30px; font-weight:700; color:#0f766e; }
QLabel#loginTag { color:#7b8a86; font-size:13px; }
QLabel#muted { color:#7b8a86; font-size:12px; }
QLabel#sectionTitle { font-size:14px; font-weight:600; color:#2c3b37; }
QLabel#dialogTitle { font-size:17px; font-weight:600; color:#2c3b37; }
QLabel#statTitle { color:#7b8a86; font-size:12px; }
QLabel#statValue { font-size:22px; font-weight:700; color:#1f2d2a; }
QLabel#identity { color:#3d4f4a; font-size:12px; background:#e9f2ef; border-radius:11px; padding:5px 12px; }
QLabel#notice { background:#fff7ea; border:1px solid #f0dcb8; border-radius:8px; color:#8a5a12; padding:9px 12px; }
QLabel#fieldLabel { color:#4b5b56; font-size:12px; }
QFrame#header { background:#ffffff; border-bottom:1px solid #e2e8e6; }
QFrame#card, QFrame#statCard { background:#ffffff; border:1px solid #e4eae8; border-radius:10px; }
QFrame#divider { background:#e2e8e6; min-width:1px; max-width:1px; }
QPushButton { background:#ffffff; color:#2c3b37; border:1px solid #cfdad6; border-radius:6px; padding:7px 14px; }
QPushButton:hover { background:#f4f8f7; border-color:#b6c7c1; }
QPushButton:pressed { background:#eef4f2; }
QPushButton:disabled { color:#9aa8a4; border-color:#e4eae8; background:#f7f9f8; }
QPushButton[primary="true"] { background:#0f766e; color:#ffffff; border:1px solid #0f766e; font-weight:600; }
QPushButton[primary="true"]:hover { background:#0c6459; border-color:#0c6459; }
QPushButton[primary="true"]:pressed { background:#0a5a51; }
QPushButton[primary="true"]:disabled { background:#a9c5be; border-color:#a9c5be; color:#f2f7f5; }
QPushButton[danger="true"] { color:#b23c2e; border-color:#e6cbc7; }
QPushButton[danger="true"]:hover { background:#fbf1f0; border-color:#dbb2ac; }
QPushButton[danger="true"]:disabled { color:#c9a7a2; }
QPushButton[ghost="true"] { background:transparent; border:0; color:#0f766e; padding:6px 8px; }
QPushButton[ghost="true"]:hover { background:#e9f2ef; }
QPushButton[ghost="true"]:disabled { color:#9aa8a4; background:transparent; }
QLineEdit, QComboBox, QDateEdit {
    background:#ffffff; border:1px solid #d3ded9; border-radius:6px; padding:6px 9px;
    min-height:20px; selection-background-color:#c7e6dd; selection-color:#10231f;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border-color:#0f766e; }
QLineEdit:disabled, QComboBox:disabled { background:#f4f7f6; color:#9aa8a4; }
QComboBox QAbstractItemView {
    background:#ffffff; border:1px solid #d3ded9; selection-background-color:#e3f1ec;
    selection-color:#10231f; outline:0; padding:4px;
}
QTableWidget {
    background:#ffffff; alternate-background-color:#f8fbfa; border:0;
    selection-background-color:#e3f1ec; selection-color:#10231f; outline:0;
}
QTableWidget::item { padding:2px 8px; }
QHeaderView::section {
    background:#f4f8f6; color:#6b7a76; border:0; border-bottom:1px solid #e4eae8;
    padding:8px; font-weight:600; font-size:12px;
}
QTableCornerButton::section { background:#f4f8f6; border:0; }
QTabWidget::pane { border:0; background:transparent; }
QTabBar { background:transparent; }
QTabBar::tab {
    background:transparent; color:#6b7a76; border:0; border-bottom:2px solid transparent;
    padding:10px 20px; margin-right:4px; font-size:14px;
}
QTabBar::tab:hover:!selected { color:#2c3b37; }
QTabBar::tab:selected { color:#0f766e; border-bottom:2px solid #0f766e; font-weight:600; }
QTabBar::tab:disabled { color:#b5c0bd; }
QStatusBar { background:#eaf1ee; color:#6b7a76; border-top:1px solid #dde6e2; }
QStatusBar::item { border:0; }
QScrollBar:vertical { background:transparent; width:10px; margin:2px; }
QScrollBar::handle:vertical { background:#cfdad6; border-radius:4px; min-height:24px; }
QScrollBar::handle:vertical:hover { background:#aebfb9; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
QScrollBar:horizontal { background:transparent; height:10px; margin:2px; }
QScrollBar::handle:horizontal { background:#cfdad6; border-radius:4px; min-width:24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background:transparent; }
QToolTip { background:#1f2d2a; color:#ffffff; border:0; padding:6px; }
QCalendarWidget QWidget { alternate-background-color:#f4f8f6; }
"""


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
        port = os.environ.get("TONGZHANG_PORT", "8765")
        self.base = os.environ.get("TONGZHANG_BASE", "http://127.0.0.1:" + port)
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


def yuan(cents):
    text = currency(cents)
    return "-¥" + text[1:] if text.startswith("-") else "¥" + text


def cents_of(value):
    """Parse a GUI amount into cents for inline hints; None when not a number."""
    try:
        number = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return int((number * 100).to_integral_value())


def direction_label(value):
    return DIRECTIONS.get(value, "")


def action_label(value):
    text = str(value or "")
    return ACTION_TEXT.get(text, text)


def beijing(value):
    """Render an ISO timestamp as Beijing time; plain business dates pass through."""
    text = str(value or "")
    if len(text) <= 10:
        return text
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return text
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M")


def short_id(value, size=8):
    text = str(value or "")
    return text[:size] if len(text) > size else text


def date_field(value="", allow_empty=False):
    field = QDateEdit()
    field.setCalendarPopup(True)
    field.setDisplayFormat("yyyy-MM-dd")
    field.setMinimumDate(NO_DATE)
    parsed = QDate.fromString(str(value or ""), "yyyy-MM-dd")
    if allow_empty:
        field.setSpecialValueText("不限")
        field.setDate(parsed if parsed.isValid() else NO_DATE)
    else:
        field.setDate(parsed if parsed.isValid() else QDate.currentDate())
    field.setMinimumWidth(118)
    return field


def date_text(field):
    if field.specialValueText() and field.date() == field.minimumDate():
        return ""
    return field.date().toString("yyyy-MM-dd")


def month_field(value=""):
    field = QDateEdit()
    field.setCalendarPopup(True)
    field.setDisplayFormat("yyyy-MM")
    field.setMinimumDate(QDate(2000, 1, 1))
    parsed = QDate.fromString(str(value or "") + "-01", "yyyy-MM-dd")
    field.setDate(parsed if parsed.isValid() else QDate.currentDate())
    field.setMinimumWidth(118)
    return field


def month_text(field):
    return field.date().toString("yyyy-MM")


@dataclass
class Cell:
    text: str
    color: str = ""
    bold: bool = False
    align: Qt.AlignmentFlag | None = None


def table(headers, widths=None, aligns=None):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setAlternatingRowColors(True)
    widget.setShowGrid(False)
    widget.verticalHeader().hide()
    widget.verticalHeader().setDefaultSectionSize(34)
    header = widget.horizontalHeader()
    header.setHighlightSections(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    if widths:
        for index, width in enumerate(widths):
            if width:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
                widget.setColumnWidth(index, width)
            else:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
    else:
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    for index, align in enumerate(aligns or []):
        item = widget.horizontalHeaderItem(index)
        if item is not None and align is not None:
            item.setTextAlignment(align)
    return widget


def fit_table(widget, rows, maximum=240):
    """Keep short tables compact so dialogs do not show empty white bands."""
    widget.setFixedHeight(min(38 + 34 * max(int(rows), 1), maximum))


def size_to_content(dialog, width, max_height=780):
    """Size a dialog to its content instead of leaving empty space."""
    dialog.setFixedWidth(width)
    dialog.adjustSize()
    dialog.resize(width, min(dialog.height(), max_height))


def fill(widget, data):
    widget.setRowCount(len(data))
    for row, values in enumerate(data):
        for column, value in enumerate(values):
            cell = value if isinstance(value, Cell) else Cell(str(value))
            item = QTableWidgetItem(cell.text)
            if cell.color:
                item.setForeground(QColor(cell.color))
            if cell.bold:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            if cell.align is not None:
                item.setTextAlignment(cell.align)
            widget.setItem(row, column, item)
    widget.clearSelection()


def new_button(text, callback=None, primary=False, danger=False, ghost=False):
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        button.setProperty("primary", True)
    if danger:
        button.setProperty("danger", True)
    if ghost:
        button.setProperty("ghost", True)
    if callback is not None:
        button.clicked.connect(callback)
    return button


class Card(QFrame):
    """White rounded container with an optional title row that hosts actions."""

    def __init__(self, title="", hint="", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 16)
        self.body.setSpacing(10)
        self.head = QHBoxLayout()
        self.head.setSpacing(8)
        if title:
            label = QLabel(title)
            label.setObjectName("sectionTitle")
            self.head.addWidget(label)
        if hint:
            note = QLabel(hint)
            note.setObjectName("muted")
            self.head.addWidget(note)
        self.head.addStretch()
        self.body.addLayout(self.head)

    def add(self, widget, stretch=0):
        self.body.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout):
        self.body.addLayout(layout)
        return layout

    def add_button(self, text, callback, primary=False, danger=False, ghost=False):
        button = new_button(text, callback, primary, danger, ghost)
        self.head.addWidget(button)
        return button


class StatCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 13, 16, 14)
        layout.setSpacing(4)
        caption = QLabel(title)
        caption.setObjectName("statTitle")
        self.value = QLabel("—")
        self.value.setObjectName("statValue")
        layout.addWidget(caption)
        layout.addWidget(self.value)

    def show_value(self, text, color=INK):
        self.value.setText(text)
        self.value.setStyleSheet(f"color:{color};")


class TextPrompt(QDialog):
    """Single field dialog used instead of the native QInputDialog."""

    def __init__(self, parent, title, label, default="", placeholder=""):
        super().__init__(parent)
        self.value = None
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        heading = QLabel(label)
        heading.setObjectName("fieldLabel")
        layout.addWidget(heading)
        self.field = QLineEdit(default)
        self.field.setPlaceholderText(placeholder)
        self.field.returnPressed.connect(self.accept_value)
        layout.addWidget(self.field)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        for name in ("Ok", "Cancel"):
            button = self.buttons.button(getattr(QDialogButtonBox.StandardButton, name))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setProperty("primary", True)
        self.buttons.accepted.connect(self.accept_value)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def accept_value(self):
        text = self.field.text().strip()
        if not text:
            self.field.setFocus()
            return
        self.value = text
        self.accept()

    @classmethod
    def ask(cls, parent, title, label, default="", placeholder=""):
        dialog = cls(parent, title, label, default, placeholder)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.value
        return None


class ChoicePrompt(QDialog):
    """Pick one option from a labelled combo box."""

    def __init__(self, parent, title, label, options, hint=""):
        super().__init__(parent)
        self.choice = None
        self.options = options
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        heading = QLabel(label)
        heading.setObjectName("fieldLabel")
        layout.addWidget(heading)
        self.combo = QComboBox()
        for text, value in options:
            self.combo.addItem(text, value)
        layout.addWidget(self.combo)
        if hint:
            note = QLabel(hint)
            note.setObjectName("muted")
            note.setWordWrap(True)
            layout.addWidget(note)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setProperty("primary", True)
        self.buttons.accepted.connect(self.accept_choice)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def accept_choice(self):
        self.choice = self.combo.currentData()
        self.accept()

    @classmethod
    def ask(cls, parent, title, label, options, hint=""):
        dialog = cls(parent, title, label, options, hint)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.choice
        return None


class LoginDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.result_data = None
        self.setWindowTitle("登录 · 同账")
        self.setFixedWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 26)
        layout.setSpacing(6)
        brand = QLabel("同账")
        brand.setObjectName("loginBrand")
        layout.addWidget(brand)
        tagline = QLabel("多人共享记账 · 让每一笔收支有据可查")
        tagline.setObjectName("loginTag")
        layout.addWidget(tagline)
        layout.addSpacing(18)
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.server = QLineEdit(client.base)
        self.username = QLineEdit("manager")
        self.password = QLineEdit("Demo123!")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("服务地址", self.server)
        form.addRow("账号", self.username)
        form.addRow("密码", self.password)
        layout.addLayout(form)
        layout.addSpacing(8)
        hint = QLabel("演示账号 manager / alice / bob / root · 密码 Demo123!")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addSpacing(10)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("登录")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setProperty("primary", True)
        self.buttons.accepted.connect(self.login)
        self.buttons.rejected.connect(self.reject)
        client.busy.connect(self.buttons.setDisabled)
        layout.addWidget(self.buttons)

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


def configure_fonts(app):
    from .branding import configure_identity

    configure_identity(app)
    from pathlib import Path

    from PySide6.QtGui import QFont, QFontDatabase, QPalette

    app.setStyle("Fusion")
    palette = app.palette()
    for role, color in (
        (QPalette.ColorRole.Window, PAGE),
        (QPalette.ColorRole.WindowText, INK),
        (QPalette.ColorRole.Base, "#ffffff"),
        (QPalette.ColorRole.AlternateBase, "#f8fbfa"),
        (QPalette.ColorRole.Text, INK),
        (QPalette.ColorRole.Button, "#ffffff"),
        (QPalette.ColorRole.ButtonText, INK),
        (QPalette.ColorRole.Highlight, "#c7e6dd"),
        (QPalette.ColorRole.HighlightedText, "#10231f"),
        (QPalette.ColorRole.PlaceholderText, "#9aa8a4"),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    font = Path("C:/Windows/Fonts/msyh.ttc")
    if font.exists():
        font_id = QFontDatabase.addApplicationFont(str(font))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2)
