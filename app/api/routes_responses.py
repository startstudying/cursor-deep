from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.api.deps import require_gateway_bearer
from app.config import settings
from app.providers.base import ProviderGatewayError
from app.providers.factory import get_chat_provider
from app.schemas.responses import ResponseCreateRequest
from services.log_service import LogService

router = APIRouter(prefix="/v1", tags=["responses"])
_LOG_PATH = "/v1/responses"
_log_service = LogService()


@router.post("/responses", dependencies=[Depends(require_gateway_bearer)], response_model=None)
async def create_response(
    http_request: Request,
    payload: ResponseCreateRequest,
) -> Response:
    provider = get_chat_provider()
    started_at = time.perf_counter()

    request_body = _serialize_body(payload.model_dump(exclude_none=True))
    requested_model = payload.model.strip() if payload.model and payload.model.strip() else None
    client_ip = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")
    request_input_count = _estimate_input_count(payload.input)

    try:
        if payload.stream:
            result = await provider.create_response_stream(payload)

            async def logged_stream():
                try:
                    async for chunk in result.stream:
                        yield chunk
                finally:
                    _log_service.safe_record_chat(
                        path=_LOG_PATH,
                        requested_model=requested_model,
                        public_model=result.public_model,
                        upstream_model=result.upstream_model,
                        stream=True,
                        request_body_truncated=request_body,
                        upstream_request_body_truncated=result.upstream_request_body,
                        upstream_status_code=result.upstream_status_code,
                        gateway_status_code=200,
                        response_body_truncated=None,
                        error_text=result.telemetry.error_text,
                        duration_ms=_duration_ms(started_at),
                        client_ip=client_ip,
                        user_agent=user_agent,
                        request_message_count=request_input_count,
                        request_user=payload.user,
                        response_chunk_count=result.telemetry.chunk_count,
                        stream_completed=result.telemetry.completed,
                    )

            return StreamingResponse(
                logged_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        result = await provider.create_response(payload)
        _log_service.safe_record_chat(
            path=_LOG_PATH,
            requested_model=requested_model,
            public_model=result.public_model,
            upstream_model=result.upstream_model,
            stream=False,
            request_body_truncated=request_body,
            upstream_request_body_truncated=result.upstream_request_body,
            upstream_status_code=result.upstream_status_code,
            gateway_status_code=200,
            response_body_truncated=result.response_body,
            error_text=None,
            duration_ms=_duration_ms(started_at),
            client_ip=client_ip,
            user_agent=user_agent,
            request_message_count=request_input_count,
            request_user=payload.user,
            response_chunk_count=0,
            stream_completed=False,
        )
        return JSONResponse(content=result.data)
    except ProviderGatewayError as exc:
        _log_service.safe_record_chat(
            path=_LOG_PATH,
            requested_model=requested_model,
            public_model=exc.public_model,
            upstream_model=exc.upstream_model,
            stream=payload.stream,
            request_body_truncated=request_body,
            upstream_request_body_truncated=exc.upstream_request_body,
            upstream_status_code=exc.upstream_status_code,
            gateway_status_code=exc.status_code,
            response_body_truncated=exc.response_body,
            error_text=exc.error_text or _extract_error_text(exc.detail),
            duration_ms=_duration_ms(started_at),
            client_ip=client_ip,
            user_agent=user_agent,
            request_message_count=request_input_count,
            request_user=payload.user,
            response_chunk_count=0,
            stream_completed=False,
        )
        raise
    except Exception as exc:
        _log_service.safe_record_chat(
            path=_LOG_PATH,
            requested_model=requested_model,
            public_model=None,
            upstream_model=None,
            stream=payload.stream,
            request_body_truncated=request_body,
            upstream_request_body_truncated=None,
            upstream_status_code=None,
            gateway_status_code=500,
            response_body_truncated=None,
            error_text=f"Unhandled gateway exception: {exc}",
            duration_ms=_duration_ms(started_at),
            client_ip=client_ip,
            user_agent=user_agent,
            request_message_count=request_input_count,
            request_user=payload.user,
            response_chunk_count=0,
            stream_completed=False,
        )
        raise


def _estimate_input_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if value is None:
        return 0
    return 1


def _truncate_text(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= settings.max_logged_body_chars:
        return value
    return value[: settings.max_logged_body_chars] + "...<truncated>"


def _serialize_body(payload: dict[str, Any]) -> str:
    try:
        return _truncate_text(json.dumps(payload, ensure_ascii=False))
    except (TypeError, ValueError):
        return _truncate_text(str(payload))


def _duration_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _extract_error_text(detail: Any) -> str:
    if isinstance(detail, dict):
        error = detail.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message
        try:
            return json.dumps(detail, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(detail)
    if isinstance(detail, str):
        return detail
    return str(detail)
