from __future__ import annotations

from datetime import datetime, timezone

from storage.repositories import ChatLog, ChatLogCreate, ChatLogRepository


class LogService:
    def __init__(self, repository: ChatLogRepository | None = None) -> None:
        self.repository = repository or ChatLogRepository()

    def record_chat_request(
        self,
        *,
        model_name: str,
        success: bool,
        error_message: str | None = None,
    ) -> int:
        payload = ChatLogCreate(
            request_time=datetime.now(timezone.utc).isoformat(),
            model_name=model_name,
            success=success,
            error_message=error_message,
        )
        return self.repository.create(payload)

    def get_logs(self, limit: int = 100) -> list[ChatLog]:
        return self.repository.list_logs(limit=limit)
