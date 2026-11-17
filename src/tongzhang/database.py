"""SQLite schema and explicit transaction ownership."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
 id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 password TEXT NOT NULL, super INTEGER NOT NULL DEFAULT 0, creator INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),expires TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledgers(id TEXT PRIMARY KEY,name TEXT NOT NULL,admin_id TEXT NOT NULL REFERENCES users(id),revision INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS memberships(id TEXT PRIMARY KEY,ledger_id TEXT NOT NULL REFERENCES ledgers(id),user_id TEXT NOT NULL REFERENCES users(id),active INTEGER NOT NULL,joined TEXT NOT NULL,left_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS active_member ON memberships(ledger_id,user_id) WHERE active=1;
CREATE TABLE IF NOT EXISTS invitations(id TEXT PRIMARY KEY,ledger_id TEXT NOT NULL REFERENCES ledgers(id),actor_id TEXT NOT NULL REFERENCES users(id),target_id TEXT NOT NULL REFERENCES users(id),expires TEXT NOT NULL,status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS categories(id TEXT PRIMARY KEY,ledger_id TEXT NOT NULL REFERENCES ledgers(id),name TEXT NOT NULL,direction TEXT NOT NULL,UNIQUE(ledger_id,name,direction));
CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY,ledger_id TEXT NOT NULL REFERENCES ledgers(id),submitter_id TEXT NOT NULL REFERENCES users(id),editor_id TEXT NOT NULL REFERENCES users(id),custodian_id TEXT REFERENCES users(id),direction TEXT NOT NULL CHECK(direction IN ('INCOME','EXPENSE')),amount INTEGER NOT NULL CHECK(amount>0),category_id TEXT NOT NULL REFERENCES categories(id),occurred TEXT NOT NULL,note TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED','WITHDRAWN')),version INTEGER NOT NULL,source_id TEXT REFERENCES entries(id),created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS entry_query ON entries(ledger_id,status,occurred);
CREATE TABLE IF NOT EXISTS participants(entry_id TEXT NOT NULL REFERENCES entries(id),user_id TEXT NOT NULL REFERENCES users(id),amount INTEGER NOT NULL CHECK(amount>=0),PRIMARY KEY(entry_id,user_id));
CREATE INDEX IF NOT EXISTS participant_user ON participants(user_id,entry_id);
CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES entries(id),version INTEGER NOT NULL,actor_id TEXT NOT NULL REFERENCES users(id),data TEXT NOT NULL,reason TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES entries(id),version INTEGER NOT NULL,actor_id TEXT NOT NULL REFERENCES users(id),decision TEXT NOT NULL,reason TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS budgets(ledger_id TEXT NOT NULL REFERENCES ledgers(id),month TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>=0),version INTEGER NOT NULL,PRIMARY KEY(ledger_id,month));
CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,ledger_id TEXT NOT NULL REFERENCES ledgers(id),revision INTEGER NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,income TEXT NOT NULL,expense TEXT NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,ledger_id TEXT NOT NULL REFERENCES ledgers(id),actor_id TEXT NOT NULL REFERENCES users(id),action TEXT NOT NULL,target TEXT NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency(ledger_id TEXT NOT NULL REFERENCES ledgers(id),actor_id TEXT NOT NULL REFERENCES users(id),key TEXT NOT NULL,payload TEXT NOT NULL,result_id TEXT NOT NULL REFERENCES entries(id),PRIMARY KEY(ledger_id,actor_id,key));
PRAGMA user_version=1;
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            conn.execute("PRAGMA journal_mode=WAL")

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def transaction(self, write=False):
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
