from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "storage" / "app_logs.db"

_db_init_lock = Lock()


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _db_init_lock:
        with get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_time TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    error_message TEXT
                )
                """
            )
            connection.commit()
