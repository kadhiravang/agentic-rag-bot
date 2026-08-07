"""SQLite persistence: users, sessions, messages, citations."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from . import config

_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL REFERENCES users(username),
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                covered INTEGER,
                trace TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS session_files (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                filename TEXT NOT NULL,
                chunks INTEGER NOT NULL,
                kind TEXT NOT NULL DEFAULT 'upload',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS citations (
                id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL REFERENCES messages(id),
                marker INTEGER,
                source TEXT,
                speakers TEXT,
                ts_start TEXT,
                ts_end TEXT,
                page_start INTEGER,
                page_end INTEGER,
                quote TEXT,
                chunk_id TEXT,
                score REAL
            );
            """
        )
        _conn.execute(
            "INSERT OR IGNORE INTO users (username, created_at) VALUES (?, ?)",
            ("admin", _now()),
        )
        _conn.commit()
    return _conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(username: str = "admin", title: str = "New session") -> dict:
    conn = get_conn()
    sid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sessions (id, username, title, created_at) VALUES (?, ?, ?, ?)",
        (sid, username, title, _now()),
    )
    conn.commit()
    return {"id": sid, "username": username, "title": title, "created_at": _now()}


def list_sessions(username: str = "admin") -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM sessions WHERE username = ? ORDER BY created_at DESC",
        (username,),
    ).fetchall()
    return [dict(r) for r in rows]


def rename_session(session_id: str, title: str) -> None:
    conn = get_conn()
    conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
    conn.commit()


def delete_session(session_id: str) -> None:
    conn = get_conn()
    conn.execute(
        "DELETE FROM citations WHERE message_id IN "
        "(SELECT id FROM messages WHERE session_id = ?)",
        (session_id,),
    )
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM session_files WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()


def add_session_file(session_id: str, filename: str, chunks: int, kind: str = "upload") -> dict:
    conn = get_conn()
    fid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO session_files (id, session_id, filename, chunks, kind, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (fid, session_id, filename, chunks, kind, _now()),
    )
    conn.commit()
    return {"id": fid, "session_id": session_id, "filename": filename, "chunks": chunks, "kind": kind}


def list_session_files(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM session_files WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_message(
    session_id: str,
    role: str,
    content: str,
    covered: bool | None = None,
    trace: list | None = None,
    citations: list[dict] | None = None,
) -> str:
    conn = get_conn()
    mid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO messages (id, session_id, role, content, covered, trace, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            mid,
            session_id,
            role,
            content,
            None if covered is None else int(covered),
            json.dumps(trace) if trace else None,
            _now(),
        ),
    )
    for c in citations or []:
        conn.execute(
            "INSERT INTO citations (id, message_id, marker, source, speakers, ts_start, "
            "ts_end, page_start, page_end, quote, chunk_id, score) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                mid,
                c.get("marker"),
                c.get("source"),
                json.dumps(c.get("speakers", [])),
                c.get("ts_start"),
                c.get("ts_end"),
                c.get("page_start"),
                c.get("page_end"),
                c.get("quote"),
                c.get("chunk_id"),
                c.get("score"),
            ),
        )
    conn.commit()
    return mid


def get_messages(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    out = []
    for r in rows:
        msg = dict(r)
        msg["covered"] = None if msg["covered"] is None else bool(msg["covered"])
        msg["trace"] = json.loads(msg["trace"]) if msg["trace"] else []
        crows = conn.execute(
            "SELECT * FROM citations WHERE message_id = ? ORDER BY marker",
            (msg["id"],),
        ).fetchall()
        msg["citations"] = []
        for c in crows:
            cit = dict(c)
            cit["speakers"] = json.loads(cit["speakers"]) if cit["speakers"] else []
            msg["citations"].append(cit)
        out.append(msg)
    return out
