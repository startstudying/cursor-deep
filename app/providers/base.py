from __future__ import annotations

from collections.abc import AsyncIterator
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from app.schemas.chat import ChatCompletionRequest


@dataclass(slots=True)
class StreamTelemetry:
    chunk_count: int = 0
    error_text: str | None = None
    completed: bool = False


@dataclass(slots=True)
class ChatCompletionResult:
    data: dict[str, Any]
    public_model: str | None
    upstream_model: str | None
    upstream_status_code: int | None
    response_body: str | None
    upstream_request_body: str | None


@dataclass(slots=True)
class ChatCompletionStreamResult:
    stream: AsyncIterator[str]
    public_model: str | None
    upstream_model: str | None
    upstream_status_code: int | None
    upstream_request_body: str | None
    telemetry: StreamTelemetry = field(default_factory=StreamTelemetry)


class ProviderGatewayError(HTTPException):
    def __init__(
        self,
        *,
        status_code: int,
        detail: Any,
        public_model: str | None,
        upstream_model: str | None,
        upstream_status_code: int | None,
        upstream_request_body: str | None,
        response_body: str | None,
        error_text: str | None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.public_model = public_model
        self.upstream_model = upstream_model
        self.upstream_status_code = upstream_status_code
        self.upstream_request_body = upstream_request_body
        self.response_body = response_body
        self.error_text = error_text


class ChatProvider(ABC):
    @abstractmethod
    async def create_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResult:
        raise NotImplementedError

    @abstractmethod
    async def create_chat_completion_stream(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionStreamResult:
        raise NotImplementedError
