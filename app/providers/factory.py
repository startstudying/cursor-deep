from __future__ import annotations

from app.config import settings
from app.providers.base import ChatProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


def get_chat_provider() -> ChatProvider:
    return OpenAICompatibleProvider(
        base_url=settings.upstream_base_url,
        api_key=settings.upstream_api_key,
        default_model=settings.default_model,
    )
