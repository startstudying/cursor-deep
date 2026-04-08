from __future__ import annotations

from app.config import settings
from app.providers.base import ChatProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


_provider: ChatProvider | None = None


def get_chat_provider() -> ChatProvider:
    global _provider

    if _provider is None:
        _provider = OpenAICompatibleProvider(
            base_url=settings.upstream_base_url,
            api_key=settings.upstream_api_key,
            default_model=settings.default_model,
            request_timeout_seconds=settings.request_timeout_seconds,
            drop_fields=set(settings.drop_fields),
            max_logged_body_chars=settings.max_logged_body_chars,
        )
    return _provider
