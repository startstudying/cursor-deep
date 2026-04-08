from __future__ import annotations

from datetime import datetime, timezone

from storage.db import get_connection


class LogService:
    def safe_record_chat(
        self,
        *,
        path: str,
        public_model: str | None,
        upstream_model: str | None,
        stream: bool,
        request_body_truncated: str | None,
        upstream_status_code: int | None,
        response_body_truncated: str | None,
        error_text: str | None,
        duration_ms: int,
    ) -> None:
        try:
            with get_connection() as connection:
                connection.execute(
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
                        datetime.now(timezone.utc).isoformat(),
                        path,
                        public_model,
                        upstream_model,
                        int(stream),
                        request_body_truncated,
                        upstream_status_code,
                        response_body_truncated,
                        error_text,
                        duration_ms,
                    ),
                )
                connection.commit()
        except Exception as exc:
            print(f"[warning] failed to write chat log: {exc}")
