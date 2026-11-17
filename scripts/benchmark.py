"""Reproducible HTTP performance measurement against a disposable database."""

import json
import tempfile
import time
from pathlib import Path
from fastapi.testclient import TestClient
from tongzhang.api import create_app
from tongzhang.domain import uid, now


def main():
    with tempfile.TemporaryDirectory() as temp:
        app = create_app(Path(temp) / "perf.db", demo=True)
        service = app.state.service
        token = service.login("manager", "Demo123!")["token"]
        ledger = service.create_ledger(token, "性能样本")["id"]
        context = service.context(token, ledger)
        user = context["ledger"]["admin_id"]
        category = next(c["id"] for c in context["categories"] if c["direction"] == "EXPENSE")
        with service.db.transaction(True) as conn:
            for index in range(10000):
                conn.execute(
                    "INSERT INTO entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        uid(),
                        ledger,
                        user,
                        user,
                        None,
                        "EXPENSE",
                        index + 1,
                        category,
                        f"2026-11-{index % 28 + 1:02}",
                        "性能数据",
                        "APPROVED",
                        1,
                        None,
                        now(),
                    ),
                )
        client = TestClient(app)
        headers = {"Authorization": "Bearer " + token}
        client.get(
            f"/ledgers/{ledger}/entries",
            headers=headers,
            params={"status": "APPROVED", "minimum": "99"},
        )
        samples = []
        for index in range(100):
            lower = (index % 10) * 1000 + 1
            begin = time.perf_counter()
            response = client.get(
                f"/ledgers/{ledger}/entries",
                headers=headers,
                params={
                    "status": "APPROVED",
                    "minimum": str(lower / 100),
                    "maximum": str((lower + 999) / 100),
                },
            )
            elapsed = time.perf_counter() - begin
            data = response.json()
            correct = (
                response.status_code == 200
                and len(data) == 1000
                and all(lower <= item["amount"] <= lower + 999 for item in data)
            )
            samples.append({"index": index + 1, "seconds": elapsed, "correct": correct})
        result = {
            "method": "FastAPI in-process HTTP TestClient; excludes socket and desktop rendering; one warm-up; 10000 rows",
            "passed": sum(s["correct"] and s["seconds"] <= 1 for s in samples),
            "maximum_seconds": max(s["seconds"] for s in samples),
            "samples": samples,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
