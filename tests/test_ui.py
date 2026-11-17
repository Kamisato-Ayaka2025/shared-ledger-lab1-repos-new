from tongzhang.widgets import Client, LoginDialog, currency
from tongzhang.forms import EntryDialog


def test_login_controls(qtbot):
    dialog = LoginDialog(Client())
    qtbot.addWidget(dialog)
    assert dialog.username.text() == "manager"
    assert dialog.password.text() == "Demo123!"
    assert currency(405000) == "4,050.00"


def test_entry_keeps_inputs_on_missing_allocation(qtbot):
    client = Client()
    context = {
        "members": [{"active": 1, "user_id": "u", "name": "成员"}],
        "categories": [{"direction": "EXPENSE", "id": "c", "name": "餐饮"}],
    }
    dialog = EntryDialog(client, "ledger", context, lambda: None)
    qtbot.addWidget(dialog)
    dialog.amount.setText("100.00")
    dialog.note.setPlainText("有效输入")
    dialog.save()
    assert dialog.amount.text() == "100.00"
    assert dialog.note.toPlainText() == "有效输入"
    assert "至少" in dialog.error.text()


def test_unauthenticated_client_omits_authorization_header(qtbot, monkeypatch):
    import httpx
    from tongzhang.widgets import RequestTask

    captured = {}

    def request(method, url, **kwargs):
        captured.update(kwargs)
        return httpx.Response(200, json={"token": "test"})

    monkeypatch.setattr(httpx, "request", request)
    task = RequestTask("POST", "http://127.0.0.1/login", "", {"username": "alice"}, None)
    with qtbot.waitSignal(task.signals.done) as signal:
        task.run()
    assert captured["headers"] == {}
    assert signal.args == [{"token": "test"}, None]


def test_application_uses_readable_light_palette(qapp):
    from PySide6.QtGui import QPalette
    from tongzhang.desktop import configure_fonts

    configure_fonts(qapp)
    assert qapp.palette().color(QPalette.ColorRole.Window).name() == "#f3f6f5"
    assert qapp.palette().color(QPalette.ColorRole.WindowText).name() == "#203b36"
