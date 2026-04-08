from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.api.deps import build_error_payload
from app.config import settings
from app.providers.base import ChatProvider
from app.schemas.chat import ChatCompletionRequest
from services.log_service import LogService


class OpenAICompatibleProvider(ChatProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        default_model: str,
        request_timeout_seconds: int,
        drop_fields: set[str] | None = None,
        max_logged_body_chars: int = 12000,
        log_service: LogService | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.request_timeout_seconds = request_timeout_seconds
        self.drop_fields = drop_fields or set()
        self.max_logged_body_chars = max(1, max_logged_body_chars)
        self.log_service = log_service or LogService()

    async def create_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> dict[str, Any]:
        self._validate_config()

        started_at = time.perf_counter()
        public_model, upstream_model = settings.resolve_upstream_model(request.model)
        payload = self._build_payload(request, upstream_model=upstream_model, stream=False)
        request_body = self._serialize_body(payload)

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._build_headers(),
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            duration_ms = self._duration_ms(started_at)
            self._record_log(
                public_model=public_model,
                upstream_model=upstream_model,
                stream=False,
                request_body=request_body,
                upstream_status_code=None,
                response_body=None,
                error_text=f"Upstream timeout: {exc}",
                duration_ms=duration_ms,
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=build_error_payload("Upstream request timed out."),
            ) from exc
        except httpx.HTTPError as exc:
            duration_ms = self._duration_ms(started_at)
            self._record_log(
                public_model=public_model,
                upstream_model=upstream_model,
                stream=False,
                request_body=request_body,
                upstream_status_code=None,
                response_body=None,
                error_text=f"Upstream request failed: {exc}",
                duration_ms=duration_ms,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=build_error_payload(f"Upstream request failed: {exc}"),
            ) from exc

        duration_ms = self._duration_ms(started_at)
        response_text = self._truncate_text(response.text)

        if response.status_code >= 400:
            detail = self._extract_error_detail_from_text(response_text)
            self._record_log(
                public_model=public_model,
                upstream_model=upstream_model,
                stream=False,
                request_body=request_body,
                upstream_status_code=response.status_code,
                response_body=response_text,
                error_text=detail,
                duration_ms=duration_ms,
            )
            raise HTTPException(
                status_code=response.status_code,
                detail=build_error_payload(detail),
            )

        try:
            data = response.json()
        except ValueError as exc:
            self._record_log(
                public_model=public_model,
                upstream_model=upstream_model,
                stream=False,
                request_body=request_body,
                upstream_status_code=response.status_code,
                response_body=response_text,
                error_text="Upstream returned invalid JSON.",
                duration_ms=duration_ms,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=build_error_payload("Upstream returned invalid JSON."),
            ) from exc

        self._record_log(
            public_model=public_model,
            upstream_model=upstream_model,
            stream=False,
            request_body=request_body,
            upstream_status_code=response.status_code,
            response_body=response_text,
            error_text=None,
            duration_ms=duration_ms,
        )
        return data

    async def create_chat_completion_stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[str]:
        self._validate_config()

        started_at = time.perf_counter()
        public_model, upstream_model = settings.resolve_upstream_model(request.model)
        payload = self._build_payload(request, upstream_model=upstream_model, stream=True)
        request_body = self._serialize_body(payload)
        client = httpx.AsyncClient(timeout=self.request_timeout_seconds)

        try:
            upstream_request = client.build_request(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._build_headers(accept_sse=True),
                json=payload,
            )
            response = await client.send(upstream_request, stream=True)
        except httpx.TimeoutException as exc:
            await client.aclose()
            duration_ms = self._duration_ms(started_at)
            self._record_log(
                public_model=public_model,
                upstream_model=upstream_model,
                stream=True,
                request_body=request_body,
                upstream_status_code=None,
                response_body=None,
                error_text=f"Upstream timeout: {exc}",
                duration_ms=duration_ms,
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=build_error_payload("Upstream request timed out."),
            ) from exc
        except httpx.HTTPError as exc:
            await client.aclose()
            duration_ms = self._duration_ms(started_at)
            self._record_log(
                public_model=public_model,
                upstream_model=upstream_model,
                stream=True,
                request_body=request_body,
                upstream_status_code=None,
                response_body=None,
                error_text=f"Upstream request failed: {exc}",
                duration_ms=duration_ms,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=build_error_payload(f"Upstream request failed: {exc}"),
            ) from exc

        if response.status_code >= 400:
            body_bytes = await response.aread()
            await response.aclose()
            await client.aclose()
            duration_ms = self._duration_ms(started_at)
            response_text = self._decode_bytes(body_bytes)
            error_text = self._extract_error_detail_from_text(response_text)
            self._record_log(
                public_model=public_model,
                upstream_model=upstream_model,
                stream=True,
                request_body=request_body,
                upstream_status_code=response.status_code,
                response_body=None,
                error_text=error_text,
                duration_ms=duration_ms,
            )
            raise HTTPException(
                status_code=response.status_code,
                detail=build_error_payload(error_text),
            )

        async def event_stream() -> AsyncIterator[str]:
            seen_done = False
            error_text: str | None = None

            try:
                async for line in response.aiter_lines():
                    if line.startswith("data:") and line.removeprefix("data:").strip() == "[DONE]":
                        seen_done = True

                    if line:
                        yield f"{line}\n"
                    else:
                        yield "\n"

                if not seen_done:
                    yield "data: [DONE]\n\n"
            except httpx.HTTPError as exc:
                error_text = f"Upstream stream interrupted: {exc}"
                yield f"data: {json.dumps(build_error_payload(error_text), ensure_ascii=False)}\n\n"
                if not seen_done:
                    yield "data: [DONE]\n\n"
            finally:
                await response.aclose()
                await client.aclose()
                self._record_log(
                    public_model=public_model,
                    upstream_model=upstream_model,
                    stream=True,
                    request_body=request_body,
                    upstream_status_code=response.status_code,
                    response_body=None,
                    error_text=error_text,
                    duration_ms=self._duration_ms(started_at),
                )

        return event_stream()

    def _build_payload(
        self,
        request: ChatCompletionRequest,
        *,
        upstream_model: str,
        stream: bool,
    ) -> dict[str, Any]:
        payload = request.model_dump(exclude_none=True)
        payload["model"] = upstream_model or self.default_model
        payload["stream"] = stream

        for field_name in self.drop_fields:
            payload.pop(field_name, None)

        return payload

    def _build_headers(self, *, accept_sse: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if accept_sse:
            headers["Accept"] = "text/event-stream"
        return headers

    def _validate_config(self) -> None:
        if not self.base_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=build_error_payload("OPENAI_BASE_URL is not configured."),
            )
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=build_error_payload("OPENAI_API_KEY is not configured."),
            )
        if not self.default_model:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=build_error_payload("OPENAI_MODEL is not configured."),
            )

    def _extract_error_detail_from_text(self, response_text: str | None) -> str:
        if not response_text:
            return "Upstream returned an error."

        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError:
            return response_text

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str) and message.strip():
                    return message
            message = payload.get("message")
            if isinstance(message, str) and message.strip():
                return message

        return json.dumps(payload, ensure_ascii=False)

    def _decode_bytes(self, payload: bytes) -> str | None:
        if not payload:
            return None
        return self._truncate_text(payload.decode("utf-8", errors="replace"))

    def _serialize_body(self, payload: dict[str, Any]) -> str:
        try:
            return self._truncate_text(json.dumps(payload, ensure_ascii=False))
        except (TypeError, ValueError):
            return self._truncate_text(str(payload))

    def _truncate_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) <= self.max_logged_body_chars:
            return value
        return value[: self.max_logged_body_chars] + "...<truncated>"

    def _duration_ms(self, started_at: float) -> int:
        return int((time.perf_counter() - started_at) * 1000)

    def _record_log(
        self,
        *,
        public_model: str | None,
        upstream_model: str | None,
        stream: bool,
        request_body: str | None,
        upstream_status_code: int | None,
        response_body: str | None,
        error_text: str | None,
        duration_ms: int,
    ) -> None:
        self.log_service.safe_record_chat(
            path="/v1/chat/completions",
            public_model=public_model,
            upstream_model=upstream_model,
            stream=stream,
            request_body_truncated=request_body,
            upstream_status_code=upstream_status_code,
            response_body_truncated=response_body,
            error_text=error_text,
            duration_ms=duration_ms,
        )
