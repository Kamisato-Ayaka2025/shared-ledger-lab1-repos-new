"""Track local clients so only the last exiting client stops the shared server."""

import json
import os
from contextlib import contextmanager
from pathlib import Path
import msvcrt
import psutil


def identity(process):
    return {"pid": process.pid, "created": process.create_time()}


def living(item):
    try:
        process = psutil.Process(item["pid"])
        return process if process.create_time() == item["created"] else None
    except (psutil.Error, KeyError, TypeError):
        return None


class RuntimeLease:
    def __init__(self, folder, port):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / f"runtime-{port}.json"
        self.lock = self.folder / f"runtime-{port}.lock"
        self.port = port
        self.me = identity(psutil.Process())

    @contextmanager
    def state(self):
        with self.lock.open("a+b") as handle:
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                try:
                    data = json.loads(self.path.read_text(encoding="utf-8"))
                except (FileNotFoundError, ValueError):
                    data = {}
                data["clients"] = [item for item in data.get("clients", []) if living(item)]
                yield data
                temporary = self.path.with_suffix(".tmp")
                temporary.write_text(json.dumps(data), encoding="utf-8")
                os.replace(temporary, self.path)
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

    def acquire(self, healthy, start, executable):
        with self.state() as data:
            if not healthy():
                child = start()
                data["server"] = identity(psutil.Process(child.pid))
            elif not living(data.get("server")):
                # Adopt only a matching local service left behind by the older launcher.
                for connection in psutil.net_connections(kind="tcp"):
                    if (
                        connection.status != psutil.CONN_LISTEN
                        or connection.laddr.port != self.port
                    ):
                        continue
                    try:
                        process = psutil.Process(connection.pid)
                        if (
                            Path(process.exe()).resolve() == Path(executable).resolve()
                            and "--server" in process.cmdline()
                        ):
                            data["server"] = identity(process)
                    except psutil.Error:
                        continue
            if self.me not in data["clients"]:
                data["clients"].append(self.me)

    def release(self):
        with self.state() as data:
            data["clients"] = [item for item in data["clients"] if item != self.me]
            if data["clients"]:
                return
            process = living(data.get("server"))
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except psutil.NoSuchProcess:
                    pass
                except psutil.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            data.pop("server", None)
