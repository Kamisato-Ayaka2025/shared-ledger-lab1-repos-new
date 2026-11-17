"""Application services: all authorizations and business mutations live here."""

import hashlib
import hmac
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from .database import Database
from .domain import BusinessError, money, now, require, text, uid


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200000)
    return salt + ":" + digest.hex()


def row(conn, sql, args=()):
    result = conn.execute(sql, args).fetchone()
    return dict(result) if result else None


def rows(conn, sql, args=()):
    return [dict(item) for item in conn.execute(sql, args)]


class Service:
    def __init__(self, database: Database):
        self.db = database

    def seed(self):
        with self.db.transaction(True) as c:
            if c.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                return
            for username, name, admin, creator in [
                ("root", "超级管理员", 1, 1),
                ("manager", "账本管理员", 0, 1),
                ("alice", "小林", 0, 0),
                ("bob", "小周", 0, 0),
            ]:
                c.execute(
                    "INSERT INTO users VALUES(?,?,?,?,?,?)",
                    (uid(), username, name, password_hash("Demo123!"), admin, creator),
                )

    def login(self, username, password):
        with self.db.transaction(True) as c:
            user = row(c, "SELECT * FROM users WHERE username=?", (username,))
            require(user is not None, "用户名或密码错误", 401)
            require(
                hmac.compare_digest(
                    user["password"], password_hash(password, user["password"].split(":")[0])
                ),
                "用户名或密码错误",
                401,
            )
            token = secrets.token_urlsafe(32)
            expires = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
            c.execute(
                "INSERT INTO sessions VALUES(?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), user["id"], expires),
            )
            user.pop("password")
            return {"token": token, "user": user}

    def actor(self, c, token):
        user = row(
            c,
            "SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?",
            (hashlib.sha256(token.encode()).hexdigest(), now()),
        )
        require(user is not None, "登录已失效，请重新登录", 401)
        user.pop("password")
        return user

    def authorize(self, c, actor, ledger_id, management=False):
        ledger = row(c, "SELECT * FROM ledgers WHERE id=?", (ledger_id,))
        require(ledger is not None, "账本不存在或无权访问", 404)
        manager = actor["super"] or ledger["admin_id"] == actor["id"]
        member = row(
            c,
            "SELECT id FROM memberships WHERE ledger_id=? AND user_id=? AND active=1",
            (ledger_id, actor["id"]),
        )
        require(bool(manager or (member and not management)), "没有此操作的权限", 403)
        return ledger

    def audit(self, c, actor, ledger_id, action, target, data):
        c.execute(
            "INSERT INTO audit VALUES(?,?,?,?,?,?,?)",
            (uid(), ledger_id, actor["id"], action, target, encode(data), now()),
        )
        c.execute("UPDATE ledgers SET revision=revision+1 WHERE id=?", (ledger_id,))

    def bootstrap(self, token):
        with self.db.transaction() as c:
            actor = self.actor(c, token)
            ledgers = rows(
                c,
                "SELECT DISTINCT l.* FROM ledgers l LEFT JOIN memberships m ON m.ledger_id=l.id AND m.active=1 WHERE ?=1 OR l.admin_id=? OR m.user_id=? ORDER BY l.name",
                (actor["super"], actor["id"], actor["id"]),
            )
            people = rows(c, "SELECT id,username,name,super,creator FROM users ORDER BY username")
            invitations = rows(
                c,
                "SELECT i.*,l.name ledger_name,u.name inviter FROM invitations i JOIN ledgers l ON l.id=i.ledger_id JOIN users u ON u.id=i.actor_id WHERE i.target_id=? AND i.status='PENDING'",
                (actor["id"],),
            )
            return {"user": actor, "ledgers": ledgers, "users": people, "invitations": invitations}

    def create_ledger(self, token, name):
        with self.db.transaction(True) as c:
            actor = self.actor(c, token)
            require(bool(actor["super"] or actor["creator"]), "没有创建账本资格", 403)
            ledger_id = uid()
            c.execute(
                "INSERT INTO ledgers VALUES(?,?,?,0)",
                (ledger_id, text(name, "账本名称", 80), actor["id"]),
            )
            c.execute(
                "INSERT INTO memberships VALUES(?,?,?,?,?,NULL)",
                (uid(), ledger_id, actor["id"], 1, now()),
            )
            for direction, names in [
                ("EXPENSE", ["餐饮", "交通", "住宿", "采购", "其他支出"]),
                ("INCOME", ["项目收入", "其他收入"]),
            ]:
                for category in names:
                    c.execute(
                        "INSERT INTO categories VALUES(?,?,?,?)",
                        (uid(), ledger_id, category, direction),
                    )
            self.audit(c, actor, ledger_id, "创建账本", ledger_id, {"name": name})
            return {"id": ledger_id}

    def context(self, token, ledger_id):
        with self.db.transaction() as c:
            actor = self.actor(c, token)
            ledger = self.authorize(c, actor, ledger_id)
            members = rows(
                c,
                "SELECT m.*,u.name,u.username FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.ledger_id=? ORDER BY m.active DESC,u.name",
                (ledger_id,),
            )
            return {
                "ledger": ledger,
                "members": members,
                "categories": rows(
                    c,
                    "SELECT * FROM categories WHERE ledger_id=? ORDER BY direction,name",
                    (ledger_id,),
                ),
                "manager": bool(actor["super"] or ledger["admin_id"] == actor["id"]),
            }

    def invite(self, token, ledger_id, target):
        with self.db.transaction(True) as c:
            actor = self.actor(c, token)
            self.authorize(c, actor, ledger_id)
            require(row(c, "SELECT id FROM users WHERE id=?", (target,)) is not None, "用户不存在")
            require(
                not row(
                    c,
                    "SELECT id FROM memberships WHERE ledger_id=? AND user_id=? AND active=1",
                    (ledger_id, target),
                ),
                "该用户已经是成员",
            )
            existing = row(
                c,
                "SELECT id FROM invitations WHERE ledger_id=? AND target_id=? AND status='PENDING' AND expires>?",
                (ledger_id, target, now()),
            )
            if existing:
                return existing
            invitation = uid()
            c.execute(
                "INSERT INTO invitations VALUES(?,?,?,?,?,?)",
                (
                    invitation,
                    ledger_id,
                    actor["id"],
                    target,
                    (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                    "PENDING",
                ),
            )
            self.audit(c, actor, ledger_id, "邀请成员", invitation, {"target": target})
            return {"id": invitation}

    def invitation_action(self, token, invitation_id, action):
        with self.db.transaction(True) as c:
            actor = self.actor(c, token)
            invitation = row(c, "SELECT * FROM invitations WHERE id=?", (invitation_id,))
            require(invitation is not None, "邀请不存在", 404)
            require(invitation["status"] == "PENDING", "邀请已经处理", 409)
            require(invitation["expires"] > now(), "邀请已过期")
            if action == "accept":
                require(actor["id"] == invitation["target_id"], "只有受邀人可接受", 403)
                inviter = row(c, "SELECT * FROM users WHERE id=?", (invitation["actor_id"],))
                self.authorize(c, inviter, invitation["ledger_id"])
                if not row(
                    c,
                    "SELECT id FROM memberships WHERE ledger_id=? AND user_id=? AND active=1",
                    (invitation["ledger_id"], actor["id"]),
                ):
                    c.execute(
                        "INSERT INTO memberships VALUES(?,?,?,?,?,NULL)",
                        (uid(), invitation["ledger_id"], actor["id"], 1, now()),
                    )
                status = "ACCEPTED"
            else:
                require(action == "cancel", "未知邀请操作")
                if actor["id"] != invitation["actor_id"]:
                    self.authorize(c, actor, invitation["ledger_id"], True)
                status = "CANCELLED"
            c.execute("UPDATE invitations SET status=? WHERE id=?", (status, invitation_id))
            self.audit(
                c, actor, invitation["ledger_id"], "处理邀请", invitation_id, {"status": status}
            )
            return {"status": status}

    def member_action(self, token, ledger_id, target, action, custodian=None):
        with self.db.transaction(True) as c:
            actor = self.actor(c, token)
            ledger = self.authorize(c, actor, ledger_id, action != "leave")
            member = row(
                c,
                "SELECT * FROM memberships WHERE ledger_id=? AND user_id=? AND active=1",
                (ledger_id, target),
            )
            require(member is not None, "目标不是有效成员")
            if action == "transfer":
                require(bool(actor["super"]), "只有超级管理员可以更换管理员", 403)
                c.execute("UPDATE ledgers SET admin_id=? WHERE id=?", (target, ledger_id))
            else:
                require(action in ("leave", "remove"), "未知成员操作")
                require(target != ledger["admin_id"], "管理员必须先移交账本")
                if action == "leave":
                    require(target == actor["id"], "只能自行退出", 403)
                target_user = row(c, "SELECT * FROM users WHERE id=?", (target,))
                require(
                    not target_user["super"] or action == "leave",
                    "不能通过成员移除操作移除超级管理员",
                )
                require(
                    row(c, "SELECT id FROM users WHERE id=? AND super=1", (custodian,)) is not None,
                    "请选择超级管理员接管历史",
                )
                c.execute(
                    "UPDATE memberships SET active=0,left_at=? WHERE id=?", (now(), member["id"])
                )
                c.execute(
                    "UPDATE entries SET custodian_id=? WHERE ledger_id=? AND submitter_id=?",
                    (custodian, ledger_id, target),
                )
            self.audit(
                c,
                actor,
                ledger_id,
                {"transfer": "更换管理员", "leave": "成员退出", "remove": "移除成员"}[action],
                target,
                {"previous_admin": ledger["admin_id"], "custodian": custodian},
            )
            return {"ok": True}

    def entry_data(self, c, ledger_id, data):
        direction = data.get("direction")
        require(direction in ("INCOME", "EXPENSE"), "请选择收入或支出")
        amount = money(data.get("amount"))
        category = row(
            c,
            "SELECT * FROM categories WHERE id=? AND ledger_id=?",
            (data.get("category_id"), ledger_id),
        )
        require(
            category is not None and category["direction"] == direction,
            "类别与账本或收支方向不匹配",
        )
        try:
            occurred = date.fromisoformat(data.get("occurred", "")).isoformat()
        except (ValueError, TypeError):
            raise BusinessError("业务日期格式应为 YYYY-MM-DD") from None
        participants = data.get("participants", [])
        require(isinstance(participants, list) and bool(participants), "至少选择一位涉及成员")
        allocated = []
        seen = set()
        for participant in participants:
            user_id = participant.get("user_id")
            require(user_id not in seen, "参与成员不能重复")
            seen.add(user_id)
            require(
                row(
                    c,
                    "SELECT id FROM memberships WHERE ledger_id=? AND user_id=? AND active=1",
                    (ledger_id, user_id),
                )
                is not None,
                "涉及成员必须属于当前账本",
            )
            allocated.append(
                {"user_id": user_id, "amount": money(participant.get("amount"), zero=True)}
            )
        require(sum(p["amount"] for p in allocated) == amount, "成员分配金额之和必须等于账目金额")
        return {
            "direction": direction,
            "amount": amount,
            "category_id": category["id"],
            "occurred": occurred,
            "note": str(data.get("note", ""))[:1000],
            "participants": allocated,
        }

    def save_revision(self, c, entry_id, actor, reason):
        item = self.full_entry(c, entry_id)
        c.execute(
            "INSERT INTO revisions VALUES(?,?,?,?,?,?,?)",
            (uid(), entry_id, item["version"], actor["id"], encode(item), reason, now()),
        )

    def full_entry(self, c, entry_id):
        item = row(
            c,
            "SELECT e.*,u.name submitter,c.name category FROM entries e JOIN users u ON u.id=e.submitter_id JOIN categories c ON c.id=e.category_id WHERE e.id=?",
            (entry_id,),
        )
        require(item is not None, "账目不存在", 404)
        item["participants"] = rows(
            c,
            "SELECT p.*,u.name FROM participants p JOIN users u ON u.id=p.user_id WHERE entry_id=?",
            (entry_id,),
        )
        return item

    def insert_entry(self, c, actor, ledger_id, data, source_id=None):
        entry_id = uid()
        c.execute(
            "INSERT INTO entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                entry_id,
                ledger_id,
                actor["id"],
                actor["id"],
                None,
                data["direction"],
                data["amount"],
                data["category_id"],
                data["occurred"],
                data["note"],
                "PENDING",
                1,
                source_id,
                now(),
            ),
        )
        for p in data["participants"]:
            c.execute(
                "INSERT INTO participants VALUES(?,?,?)", (entry_id, p["user_id"], p["amount"])
            )
        self.save_revision(c, entry_id, actor, "新增" if not source_id else "更正记录")
        return entry_id

    def submit(self, token, ledger_id, data, key):
        key = text(key, "请求标识", 100)
        payload = hashlib.sha256(encode(data).encode()).hexdigest()
        with self.db.transaction(True) as c:
            actor = self.actor(c, token)
            self.authorize(c, actor, ledger_id)
            previous = row(
                c,
                "SELECT * FROM idempotency WHERE ledger_id=? AND actor_id=? AND key=?",
                (ledger_id, actor["id"], key),
            )
            if previous:
                require(previous["payload"] == payload, "请求标识已用于不同内容", 409)
                return self.full_entry(c, previous["result_id"])
            clean = self.entry_data(c, ledger_id, data)
            entry_id = self.insert_entry(c, actor, ledger_id, clean)
            c.execute(
                "INSERT INTO idempotency VALUES(?,?,?,?,?)",
                (ledger_id, actor["id"], key, payload, entry_id),
            )
            self.audit(c, actor, ledger_id, "新增账目", entry_id, clean)
            return self.full_entry(c, entry_id)

    def entry_action(self, token, entry_id, action, version, reason="", data=None):
        with self.db.transaction(True) as c:
            actor = self.actor(c, token)
            item = self.full_entry(c, entry_id)
            self.authorize(c, actor, item["ledger_id"], action != "resubmit")
            if action == "withdraw" and item["status"] == "WITHDRAWN":
                return item
            require(item["version"] == version, "记录已变化，请刷新后重试", 409)
            result_id = entry_id
            if action in ("approve", "reject"):
                require(item["status"] == "PENDING", "仅待审核记录可审核", 409)
                require(
                    actor["id"] not in (item["submitter_id"], item["editor_id"]),
                    "不能审核本人提交或修改的记录",
                    403,
                )
                if action == "reject":
                    reason = text(reason, "驳回原因")
                status = "APPROVED" if action == "approve" else "REJECTED"
                c.execute(
                    "INSERT INTO reviews VALUES(?,?,?,?,?,?,?)",
                    (uid(), entry_id, version, actor["id"], status, reason, now()),
                )
            elif action == "withdraw":
                reason = text(reason, "撤回原因")
                status = "WITHDRAWN"
            elif action in ("edit", "resubmit", "correct"):
                if action == "resubmit":
                    require(item["status"] == "REJECTED", "仅驳回记录可以重交", 409)
                    require(
                        actor["id"] in (item["submitter_id"], item["custodian_id"]),
                        "只有原提交人或接管人可以重交",
                        403,
                    )
                elif action == "edit":
                    require(item["status"] == "PENDING", "仅待审记录可直接修改", 409)
                else:
                    require(item["status"] == "APPROVED", "仅已审核记录可以更正", 409)
                reason = text(reason, "修改原因")
                clean = self.entry_data(c, item["ledger_id"], data or {})
                if action == "correct":
                    result_id = self.insert_entry(c, actor, item["ledger_id"], clean, entry_id)
                    status = "WITHDRAWN"
                else:
                    c.execute(
                        "UPDATE entries SET direction=?,amount=?,category_id=?,occurred=?,note=?,editor_id=? WHERE id=?",
                        (
                            clean["direction"],
                            clean["amount"],
                            clean["category_id"],
                            clean["occurred"],
                            clean["note"],
                            actor["id"],
                            entry_id,
                        ),
                    )
                    c.execute("DELETE FROM participants WHERE entry_id=?", (entry_id,))
                    for p in clean["participants"]:
                        c.execute(
                            "INSERT INTO participants VALUES(?,?,?)",
                            (entry_id, p["user_id"], p["amount"]),
                        )
                    status = "PENDING"
            else:
                raise BusinessError("未知账目操作")
            c.execute(
                "UPDATE entries SET status=?,version=version+1 WHERE id=?", (status, entry_id)
            )
            self.save_revision(c, entry_id, actor, reason or action)
            self.audit(
                c,
                actor,
                item["ledger_id"],
                action,
                entry_id,
                {
                    "before": item,
                    "after": self.full_entry(c, entry_id),
                    "reason": reason,
                    "result_id": result_id,
                },
            )
            return self.full_entry(c, result_id)

    def query(self, token, ledger_id, filters=None):
        filters = filters or {}
        with self.db.transaction() as c:
            actor = self.actor(c, token)
            ledger = self.authorize(c, actor, ledger_id)
            clauses = ["e.ledger_id=?"]
            args = [ledger_id]
            if not actor["super"] and ledger["admin_id"] != actor["id"]:
                clauses.append("e.submitter_id=?")
                args.append(actor["id"])
            status = filters.get("status", "")
            if status:
                require(
                    status in ("PENDING", "APPROVED", "REJECTED", "WITHDRAWN", "ALL"), "未知状态"
                )
                if status != "ALL":
                    clauses.append("e.status=?")
                    args.append(status)
            else:
                clauses.append("e.status!='WITHDRAWN'")
            for key, op in (("start", ">="), ("end", "<=")):
                if filters.get(key):
                    try:
                        date.fromisoformat(filters[key])
                    except ValueError:
                        raise BusinessError("查询日期格式错误") from None
                    clauses.append(f"e.occurred{op}?")
                    args.append(filters[key])
            require(
                not (filters.get("start") and filters.get("end"))
                or filters["start"] <= filters["end"],
                "开始日期不能晚于结束日期",
            )
            for key, op in (("minimum", ">="), ("maximum", "<=")):
                if filters.get(key) not in (None, ""):
                    clauses.append(f"e.amount{op}?")
                    args.append(money(filters[key], zero=True))
            if filters.get("minimum") not in (None, "") and filters.get("maximum") not in (
                None,
                "",
            ):
                require(
                    money(filters["minimum"], zero=True) <= money(filters["maximum"], zero=True),
                    "金额下界不能大于上界",
                )
            if filters.get("category_id"):
                clauses.append("e.category_id=?")
                args.append(filters["category_id"])
            if filters.get("user_id"):
                clauses.append(
                    "EXISTS(SELECT 1 FROM participants p WHERE p.entry_id=e.id AND p.user_id=?)"
                )
                args.append(filters["user_id"])
            return rows(
                c,
                "SELECT e.*,u.name submitter,c.name category FROM entries e JOIN users u ON u.id=e.submitter_id JOIN categories c ON c.id=e.category_id WHERE "
                + " AND ".join(clauses)
                + " ORDER BY e.occurred DESC,e.created DESC LIMIT 10001",
                args,
            )

    def detail(self, token, entry_id):
        with self.db.transaction() as c:
            actor = self.actor(c, token)
            item = self.full_entry(c, entry_id)
            ledger = self.authorize(c, actor, item["ledger_id"])
            require(
                bool(
                    actor["super"]
                    or ledger["admin_id"] == actor["id"]
                    or item["submitter_id"] == actor["id"]
                ),
                "无权查看他人账目",
                403,
            )
            item["history"] = rows(
                c,
                "SELECT r.*,u.name actor FROM revisions r JOIN users u ON u.id=r.actor_id WHERE entry_id=? ORDER BY created",
                (entry_id,),
            )
            item["reviews"] = rows(
                c,
                "SELECT r.*,u.name actor FROM reviews r JOIN users u ON u.id=r.actor_id WHERE entry_id=? ORDER BY created",
                (entry_id,),
            )
            return item

    def finance_data(self, c, ledger_id, start, end):
        try:
            date.fromisoformat(start)
            date.fromisoformat(end)
        except (ValueError, TypeError):
            raise BusinessError("请填写有效的起止日期") from None
        require(start <= end, "开始日期不能晚于结束日期")
        items = rows(
            c,
            "SELECT e.*,c.name category FROM entries e JOIN categories c ON c.id=e.category_id WHERE e.ledger_id=? AND e.status='APPROVED' AND e.occurred>=? AND e.occurred<=? ORDER BY e.id",
            (ledger_id, start, end),
        )
        income = sum(i["amount"] for i in items if i["direction"] == "INCOME")
        expense = sum(i["amount"] for i in items if i["direction"] == "EXPENSE")
        categories = {}
        members = {}
        for item in items:
            direction = "income" if item["direction"] == "INCOME" else "expense"
            categories.setdefault(item["category"], {"income": 0, "expense": 0})[direction] += item[
                "amount"
            ]
            item["participants"] = rows(
                c,
                "SELECT p.*,u.name FROM participants p JOIN users u ON u.id=p.user_id WHERE entry_id=?",
                (item["id"],),
            )
            for p in item["participants"]:
                members.setdefault(p["user_id"], {"name": p["name"], "income": 0, "expense": 0})[
                    direction
                ] += p["amount"]
        return {
            "income": income,
            "expense": expense,
            "profit": income - expense,
            "categories": categories,
            "members": members,
            "items": items,
        }

    def finance(self, token, ledger_id, start, end):
        with self.db.transaction() as c:
            actor = self.actor(c, token)
            self.authorize(c, actor, ledger_id, True)
            data = self.finance_data(c, ledger_id, start, end)
            budgets = rows(
                c, "SELECT * FROM budgets WHERE ledger_id=? ORDER BY month", (ledger_id,)
            )
            for budget in budgets:
                month_start = date.fromisoformat(budget["month"] + "-01")
                next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
                summary = self.finance_data(
                    c,
                    ledger_id,
                    month_start.isoformat(),
                    (next_month - timedelta(days=1)).isoformat(),
                )
                budget["available"] = budget["amount"] + summary["profit"]
            data["budgets"] = budgets
            return data

    def set_budget(self, token, ledger_id, month, amount, version, reason):
        try:
            require(date.fromisoformat(month + "-01").strftime("%Y-%m") == month, "月份格式错误")
        except (ValueError, TypeError):
            raise BusinessError("月份格式应为 YYYY-MM") from None
        amount = money(amount, zero=True)
        reason = text(reason, "预算变更原因")
        with self.db.transaction(True) as c:
            actor = self.actor(c, token)
            self.authorize(c, actor, ledger_id, True)
            old = row(c, "SELECT * FROM budgets WHERE ledger_id=? AND month=?", (ledger_id, month))
            require((old["version"] if old else 0) == version, "预算已变化，请刷新", 409)
            c.execute(
                "INSERT INTO budgets VALUES(?,?,?,?) ON CONFLICT(ledger_id,month) DO UPDATE SET amount=excluded.amount,version=excluded.version",
                (ledger_id, month, amount, version + 1),
            )
            self.audit(
                c,
                actor,
                ledger_id,
                "设置预算",
                month,
                {"before": old, "amount": amount, "reason": reason},
            )
            return {"ok": True}

    def settle(self, token, ledger_id, start, end):
        with self.db.transaction(True) as c:
            actor = self.actor(c, token)
            ledger = self.authorize(c, actor, ledger_id, True)
            data = self.finance_data(c, ledger_id, start, end)
            snapshot_id = uid()
            c.execute(
                "INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    snapshot_id,
                    ledger_id,
                    ledger["revision"],
                    start,
                    end,
                    str(data["income"]),
                    str(data["expense"]),
                    encode(data),
                    now(),
                ),
            )
            # Saving a snapshot does not change source data or invalidate earlier snapshots.
            c.execute(
                "INSERT INTO audit VALUES(?,?,?,?,?,?,?)",
                (
                    uid(),
                    ledger_id,
                    actor["id"],
                    "保存结算快照",
                    snapshot_id,
                    encode({"start": start, "end": end}),
                    now(),
                ),
            )
            return {"id": snapshot_id, **data}

    def records(self, token, ledger_id, kind):
        with self.db.transaction() as c:
            actor = self.actor(c, token)
            ledger = self.authorize(c, actor, ledger_id, True)
            if kind == "snapshots":
                result = rows(
                    c,
                    "SELECT * FROM snapshots WHERE ledger_id=? ORDER BY created DESC",
                    (ledger_id,),
                )
                for item in result:
                    item["stale"] = item["revision"] != ledger["revision"]
                return result
            if kind == "invitations":
                return rows(
                    c,
                    "SELECT i.*,u.name target FROM invitations i JOIN users u ON u.id=i.target_id WHERE ledger_id=? ORDER BY expires DESC",
                    (ledger_id,),
                )
            return rows(
                c,
                "SELECT a.*,u.name actor FROM audit a JOIN users u ON u.id=a.actor_id WHERE ledger_id=? ORDER BY created DESC",
                (ledger_id,),
            )
