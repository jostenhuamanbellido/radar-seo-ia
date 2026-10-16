"""Historial de auditorías en SQLite (data/radar.db) para ver la evolución de cada web."""
import json
import sqlite3

from .config import DATA_DIR

DB = DATA_DIR / "radar.db"


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE IF NOT EXISTS audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT, domain TEXT, created_at TEXT,
            total INTEGER, local INTEGER, geo INTEGER, aeo INTEGER, ai INTEGER,
            data TEXT
        )""")
    return c


def save(result: dict) -> int:
    s = result["scores"]
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO audits (url, domain, created_at, total, local, geo, aeo, ai, data) VALUES (?,?,?,?,?,?,?,?,?)",
            (result["final_url"], result["domain"], result["created_at"], s["total"], s.get("local"), s.get("geo"),
             s.get("aeo"), s.get("ai"), json.dumps(result, ensure_ascii=False, default=str)),
        )
        return cur.lastrowid


def get(audit_id: int):
    with _conn() as c:
        row = c.execute("SELECT data FROM audits WHERE id=?", (audit_id,)).fetchone()
    if not row:
        return None
    data = json.loads(row["data"])
    data["id"] = audit_id
    return data


def recent(limit: int = 30) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, url, domain, created_at, total, local, geo, aeo, ai FROM audits ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def history(domain: str) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, url, created_at, total, local, geo, aeo, ai FROM audits WHERE domain=? ORDER BY id", (domain,)
        ).fetchall()
    return [dict(r) for r in rows]


def previous(domain: str, before_id: int):
    with _conn() as c:
        row = c.execute(
            "SELECT id, total, local, geo, aeo, ai, created_at FROM audits WHERE domain=? AND id<? ORDER BY id DESC LIMIT 1",
            (domain, before_id),
        ).fetchone()
    return dict(row) if row else None


def delete(audit_id: int):
    with _conn() as c:
        c.execute("DELETE FROM audits WHERE id=?", (audit_id,))
