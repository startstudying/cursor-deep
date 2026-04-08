from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class SettingsError(RuntimeError):
    pass


def _load_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer.") from exc


def _load_string(name: str, default: str) -> str:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    value = raw_value.strip()
    return value or default


def _load_model_map(public_model_name: str, default_model: str) -> dict[str, str]:
    raw_value = os.getenv("MODEL_MAP_JSON", "").strip()
    if not raw_value:
        return {public_model_name: default_model}

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise SettingsError("MODEL_MAP_JSON must be valid JSON.") from exc

    if not isinstance(parsed, dict) or not parsed:
        raise SettingsError("MODEL_MAP_JSON must be a non-empty JSON object.")

    normalized: dict[str, str] = {}
    for public_name, upstream_name in parsed.items():
        if not isinstance(public_name, str) or not public_name.strip():
            raise SettingsError("MODEL_MAP_JSON keys must be non-empty strings.")
        if not isinstance(upstream_name, str) or not upstream_name.strip():
            raise SettingsError("MODEL_MAP_JSON values must be non-empty strings.")
        normalized[public_name.strip()] = upstream_name.strip()

    return normalized


def _load_drop_fields() -> list[str]:
    raw_value = os.getenv("DROP_FIELDS", "")
    return [field.strip() for field in raw_value.split(",") if field.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: _load_string("APP_NAME", "cursor-deep-plus"))
    host: str = field(default_factory=lambda: _load_string("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _load_int("PORT", 8787))

    upstream_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "").strip().rstrip("/")
    )
    upstream_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip())
    default_model: str = field(default_factory=lambda: _load_string("OPENAI_MODEL", "gpt-4o-mini"))

    public_model_name: str = field(
        default_factory=lambda: _load_string("PUBLIC_MODEL_NAME", "cursor-proxy")
    )
    model_map: dict[str, str] = field(
        default_factory=lambda: _load_model_map(
            _load_string("PUBLIC_MODEL_NAME", "cursor-proxy"),
            _load_string("OPENAI_MODEL", "gpt-4o-mini"),
        )
    )

    gateway_api_key: str = field(
        default_factory=lambda: _load_string("GATEWAY_API_KEY", "local-dev-token")
    )
    request_timeout_seconds: int = field(
        default_factory=lambda: _load_int("REQUEST_TIMEOUT_SECONDS", 600)
    )
    log_db_path: str = field(default_factory=lambda: _load_string("LOG_DB_PATH", "storage/chat_logs.db"))
    max_logged_body_chars: int = field(
        default_factory=lambda: _load_int("MAX_LOGGED_BODY_CHARS", 12000)
    )
    drop_fields: list[str] = field(default_factory=_load_drop_fields)

    def resolve_public_model(self, requested_model: str | None) -> str:
        if requested_model and requested_model.strip():
            return requested_model.strip()
        return next(iter(self.model_map.keys()), self.public_model_name)

    def resolve_upstream_model(self, requested_model: str | None) -> tuple[str, str]:
        public_model = self.resolve_public_model(requested_model)
        upstream_model = self.model_map.get(public_model, public_model or self.default_model)
        return public_model, upstream_model

    def models_response_items(self) -> list[dict[str, Any]]:
        return [
            {
                "id": public_model,
                "object": "model",
                "owned_by": self.app_name,
            }
            for public_model in self.model_map.keys()
        ]


settings = Settings()
