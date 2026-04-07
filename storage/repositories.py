from __future__ import annotations

from dataclasses import dataclass

from storage.db import get_connection


@dataclass(slots=True)
class ChatLogCreate:
    request_time: str
    model_name: str
    success: bool
    error_message: str | None = None


@dataclass(slots=True)
class ChatLog:
    id: int
    request_time: str
    model_name: str
    success: bool
    error_message: str | None


class ChatLogRepository:
    def create(self, payload: ChatLogCreate) -> int:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_logs (request_time, model_name, success, error_message)
                VALUES (?, ?, ?, ?)
                """,
                (
                    payload.request_time,
                    payload.model_name,
                    int(payload.success),
                    payload.error_message,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def list_logs(self, limit: int = 100) -> list[ChatLog]:
        safe_limit = max(1, min(limit, 1000))
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, request_time, model_name, success, error_message
                FROM chat_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        return [
            ChatLog(
                id=int(row["id"]),
                request_time=str(row["request_time"]),
                model_name=str(row["model_name"]),
                success=bool(row["success"]),
                error_message=row["error_message"],
            )
            for row in rows
        ]
