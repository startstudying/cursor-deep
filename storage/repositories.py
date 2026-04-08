from __future__ import annotations

from dataclasses import dataclass

from storage.db import get_connection


@dataclass(slots=True)
class ChatLogCreate:
    created_at: str
    path: str
    public_model: str | None
    upstream_model: str | None
    stream: bool
    request_body_truncated: str | None = None
    upstream_status_code: int | None = None
    response_body_truncated: str | None = None
    error_text: str | None = None
    duration_ms: int = 0


@dataclass(slots=True)
class ChatLog:
    id: int
    created_at: str
    path: str
    public_model: str | None
    upstream_model: str | None
    stream: bool
    request_body_truncated: str | None
    upstream_status_code: int | None
    response_body_truncated: str | None
    error_text: str | None
    duration_ms: int


class ChatLogRepository:
    def create(self, payload: ChatLogCreate) -> int:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_logs (
                    created_at,
                    path,
                    public_model,
                    upstream_model,
                    stream,
                    request_body_truncated,
                    upstream_status_code,
                    response_body_truncated,
                    error_text,
                    duration_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.created_at,
                    payload.path,
                    payload.public_model,
                    payload.upstream_model,
                    int(payload.stream),
                    payload.request_body_truncated,
                    payload.upstream_status_code,
                    payload.response_body_truncated,
                    payload.error_text,
                    payload.duration_ms,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def list_logs(self, limit: int = 100) -> list[ChatLog]:
        safe_limit = max(1, min(limit, 1000))
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    created_at,
                    path,
                    public_model,
                    upstream_model,
                    stream,
                    request_body_truncated,
                    upstream_status_code,
                    response_body_truncated,
                    error_text,
                    duration_ms
                FROM chat_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        return [
            ChatLog(
                id=int(row["id"]),
                created_at=str(row["created_at"]),
                path=str(row["path"]),
                public_model=row["public_model"],
                upstream_model=row["upstream_model"],
                stream=bool(row["stream"]),
                request_body_truncated=row["request_body_truncated"],
                upstream_status_code=row["upstream_status_code"],
                response_body_truncated=row["response_body_truncated"],
                error_text=row["error_text"],
                duration_ms=int(row["duration_ms"]),
            )
            for row in rows
        ]
