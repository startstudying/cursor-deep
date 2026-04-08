from __future__ import annotations

import json
import os
import sys
from html import escape
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, set_key
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.config import DEFAULT_GATEWAY_API_KEY, reload_settings, settings
from app.providers.factory import reset_chat_provider

router = APIRouter(tags=["desktop"])


class DesktopConfigPayload(BaseModel):
    upstreamBaseUrl: str = Field(default="")
    upstreamApiKey: str = Field(default="")
    defaultModel: str = Field(default="")
    publicModelName: str = Field(default="")
    modelMapJson: str = Field(default="")
    gatewayApiKey: str = Field(default="")
    requestTimeoutSeconds: int = Field(default=600, ge=1)


def _desktop_html_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app" / "desktop" / "index.html"
    return Path(__file__).resolve().parents[1] / "desktop" / "index.html"


def _env_path() -> Path:
    return Path(settings.env_file_path).expanduser()


def _ensure_env_file() -> Path:
    env_path = _env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")
    return env_path


def _read_env_values() -> dict[str, str | None]:
    env_path = _env_path()
    if not env_path.exists():
        return {}
    return dict(dotenv_values(env_path))


def _env_string(values: dict[str, str | None], key: str, fallback: str) -> str:
    if key not in values:
        return fallback

    value = values.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _env_int(values: dict[str, str | None], key: str, fallback: int) -> int:
    if key not in values:
        return fallback

    raw_value = values.get(key)
    if raw_value is None:
        return fallback

    text = str(raw_value).strip()
    if not text:
        return fallback

    try:
        return max(1, int(text))
    except ValueError:
        return fallback


def _normalize_model_map_json(
    raw_value: str,
    *,
    public_model_name: str,
    default_model: str,
) -> str:
    candidate = raw_value.strip()
    if not candidate:
        if not public_model_name or not default_model:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "message": "请填写默认模型和对外模型名称，或直接提供有效的 MODEL_MAP_JSON。",
                        "type": "invalid_config",
                    }
                },
            )
        candidate = json.dumps({public_model_name: default_model}, ensure_ascii=False)

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "message": f"MODEL_MAP_JSON 不是有效的 JSON：{exc}",
                    "type": "invalid_config",
                }
            },
        ) from exc

    if not isinstance(parsed, dict) or not parsed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "message": "MODEL_MAP_JSON 必须是非空 JSON 对象。",
                    "type": "invalid_config",
                }
            },
        )

    normalized: dict[str, str] = {}
    for public_name, upstream_name in parsed.items():
        if not isinstance(public_name, str) or not public_name.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "message": "MODEL_MAP_JSON 的键必须是非空字符串。",
                        "type": "invalid_config",
                    }
                },
            )
        if not isinstance(upstream_name, str) or not upstream_name.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "message": "MODEL_MAP_JSON 的值必须是非空字符串。",
                        "type": "invalid_config",
                    }
                },
            )
        normalized[public_name.strip()] = upstream_name.strip()

    return json.dumps(normalized, ensure_ascii=False)


def _editable_config_snapshot() -> dict[str, Any]:
    env_values = _read_env_values()
    return {
        "upstreamBaseUrl": _env_string(env_values, "OPENAI_BASE_URL", settings.upstream_base_url).rstrip("/"),
        "upstreamApiKey": _env_string(env_values, "OPENAI_API_KEY", settings.upstream_api_key),
        "defaultModel": _env_string(env_values, "OPENAI_MODEL", settings.default_model),
        "publicModelName": _env_string(env_values, "PUBLIC_MODEL_NAME", settings.public_model_name),
        "modelMapJson": _env_string(
            env_values,
            "MODEL_MAP_JSON",
            json.dumps(settings.model_map, ensure_ascii=False),
        ),
        "gatewayApiKey": _env_string(env_values, "GATEWAY_API_KEY", settings.gateway_api_key),
        "requestTimeoutSeconds": _env_int(
            env_values,
            "REQUEST_TIMEOUT_SECONDS",
            settings.request_timeout_seconds,
        ),
    }


def _desktop_bootstrap(request: Request) -> dict[str, Any]:
    return {
        "appName": settings.app_name,
        "apiBaseUrl": str(request.base_url).rstrip("/"),
        "defaultModel": next(iter(settings.model_map.keys()), settings.public_model_name),
        "availableModels": [item["id"] for item in settings.models_response_items()],
        "upstreamConfigured": bool(settings.upstream_base_url and settings.upstream_api_key),
        "usingDefaultGatewayKey": settings.gateway_api_key == DEFAULT_GATEWAY_API_KEY,
        "logDbPath": settings.log_db_path,
        "requestTimeoutSeconds": settings.request_timeout_seconds,
        "envFilePath": settings.env_file_path,
        "envFileExists": settings.env_file_exists,
        "envAutoCreated": os.getenv("CURSOR_DEEP_ENV_AUTOCREATED") == "1",
        "isFirstLaunch": os.getenv("CURSOR_DEEP_ENV_FIRST_LAUNCH") == "1",
        "dataDir": settings.data_dir,
        "editableConfig": _editable_config_snapshot(),
    }


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/desktop", status_code=307)


@router.get("/desktop", include_in_schema=False)
def desktop_home(request: Request) -> HTMLResponse:
    html_template = _desktop_html_path().read_text(encoding="utf-8")
    html = html_template.replace("__TITLE__", escape(settings.app_name))
    html = html.replace("__BOOTSTRAP_JSON__", json.dumps(_desktop_bootstrap(request), ensure_ascii=False))
    return HTMLResponse(content=html)


@router.get("/desktop/config")
def desktop_config() -> dict[str, Any]:
    return {
        "envFilePath": settings.env_file_path,
        "envFileExists": _env_path().exists(),
        "config": _editable_config_snapshot(),
        "restartRequired": False,
        "appliedAtRuntime": True,
    }


@router.post("/desktop/config")
def save_desktop_config(payload: DesktopConfigPayload) -> dict[str, Any]:
    env_path = _ensure_env_file()

    normalized_config = {
        "upstreamBaseUrl": payload.upstreamBaseUrl.strip().rstrip("/"),
        "upstreamApiKey": payload.upstreamApiKey.strip(),
        "defaultModel": payload.defaultModel.strip(),
        "publicModelName": payload.publicModelName.strip(),
        "gatewayApiKey": payload.gatewayApiKey.strip(),
        "requestTimeoutSeconds": max(1, int(payload.requestTimeoutSeconds)),
    }
    normalized_config["modelMapJson"] = _normalize_model_map_json(
        payload.modelMapJson,
        public_model_name=normalized_config["publicModelName"],
        default_model=normalized_config["defaultModel"],
    )

    writes = {
        "OPENAI_BASE_URL": normalized_config["upstreamBaseUrl"],
        "OPENAI_API_KEY": normalized_config["upstreamApiKey"],
        "OPENAI_MODEL": normalized_config["defaultModel"],
        "PUBLIC_MODEL_NAME": normalized_config["publicModelName"],
        "MODEL_MAP_JSON": normalized_config["modelMapJson"],
        "GATEWAY_API_KEY": normalized_config["gatewayApiKey"],
        "REQUEST_TIMEOUT_SECONDS": str(normalized_config["requestTimeoutSeconds"]),
    }

    for key, value in writes.items():
        set_key(str(env_path), key, value, quote_mode="auto", encoding="utf-8")

    reload_settings()
    reset_chat_provider()

    return {
        "message": "配置已保存并自动应用，新的接口请求现在就会使用最新配置。",
        "envFilePath": str(env_path),
        "restartRequired": False,
        "appliedAtRuntime": True,
        "runtimeConfigured": bool(settings.upstream_base_url and settings.upstream_api_key),
        "savedConfig": _editable_config_snapshot(),
        "upstreamConfigured": bool(settings.upstream_base_url and settings.upstream_api_key),
        "availableModels": [item["id"] for item in settings.models_response_items()],
    }
