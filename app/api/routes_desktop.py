from __future__ import annotations

import json
from html import escape
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import DEFAULT_GATEWAY_API_KEY, settings

router = APIRouter(tags=["desktop"])
_DESKTOP_HTML_PATH = Path(__file__).resolve().parents[1] / "desktop" / "index.html"


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/desktop", status_code=307)


@router.get("/desktop", include_in_schema=False)
def desktop_home(request: Request) -> HTMLResponse:
    html_template = _DESKTOP_HTML_PATH.read_text(encoding="utf-8")
    bootstrap = {
        "appName": settings.app_name,
        "apiBaseUrl": str(request.base_url).rstrip("/"),
        "defaultModel": next(iter(settings.model_map.keys()), settings.public_model_name),
        "availableModels": [item["id"] for item in settings.models_response_items()],
        "upstreamConfigured": bool(settings.upstream_base_url and settings.upstream_api_key),
        "usingDefaultGatewayKey": settings.gateway_api_key == DEFAULT_GATEWAY_API_KEY,
        "logDbPath": settings.log_db_path,
        "requestTimeoutSeconds": settings.request_timeout_seconds,
    }

    html = html_template.replace("__TITLE__", escape(settings.app_name))
    html = html.replace("__BOOTSTRAP_JSON__", json.dumps(bootstrap, ensure_ascii=False))
    return HTMLResponse(content=html)
