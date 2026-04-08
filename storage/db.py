from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from app.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent
_db_init_lock = Lock()

_EXPECTED_COLUMNS: dict[str, str] = {
    "created_at": "TEXT NOT NULL DEFAULT ''",
    "path": "TEXT NOT NULL DEFAULT ''",
    "requested_model": "TEXT",
    "public_model": "TEXT",
    "upstream_model": "TEXT",
    "stream": "INTEGER NOT NULL DEFAULT 0",
    "request_body_truncated": "TEXT",
    "upstream_request_body_truncated": "TEXT",
    "upstream_status_code": "INTEGER",
    "gateway_status_code": "INTEGER",
    "response_body_truncated": "TEXT",
    "error_text": "TEXT",
    "duration_ms": "INTEGER NOT NULL DEFAULT 0",
    "client_ip": "TEXT",
    "user_agent": "TEXT",
    "request_message_count": "INTEGER NOT NULL DEFAULT 0",
    "request_user": "TEXT",
    "response_chunk_count": "INTEGER NOT NULL DEFAULT 0",
    "stream_completed": "INTEGER NOT NULL DEFAULT 0",
}


def get_db_path() -> Path:
    configured_path = Path(settings.log_db_path)
    if configured_path.is_absolute():
        return configured_path
    return BASE_DIR / configured_path


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _db_init_lock:
        with get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    path TEXT NOT NULL,
                    requested_model TEXT,
                    public_model TEXT,
                    upstream_model TEXT,
                    stream INTEGER NOT NULL,
                    request_body_truncated TEXT,
                    upstream_request_body_truncated TEXT,
                    upstream_status_code INTEGER,
                    gateway_status_code INTEGER,
                    response_body_truncated TEXT,
                    error_text TEXT,
                    duration_ms INTEGER NOT NULL,
                    client_ip TEXT,
                    user_agent TEXT,
                    request_message_count INTEGER NOT NULL,
                    request_user TEXT,
                    response_chunk_count INTEGER NOT NULL,
                    stream_completed INTEGER NOT NULL
                )
                """
            )
            _ensure_expected_columns(connection)
            connection.commit()


def _ensure_expected_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(chat_logs)").fetchall()
    }

    for column_name, column_definition in _EXPECTED_COLUMNS.items():
        if column_name in existing_columns:
            continue
        connection.execute(
            f"ALTER TABLE chat_logs ADD COLUMN {column_name} {column_definition}"
        )
