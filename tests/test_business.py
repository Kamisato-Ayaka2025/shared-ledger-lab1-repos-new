import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from tongzhang.api import create_app
from tongzhang.domain import BusinessError, money


@pytest.fixture
def env(tmp_path):
    app = create_app(tmp_path / "test.db", demo=True)
    service = app.state.service
    tokens = {
        name: service.login(name, "Demo123!")["token"]
        for name in ["root", "manager", "alice", "bob"]
    }
    users = {u["username"]: u["id"] for u in service.bootstrap(tokens["root"])["users"]}
    ledger = service.create_ledger(tokens["manager"], "测试账本")["id"]
    for name in ["alice", "bob"]:
        invitation = service.invite(tokens["manager"], ledger, users[name])
        service.invitation_action(tokens[name], invitation["id"], "accept")
    return app, service, tokens, users, ledger


def payload(service, tokens, users, ledger, amount="100", direction="EXPENSE"):
    context = service.context(tokens["alice"], ledger)
    category = next(c["id"] for c in context["categories"] if c["direction"] == direction)
    return {
        "direction": direction,
        "amount": amount,
        "category_id": category,
        "occurred": "2026-11-17",
        "note": "测试",
        "participants": [{"user_id": users["alice"], "amount": amount}],
    }


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0", "0.001", "1000000000000", "abc"])
def test_invalid_money(value):
    with pytest.raises(BusinessError):
        money(value)


def test_lifecycle_finance_snapshot(env):
    _, s, t, u, ledger = env
    s.set_budget(t["manager"], ledger, "2026-11", "5000", 0, "初始预算")
    expense = s.submit(t["alice"], ledger, payload(s, t, u, ledger, "2150"), "expense")
    income = s.submit(t["alice"], ledger, payload(s, t, u, ledger, "1200", "INCOME"), "income")
    assert s.finance(t["manager"], ledger, "2026-11-01", "2026-11-30")["profit"] == 0
    for item in [expense, income]:
        s.entry_action(t["manager"], item["id"], "approve", 1)
    financial = s.finance(t["manager"], ledger, "2026-11-01", "2026-11-30")
    assert financial["budgets"][0]["available"] == 405000
    snapshot = s.settle(t["manager"], ledger, "2026-11-01", "2026-11-30")
    assert snapshot["expense"] == 215000
    s.entry_action(t["manager"], expense["id"], "withdraw", 2, "取消")
    s.entry_action(t["manager"], expense["id"], "withdraw", 2, "重试")
    assert (
        s.finance(t["manager"], ledger, "2026-11-01", "2026-11-30")["budgets"][0]["available"]
        == 620000
    )
    old = s.records(t["manager"], ledger, "snapshots")[0]
    assert old["stale"] and json.loads(old["data"])["expense"] == 215000


def test_reject_resubmit_correct_self_review(env):
    _, s, t, u, ledger = env
    data = payload(s, t, u, ledger)
    item = s.submit(t["alice"], ledger, data, "x")
    s.entry_action(t["manager"], item["id"], "reject", 1, "金额有误")
    resubmitted = s.entry_action(t["alice"], item["id"], "resubmit", 2, "修正", data)
    assert resubmitted["status"] == "PENDING"
    s.entry_action(t["manager"], item["id"], "approve", 3)
    correction = s.entry_action(t["manager"], item["id"], "correct", 4, "更正", data)
    assert correction["source_id"] == item["id"]
    with pytest.raises(BusinessError, match="本人"):
        s.entry_action(t["manager"], correction["id"], "approve", 1)
    s.entry_action(t["root"], correction["id"], "approve", 1)
    assert s.finance(t["manager"], ledger, "2026-11-01", "2026-11-30")["expense"] == 10000


def test_idempotency_concurrent_and_version(env):
    _, s, t, u, ledger = env
    data = payload(s, t, u, ledger)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: s.submit(t["alice"], ledger, data, "same"), range(8)))
    assert len({r["id"] for r in results}) == 1
    item = results[0]
    with pytest.raises(BusinessError, match="不同内容"):
        s.submit(t["alice"], ledger, {**data, "note": "changed"}, "same")
    s.entry_action(t["manager"], item["id"], "approve", 1)
    with pytest.raises(BusinessError, match="记录已变化"):
        s.entry_action(t["manager"], item["id"], "reject", 1, "旧页面")


def test_permissions_exit_transfer(env):
    _, s, t, u, ledger = env
    item = s.submit(t["alice"], ledger, payload(s, t, u, ledger), "a")
    with pytest.raises(BusinessError):
        s.detail(t["bob"], item["id"])
    with pytest.raises(BusinessError):
        s.entry_action(t["alice"], item["id"], "approve", 1)
    s.member_action(t["alice"], ledger, u["alice"], "leave", u["root"])
    with pytest.raises(BusinessError):
        s.query(t["alice"], ledger)
    historical = s.detail(t["root"], item["id"])
    assert historical["submitter_id"] == u["alice"]
    assert historical["custodian_id"] == u["root"]
    s.member_action(t["root"], ledger, u["bob"], "transfer")
    with pytest.raises(BusinessError):
        s.finance(t["manager"], ledger, "2026-11-01", "2026-11-30")


def test_transaction_rolls_back_on_audit_failure(env, monkeypatch):
    _, s, t, u, ledger = env
    data = payload(s, t, u, ledger)

    def fail(*args):
        raise RuntimeError("injected")

    monkeypatch.setattr(s, "audit", fail)
    with pytest.raises(RuntimeError):
        s.submit(t["alice"], ledger, data, "fail")
    assert s.query(t["manager"], ledger, {"status": "ALL"}) == []
    with s.db.transaction() as c:
        assert c.execute("SELECT count(*) FROM idempotency").fetchone()[0] == 0


def test_api_login_and_unauthorized(env):
    app, s, t, u, ledger = env
    client = TestClient(app)
    assert client.get("/bootstrap").status_code == 401
    assert client.post("/login", json={"username": "alice", "password": "bad"}).status_code == 401
    response = client.post(
        f"/ledgers/{ledger}/entries",
        headers={"Authorization": "Bearer " + t["alice"]},
        json={"data": payload(s, t, u, ledger), "key": "api"},
    )
    assert response.status_code == 200
    client.post("/logout", headers={"Authorization": "Bearer " + t["alice"]})
    assert (
        client.get("/bootstrap", headers={"Authorization": "Bearer " + t["alice"]}).status_code
        == 401
    )


def test_query_ranges_and_allocation(env):
    _, s, t, u, ledger = env
    data = payload(s, t, u, ledger)
    data["participants"] = [
        {"user_id": u["alice"], "amount": "40"},
        {"user_id": u["bob"], "amount": "60"},
    ]
    item = s.submit(t["alice"], ledger, data, "split")
    s.entry_action(t["manager"], item["id"], "approve", 1)
    result = s.finance(t["manager"], ledger, "2026-11-17", "2026-11-17")
    assert sum(x["expense"] for x in result["members"].values()) == result["expense"]
    assert (
        len(
            s.query(t["manager"], ledger, {"minimum": "100", "maximum": "100", "user_id": u["bob"]})
        )
        == 1
    )
    with pytest.raises(BusinessError):
        s.query(t["manager"], ledger, {"minimum": "200", "maximum": "100"})
    data["participants"][0]["amount"] = "41"
    with pytest.raises(BusinessError, match="合计|之和"):
        s.submit(t["alice"], ledger, data, "bad-split")


def test_modified_content_cannot_be_self_approved(env):
    _, s, t, u, ledger = env
    data = payload(s, t, u, ledger)
    item = s.submit(t["alice"], ledger, data, "edited")
    s.entry_action(t["manager"], item["id"], "edit", 1, "修改", data)
    with pytest.raises(BusinessError, match="本人"):
        s.entry_action(t["manager"], item["id"], "approve", 2)
    s.entry_action(t["root"], item["id"], "approve", 2)
