"""Tiny SQLite store for workflow state (campaigns + audit log). The dataset itself stays in read-only parquet.

DB file: data/app.db (override with PROMOFORGE_DB). Created automatically on first use; delete it to reset the demo.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("PROMOFORGE_DB", Path(__file__).resolve().parents[2] / "data" / "app.db"))
_LOCK = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                data_json TEXT NOT NULL,          -- full campaign document (spec, simulation, seals, outcome)
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL);
        """)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_id() -> str:
    with _LOCK, _conn() as c:
        n = c.execute("SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM campaigns").fetchone()[0]
    return f"PF-{(n or 100) + 1}"


def save(doc: dict, action: str, detail: str = "") -> dict:
    """Insert or update a campaign and record the action in the audit log, atomically."""
    now = _now()
    with _LOCK, _conn() as c:
        c.execute("""INSERT INTO campaigns (id, status, data_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)
                     ON CONFLICT(id) DO UPDATE SET status=excluded.status, data_json=excluded.data_json, updated_at=excluded.updated_at""",
                  (doc["id"], doc["status"], json.dumps(doc), now, now))
        c.execute("INSERT INTO audit_events (campaign_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
                  (doc["id"], action, detail, now))
    return doc


def get(cid: str) -> dict | None:
    with _LOCK, _conn() as c:
        row = c.execute("SELECT data_json FROM campaigns WHERE id = ?", (cid,)).fetchone()
    return json.loads(row["data_json"]) if row else None


def all_campaigns() -> list[dict]:
    with _LOCK, _conn() as c:
        rows = c.execute("SELECT data_json FROM campaigns ORDER BY created_at, id").fetchall()
    return [json.loads(r["data_json"]) for r in rows]


def audit(cid: str) -> list[dict]:
    with _LOCK, _conn() as c:
        rows = c.execute("SELECT action, detail, created_at FROM audit_events WHERE campaign_id = ? ORDER BY id", (cid,)).fetchall()
    return [dict(r) for r in rows]


def reset() -> None:
    with _LOCK, _conn() as c:
        c.execute("DELETE FROM campaigns")
        c.execute("DELETE FROM audit_events")
