"""Database access shared by the MCP server.

Uses PostgreSQL when DATABASE_URL is set, otherwise a local SQLite file that is
created and seeded on first use. The SQL is written to work on both engines.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _init_sqlite(path: Path) -> None:
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript((DATA / "schema.sql").read_text(encoding="utf-8"))
    conn.executescript((DATA / "seed.sql").read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


def connect():
    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        import psycopg2  # optional dependency, only needed for PostgreSQL

        return psycopg2.connect(dsn), "postgres"
    path = DATA / "helpdesk.db"
    if not path.exists():
        _init_sqlite(path)
    return sqlite3.connect(path), "sqlite"


def fetch_one(conn, engine: str, sql: str, params: tuple):
    sql = sql if engine == "sqlite" else sql.replace("?", "%s")
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return row


def leave_balance(conn, engine: str, employee_id: str) -> dict | None:
    row = fetch_one(
        conn,
        engine,
        "SELECT annual_remaining, sick_remaining, casual_remaining, as_of "
        "FROM leave_balances WHERE employee_id = ?",
        (employee_id.upper(),),
    )
    if not row:
        return None
    return {
        "employee_id": employee_id.upper(),
        "annual_remaining": row[0],
        "sick_remaining": row[1],
        "casual_remaining": row[2],
        "as_of": str(row[3]),
    }


def employee_profile(conn, engine: str, employee_id: str) -> dict | None:
    row = fetch_one(
        conn,
        engine,
        "SELECT full_name, department, manager_id, date_joined "
        "FROM employees WHERE employee_id = ?",
        (employee_id.upper(),),
    )
    if not row:
        return None
    return {
        "employee_id": employee_id.upper(),
        "full_name": row[0],
        "department": row[1],
        "manager_id": row[2],
        "date_joined": str(row[3]),
    }
