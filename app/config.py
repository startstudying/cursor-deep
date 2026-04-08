from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DEFAULT_APP_NAME = "cursor-deep-plus"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8787
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_PUBLIC_MODEL_NAME = "cursor-proxy"
DEFAULT_GATEWAY_API_KEY = "local-dev-token"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 600
DEFAULT_LOG_DB_PATH = Path("storage") / "chat_logs.db"
DEFAULT_MAX_LOGGED_BODY_CHARS = 12000


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


def _normalize_string_list(values: list[Any], *, name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            raise SettingsError(f"{name} items must be strings.")

        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue

        normalized.append(cleaned)
        seen.add(cleaned)

    return normalized


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
    raw_value = os.getenv("DROP_FIELDS", "").strip()
    if not raw_value:
        return []

    if raw_value.startswith("["):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise SettingsError(
                "DROP_FIELDS must be a comma-separated string or a JSON array of strings."
            ) from exc

        if not isinstance(parsed, list):
            raise SettingsError("DROP_FIELDS JSON value must be an array of strings.")
        return _normalize_string_list(parsed, name="DROP_FIELDS")

    return _normalize_string_list(raw_value.split(","), name="DROP_FIELDS")


def _load_log_db_path() -> str:
    raw_value = _load_string("LOG_DB_PATH", DEFAULT_LOG_DB_PATH.as_posix())
    normalized_path = Path(raw_value).expanduser()
    return str(normalized_path)


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: _load_string("APP_NAME", DEFAULT_APP_NAME))
    host: str = field(default_factory=lambda: _load_string("HOST", DEFAULT_HOST))
    port: int = field(default_factory=lambda: _load_int("PORT", DEFAULT_PORT))

    upstream_base_url: str = field(
        default_factory=lambda: _load_string("OPENAI_BASE_URL", "").rstrip("/")
    )
    upstream_api_key: str = field(default_factory=lambda: _load_string("OPENAI_API_KEY", ""))
    default_model: str = field(
        default_factory=lambda: _load_string("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    )

    public_model_name: str = field(
        default_factory=lambda: _load_string("PUBLIC_MODEL_NAME", DEFAULT_PUBLIC_MODEL_NAME)
    )
    model_map: dict[str, str] = field(
        default_factory=lambda: _load_model_map(
            _load_string("PUBLIC_MODEL_NAME", DEFAULT_PUBLIC_MODEL_NAME),
            _load_string("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        )
    )

    gateway_api_key: str = field(
        default_factory=lambda: _load_string("GATEWAY_API_KEY", DEFAULT_GATEWAY_API_KEY)
    )
    request_timeout_seconds: int = field(
        default_factory=lambda: _load_int(
            "REQUEST_TIMEOUT_SECONDS",
            DEFAULT_REQUEST_TIMEOUT_SECONDS,
        )
    )
    log_db_path: str = field(default_factory=_load_log_db_path)
    max_logged_body_chars: int = field(
        default_factory=lambda: _load_int(
            "MAX_LOGGED_BODY_CHARS",
            DEFAULT_MAX_LOGGED_BODY_CHARS,
        )
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
