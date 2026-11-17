from tongzhang.forms import EntryDialog
from tongzhang.widgets import Client, LoginDialog, currency


def context():
    return {
        "members": [
            {"active": 1, "user_id": "u1", "name": "成员"},
            {"active": 1, "user_id": "u2", "name": "同事"},
        ],
        "categories": [{"direction": "EXPENSE", "id": "c", "name": "餐饮"}],
    }


def test_login_controls(qtbot):
    dialog = LoginDialog(Client())
    qtbot.addWidget(dialog)
    assert dialog.username.text() == "manager"
    assert dialog.password.text() == "Demo123!"
    assert currency(405000) == "4,050.00"


def test_entry_keeps_inputs_on_missing_allocation(qtbot):
    dialog = EntryDialog(Client(), "ledger", context(), lambda: None, user_id="u1")
    qtbot.addWidget(dialog)
    dialog.amount.setText("100.00")
    dialog.note.setText("有效输入")
    dialog.save()
    assert dialog.amount.text() == "100.00"
    assert dialog.note.text() == "有效输入"
    assert "至少" in dialog.error.text()


def test_entry_allocation_helpers_add_up(qtbot):
    dialog = EntryDialog(Client(), "ledger", context(), lambda: None, user_id="u1")
    qtbot.addWidget(dialog)
    dialog.amount.setText("100.00")
    dialog.split_evenly()
    assert dialog.allocation_total() == 10000
    dialog.all_to_me()
    assert dialog.allocation_total() == 10000
    assert dialog.allocations.item(0, 1).text() == "100.00"


def test_entry_blocks_uneven_allocation(qtbot):
    dialog = EntryDialog(Client(), "ledger", context(), lambda: None, user_id="u1")
    qtbot.addWidget(dialog)
    dialog.amount.setText("100.00")
    dialog.allocations.item(0, 1).setText("60")
    dialog.save()
    assert "合计" in dialog.error.text()


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
    assert qapp.palette().color(QPalette.ColorRole.Window).name() == "#f2f5f4"
    assert qapp.palette().color(QPalette.ColorRole.WindowText).name() == "#1f2d2a"
