from __future__ import annotations

from collections.abc import AsyncIterator
from abc import ABC, abstractmethod

from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse


class ChatProvider(ABC):
    @abstractmethod
    async def create_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        raise NotImplementedError

    @abstractmethod
    async def create_chat_completion_stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[str]:
        raise NotImplementedError
