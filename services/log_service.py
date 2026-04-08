from __future__ import annotations

from datetime import datetime, timezone

from storage.repositories import ChatLogCreate, ChatLogRepository


class LogService:
    def __init__(self, repository: ChatLogRepository | None = None) -> None:
        self.repository = repository or ChatLogRepository()

    def safe_record_chat(
        self,
        *,
        path: str,
        requested_model: str | None,
        public_model: str | None,
        upstream_model: str | None,
        stream: bool,
        request_body_truncated: str | None,
        upstream_request_body_truncated: str | None,
        upstream_status_code: int | None,
        gateway_status_code: int | None,
        response_body_truncated: str | None,
        error_text: str | None,
        duration_ms: int,
        client_ip: str | None,
        user_agent: str | None,
        request_message_count: int,
        request_user: str | None,
        response_chunk_count: int,
        stream_completed: bool,
    ) -> None:
        try:
            self.repository.create(
                ChatLogCreate(
                    created_at=datetime.now(timezone.utc).isoformat(),
                    path=path,
                    requested_model=requested_model,
                    public_model=public_model,
                    upstream_model=upstream_model,
                    stream=stream,
                    request_body_truncated=request_body_truncated,
                    upstream_request_body_truncated=upstream_request_body_truncated,
                    upstream_status_code=upstream_status_code,
                    gateway_status_code=gateway_status_code,
                    response_body_truncated=response_body_truncated,
                    error_text=error_text,
                    duration_ms=duration_ms,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    request_message_count=request_message_count,
                    request_user=request_user,
                    response_chunk_count=response_chunk_count,
                    stream_completed=stream_completed,
                )
            )
        except Exception as exc:
            print(f"[warning] failed to write chat log: {exc}")
