from __future__ import annotations

from collections.abc import AsyncIterator
from abc import ABC, abstractmethod
from typing import Any

from app.schemas.chat import ChatCompletionRequest


class ChatProvider(ABC):
    @abstractmethod
    async def create_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def create_chat_completion_stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[str]:
        raise NotImplementedError
