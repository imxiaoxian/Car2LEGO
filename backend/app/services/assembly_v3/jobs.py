"""Durable job checkpoints and atomic controls, shared by web and Celery workers."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


class JobStopped(Exception):
    pass


class BudgetExceeded(Exception):
    pass


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    replace_file(tmp,path)


def replace_file(source: Path, target: Path):
    """Windows readers can briefly deny rename while polling an artifact."""
    for attempt in range(30):
        try:
            source.replace(target)
            return
        except PermissionError as exc:
            if getattr(exc,"winerror",None) not in (5,32,33) or attempt==29:
                raise
            time.sleep(.1)


class JobStore:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root or settings.storage_path)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "assembly_jobs.sqlite3"
        with self.db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, state TEXT NOT NULL, stage TEXT NOT NULL,
                progress INTEGER NOT NULL, data TEXT NOT NULL, owner TEXT,
                lease REAL NOT NULL DEFAULT 0, updated REAL NOT NULL)""")

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, id: str) -> dict | None:
        with self.db() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
        if not row:
            return None
        data = json.loads(row["data"])
        # Historical tasks retain their checkpoints, but image calls are unlimited.
        data["limits"]["image"] = None
        return dict(row) | {"data": data}

    def ensure(self, id: str, request: dict):
        data = dict(request=request, checkpoint={}, calls={"text": 0, "image": 0},
                    limits={"text": settings.assembly_text_call_limit, "image": None},
                    module_repairs={}, replans=0)
        with self.db() as conn:
            conn.execute("INSERT OR IGNORE INTO jobs(id,state,stage,progress,data,updated) VALUES(?,?,?,?,?,?)",
                         (id, "pending", "starting", 0, json.dumps(data), time.time()))

    def claim(self, id: str) -> str | None:
        owner = uuid.uuid4().hex
        with self.db() as conn:
            row = conn.execute("SELECT state,owner,lease FROM jobs WHERE id=?", (id,)).fetchone()
            if not row or row["state"] in ("paused", "cancelled", "completed", "draft"):
                return None
            if row["owner"] and row["lease"] > time.time():
                return None
            conn.execute("UPDATE jobs SET owner=?,lease=?,state='processing',updated=? WHERE id=?",
                         (owner, time.time() + settings.assembly_lease_seconds, time.time(), id))
        return owner

    def checkpoint(self, id: str, owner: str, stage: str, progress: int, **updates):
        with self.db() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
            if not row or row["owner"] != owner:
                raise JobStopped("Worker lease lost")
            if row["state"] in ("paused", "cancelled"):
                raise JobStopped(row["state"])
            data = json.loads(row["data"])
            data["checkpoint"].update(updates)
            conn.execute("UPDATE jobs SET stage=?,progress=?,data=?,lease=?,updated=? WHERE id=?",
                         (stage, progress, json.dumps(data), time.time() + settings.assembly_lease_seconds, time.time(), id))
        atomic_json(self.root / id / "generation_status.json", {"stage": stage, "progress": progress, "status": "processing"})

    def consume(self, id: str, owner: str, kind: str):
        with self.db() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
            if not row or row["owner"] != owner or row["state"] in ("paused", "cancelled"):
                raise JobStopped(row["state"] if row else "missing")
            data = json.loads(row["data"])
            data["limits"]["image"] = None
            if kind not in ("text", "image"):
                raise ValueError("Unknown model call kind")
            limit = data["limits"][kind]
            if limit is not None and data["calls"][kind] >= limit:
                raise BudgetExceeded(f"{kind} call budget exhausted")
            data["calls"][kind] += 1
            conn.execute("UPDATE jobs SET data=?,lease=?,updated=? WHERE id=?",
                         (json.dumps(data), time.time() + settings.assembly_lease_seconds, time.time(), id))

    def finish(self, id: str, owner: str, state: str, error: str = "", failure: dict | None = None):
        if state not in ("completed", "draft", "failed", "paused", "cancelled"):
            raise ValueError("Invalid terminal job state")
        with self.db() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
            if not row or row["owner"] != owner:
                return
            state = row["state"] if row["state"] in ("paused", "cancelled") else state
            data = json.loads(row["data"])
            data["error"] = error
            data["failure"] = failure if error else None
            progress = 100 if state in ("completed", "draft") and not error else row["progress"]
            conn.execute("UPDATE jobs SET state=?,stage=?,progress=?,owner=NULL,lease=0,data=?,updated=? WHERE id=?",
                         (state, state, progress, json.dumps(data), time.time(), id))
        atomic_json(self.root / id / "generation_status.json", {"stage": state, "status": state, "progress": progress, "error": error, "failure": data["failure"]})

    def control(self, id: str, action: str, module: str | None = None) -> dict:
        with self.db() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
            if not row:
                raise ValueError("Job not found")
            data = json.loads(row["data"])
            state = row["state"]
            if action == "pause" and state in ("processing", "pending"):
                state = "paused"
            elif action == "cancel" and state not in ("completed", "cancelled"):
                state = "cancelled"
            elif action in ("resume", "retry") and state in ("paused", "failed", "draft", "processing"):
                if row["owner"] and row["lease"] > time.time():
                    raise ValueError("Worker is still saving its checkpoint; retry after it stops")
                if action == "retry":
                    if not module:
                        raise ValueError("Local retry requires a module")
                    count = data["module_repairs"].get(module, 0)
                    if count >= settings.assembly_module_repair_limit:
                        raise ValueError("Module repair limit reached; best draft preserved")
                    data["checkpoint"]["retry_module"] = module
                    data["checkpoint"].pop("exported", None)
                elif state == "draft" and data["checkpoint"].get("exported"):
                    raise ValueError("Draft generation finished; retry a specific failed module")
                data["error"] = ""
                data["failure"] = None
                state = "pending"
            else:
                raise ValueError(f"Cannot {action} a {state} job")
            if action in ("resume", "retry"):
                conn.execute("UPDATE jobs SET state=?,stage='resuming',owner=NULL,lease=0,data=?,updated=? WHERE id=?", (state, json.dumps(data), time.time(), id))
            else:
                conn.execute("UPDATE jobs SET state=?,data=?,updated=? WHERE id=?", (state, json.dumps(data), time.time(), id))
        return self.get(id)

    def reserve_repair(self, id: str, owner: str, module: str) -> bool:
        with self.db() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
            if not row or row["owner"] != owner or row["state"] != "processing":
                raise JobStopped("Job interrupted")
            data = json.loads(row["data"])
            count = data["module_repairs"].get(module, 0)
            if count >= settings.assembly_module_repair_limit:
                return False
            data["module_repairs"][module] = count + 1
            conn.execute("UPDATE jobs SET data=?,updated=? WHERE id=?", (json.dumps(data), time.time(), id))
            return True

    def reserve_replan(self, id: str, owner: str) -> bool:
        with self.db() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
            if not row or row["owner"] != owner or row["state"] != "processing":
                raise JobStopped("Job interrupted")
            data = json.loads(row["data"])
            if data["replans"] >= settings.assembly_replan_limit:
                return False
            data["replans"] += 1
            conn.execute("UPDATE jobs SET data=?,updated=? WHERE id=?", (json.dumps(data), time.time(), id))
            return True

    def recoverable(self) -> list[str]:
        with self.db() as conn:
            return [r[0] for r in conn.execute("SELECT id FROM jobs WHERE state IN ('pending','processing') AND lease<?", (time.time(),))]
