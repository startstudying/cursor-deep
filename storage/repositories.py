from __future__ import annotations

from dataclasses import dataclass

from storage.db import get_connection


@dataclass(slots=True)
class ChatLogCreate:
    created_at: str
    path: str
    requested_model: str | None
    public_model: str | None
    upstream_model: str | None
    stream: bool
    request_body_truncated: str | None = None
    upstream_request_body_truncated: str | None = None
    upstream_status_code: int | None = None
    gateway_status_code: int | None = None
    response_body_truncated: str | None = None
    error_text: str | None = None
    duration_ms: int = 0
    client_ip: str | None = None
    user_agent: str | None = None
    request_message_count: int = 0
    request_user: str | None = None
    response_chunk_count: int = 0
    stream_completed: bool = False


@dataclass(slots=True)
class ChatLog:
    id: int
    created_at: str
    path: str
    requested_model: str | None
    public_model: str | None
    upstream_model: str | None
    stream: bool
    request_body_truncated: str | None
    upstream_request_body_truncated: str | None
    upstream_status_code: int | None
    gateway_status_code: int | None
    response_body_truncated: str | None
    error_text: str | None
    duration_ms: int
    client_ip: str | None
    user_agent: str | None
    request_message_count: int
    request_user: str | None
    response_chunk_count: int
    stream_completed: bool


class ChatLogRepository:
    def create(self, payload: ChatLogCreate) -> int:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_logs (
                    created_at,
                    path,
                    requested_model,
                    public_model,
                    upstream_model,
                    stream,
                    request_body_truncated,
                    upstream_request_body_truncated,
                    upstream_status_code,
                    gateway_status_code,
                    response_body_truncated,
                    error_text,
                    duration_ms,
                    client_ip,
                    user_agent,
                    request_message_count,
                    request_user,
                    response_chunk_count,
                    stream_completed
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.created_at,
                    payload.path,
                    payload.requested_model,
                    payload.public_model,
                    payload.upstream_model,
                    int(payload.stream),
                    payload.request_body_truncated,
                    payload.upstream_request_body_truncated,
                    payload.upstream_status_code,
                    payload.gateway_status_code,
                    payload.response_body_truncated,
                    payload.error_text,
                    payload.duration_ms,
                    payload.client_ip,
                    payload.user_agent,
                    payload.request_message_count,
                    payload.request_user,
                    payload.response_chunk_count,
                    int(payload.stream_completed),
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
                    requested_model,
                    public_model,
                    upstream_model,
                    stream,
                    request_body_truncated,
                    upstream_request_body_truncated,
                    upstream_status_code,
                    gateway_status_code,
                    response_body_truncated,
                    error_text,
                    duration_ms,
                    client_ip,
                    user_agent,
                    request_message_count,
                    request_user,
                    response_chunk_count,
                    stream_completed
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
                requested_model=row["requested_model"],
                public_model=row["public_model"],
                upstream_model=row["upstream_model"],
                stream=bool(row["stream"]),
                request_body_truncated=row["request_body_truncated"],
                upstream_request_body_truncated=row["upstream_request_body_truncated"],
                upstream_status_code=row["upstream_status_code"],
                gateway_status_code=row["gateway_status_code"],
                response_body_truncated=row["response_body_truncated"],
                error_text=row["error_text"],
                duration_ms=int(row["duration_ms"]),
                client_ip=row["client_ip"],
                user_agent=row["user_agent"],
                request_message_count=int(row["request_message_count"]),
                request_user=row["request_user"],
                response_chunk_count=int(row["response_chunk_count"]),
                stream_completed=bool(row["stream_completed"]),
            )
            for row in rows
        ]
