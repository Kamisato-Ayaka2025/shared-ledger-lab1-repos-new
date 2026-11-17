"""HTTP boundary for the desktop application."""

import logging
import os
import sqlite3
from pathlib import Path
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .database import Database
from .domain import BusinessError
from .service import Service


class Login(BaseModel):
    username: str
    password: str


class Command(BaseModel):
    name: str = ""
    target: str = ""
    action: str = ""
    custodian: str | None = None
    version: int = 0
    reason: str = ""
    data: dict = Field(default_factory=dict)
    key: str = ""
    month: str = ""
    amount: str = ""
    start: str = ""
    end: str = ""


def create_app(path=None, demo=False):
    folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Tongzhang"
    database = Database(str(path or folder / "ledger.db"))
    service = Service(database)
    if demo:
        service.seed()
    app = FastAPI(title="同账", version="0.1.0")
    app.state.service = service

    @app.exception_handler(BusinessError)
    async def business_error(request: Request, exc: BusinessError):
        logging.getLogger("tongzhang.security").warning(
            "%s %s status=%s", request.method, request.url.path, exc.status
        )
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request: Request, exc: sqlite3.OperationalError):
        logging.exception("Database operation failed")
        return JSONResponse({"detail": "数据保存暂未完成，请稍后重试"}, status_code=503)

    def token(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise BusinessError("请先登录", 401)
        return authorization[7:]

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/login")
    def login(body: Login):
        return service.login(body.username, body.password)

    @app.post("/logout")
    def logout(authorization: str = Header(default="")):
        import hashlib

        with database.transaction(True) as c:
            c.execute(
                "DELETE FROM sessions WHERE token=?",
                (hashlib.sha256(token(authorization).encode()).hexdigest(),),
            )
        return {"ok": True}

    @app.get("/bootstrap")
    def bootstrap(authorization: str = Header(default="")):
        return service.bootstrap(token(authorization))

    @app.post("/ledgers")
    def create(body: Command, authorization: str = Header(default="")):
        return service.create_ledger(token(authorization), body.name)

    @app.get("/ledgers/{ledger_id}/context")
    def context(ledger_id: str, authorization: str = Header(default="")):
        return service.context(token(authorization), ledger_id)

    @app.post("/ledgers/{ledger_id}/invite")
    def invite(ledger_id: str, body: Command, authorization: str = Header(default="")):
        return service.invite(token(authorization), ledger_id, body.target)

    @app.post("/invitations/{invitation_id}")
    def invitation(invitation_id: str, body: Command, authorization: str = Header(default="")):
        return service.invitation_action(token(authorization), invitation_id, body.action)

    @app.post("/ledgers/{ledger_id}/members")
    def member(ledger_id: str, body: Command, authorization: str = Header(default="")):
        return service.member_action(
            token(authorization), ledger_id, body.target, body.action, body.custodian
        )

    @app.get("/ledgers/{ledger_id}/entries")
    def query(ledger_id: str, request: Request, authorization: str = Header(default="")):
        return service.query(token(authorization), ledger_id, dict(request.query_params))

    @app.post("/ledgers/{ledger_id}/entries")
    def submit(ledger_id: str, body: Command, authorization: str = Header(default="")):
        return service.submit(token(authorization), ledger_id, body.data, body.key)

    @app.get("/entries/{entry_id}")
    def detail(entry_id: str, authorization: str = Header(default="")):
        return service.detail(token(authorization), entry_id)

    @app.post("/entries/{entry_id}")
    def entry_action(entry_id: str, body: Command, authorization: str = Header(default="")):
        return service.entry_action(
            token(authorization), entry_id, body.action, body.version, body.reason, body.data
        )

    @app.get("/ledgers/{ledger_id}/finance")
    def finance(ledger_id: str, start: str, end: str, authorization: str = Header(default="")):
        return service.finance(token(authorization), ledger_id, start, end)

    @app.post("/ledgers/{ledger_id}/budget")
    def budget(ledger_id: str, body: Command, authorization: str = Header(default="")):
        return service.set_budget(
            token(authorization), ledger_id, body.month, body.amount, body.version, body.reason
        )

    @app.post("/ledgers/{ledger_id}/settle")
    def settle(ledger_id: str, body: Command, authorization: str = Header(default="")):
        return service.settle(token(authorization), ledger_id, body.start, body.end)

    @app.get("/ledgers/{ledger_id}/records/{kind}")
    def records(ledger_id: str, kind: str, authorization: str = Header(default="")):
        return service.records(token(authorization), ledger_id, kind)

    return app


def main():
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    uvicorn.run(create_app(args.database, args.demo), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
