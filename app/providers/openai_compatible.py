from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.api.deps import build_error_payload
from app.config import settings
from app.providers.base import (
    ChatCompletionResult,
    ChatCompletionStreamResult,
    ChatProvider,
    ProviderGatewayError,
)
from app.schemas.chat import ChatCompletionRequest
from app.schemas.responses import ResponseCreateRequest


class OpenAICompatibleProvider(ChatProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        default_model: str,
        request_timeout_seconds: int,
        drop_fields: set[str] | None = None,
        max_logged_body_chars: int = 12000,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.request_timeout_seconds = request_timeout_seconds
        self.drop_fields = drop_fields or set()
        self.max_logged_body_chars = max(1, max_logged_body_chars)

    async def create_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResult:
        self._validate_config()

        public_model, upstream_model = settings.resolve_upstream_model(request.model)
        payload = self._build_chat_payload(request, upstream_model=upstream_model, stream=False)
        request_body = self._serialize_body(payload)
        return await self._post_json(
            endpoint=settings.upstream_chat_path,
            payload=payload,
            request_body=request_body,
            public_model=public_model,
            upstream_model=upstream_model,
        )

    async def create_chat_completion_stream(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionStreamResult:
        self._validate_config()

        public_model, upstream_model = settings.resolve_upstream_model(request.model)
        payload = self._build_chat_payload(request, upstream_model=upstream_model, stream=True)
        request_body = self._serialize_body(payload)
        return await self._post_stream(
            endpoint=settings.upstream_chat_path,
            payload=payload,
            request_body=request_body,
            public_model=public_model,
            upstream_model=upstream_model,
        )

    async def create_response(
        self,
        request: ResponseCreateRequest,
    ) -> ChatCompletionResult:
        self._validate_config()

        if not settings.upstream_supports_responses:
            raise self._provider_error(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=build_error_payload("Upstream /responses is disabled."),
                public_model=None,
                upstream_model=None,
                upstream_status_code=None,
                upstream_request_body=None,
                response_body=None,
                error_text="Upstream /responses is disabled.",
            )

        public_model, upstream_model = settings.resolve_upstream_model(request.model)
        payload = self._build_response_payload(request, upstream_model=upstream_model, stream=False)
        request_body = self._serialize_body(payload)
        return await self._post_json(
            endpoint=settings.upstream_responses_path,
            payload=payload,
            request_body=request_body,
            public_model=public_model,
            upstream_model=upstream_model,
        )

    async def create_response_stream(
        self,
        request: ResponseCreateRequest,
    ) -> ChatCompletionStreamResult:
        self._validate_config()

        if not settings.upstream_supports_responses:
            raise self._provider_error(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=build_error_payload("Upstream /responses is disabled."),
                public_model=None,
                upstream_model=None,
                upstream_status_code=None,
                upstream_request_body=None,
                response_body=None,
                error_text="Upstream /responses is disabled.",
            )

        public_model, upstream_model = settings.resolve_upstream_model(request.model)
        payload = self._build_response_payload(request, upstream_model=upstream_model, stream=True)
        request_body = self._serialize_body(payload)
        return await self._post_stream(
            endpoint=settings.upstream_responses_path,
            payload=payload,
            request_body=request_body,
            public_model=public_model,
            upstream_model=upstream_model,
        )

    async def _post_json(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        request_body: str,
        public_model: str | None,
        upstream_model: str | None,
    ) -> ChatCompletionResult:
        try:
            async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
                response = await client.post(
                    self._build_url(endpoint),
                    headers=self._build_headers(),
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise self._provider_error(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=build_error_payload("Upstream request timed out."),
                public_model=public_model,
                upstream_model=upstream_model,
                upstream_status_code=None,
                upstream_request_body=request_body,
                response_body=None,
                error_text=f"Upstream timeout: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            raise self._provider_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=build_error_payload(f"Upstream request failed: {exc}"),
                public_model=public_model,
                upstream_model=upstream_model,
                upstream_status_code=None,
                upstream_request_body=request_body,
                response_body=None,
                error_text=f"Upstream request failed: {exc}",
            ) from exc

        response_text = self._truncate_text(response.text)

        if response.status_code >= 400:
            detail = self._extract_error_detail_from_text(response_text)
            raise self._provider_error(
                status_code=response.status_code,
                detail=build_error_payload(detail),
                public_model=public_model,
                upstream_model=upstream_model,
                upstream_status_code=response.status_code,
                upstream_request_body=request_body,
                response_body=response_text,
                error_text=detail,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise self._provider_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=build_error_payload("Upstream returned invalid JSON."),
                public_model=public_model,
                upstream_model=upstream_model,
                upstream_status_code=response.status_code,
                upstream_request_body=request_body,
                response_body=response_text,
                error_text="Upstream returned invalid JSON.",
            ) from exc

        return ChatCompletionResult(
            data=data,
            public_model=public_model,
            upstream_model=upstream_model,
            upstream_status_code=response.status_code,
            response_body=response_text,
            upstream_request_body=request_body,
        )

    async def _post_stream(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        request_body: str,
        public_model: str | None,
        upstream_model: str | None,
    ) -> ChatCompletionStreamResult:
        client = httpx.AsyncClient(timeout=self.request_timeout_seconds)

        try:
            upstream_request = client.build_request(
                "POST",
                self._build_url(endpoint),
                headers=self._build_headers(accept_sse=True),
                json=payload,
            )
            response = await client.send(upstream_request, stream=True)
        except httpx.TimeoutException as exc:
            await client.aclose()
            raise self._provider_error(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=build_error_payload("Upstream request timed out."),
                public_model=public_model,
                upstream_model=upstream_model,
                upstream_status_code=None,
                upstream_request_body=request_body,
                response_body=None,
                error_text=f"Upstream timeout: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            await client.aclose()
            raise self._provider_error(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=build_error_payload(f"Upstream request failed: {exc}"),
                public_model=public_model,
                upstream_model=upstream_model,
                upstream_status_code=None,
                upstream_request_body=request_body,
                response_body=None,
                error_text=f"Upstream request failed: {exc}",
            ) from exc

        if response.status_code >= 400:
            body_bytes = await response.aread()
            await response.aclose()
            await client.aclose()
            response_text = self._decode_bytes(body_bytes)
            error_text = self._extract_error_detail_from_text(response_text)
            raise self._provider_error(
                status_code=response.status_code,
                detail=build_error_payload(error_text),
                public_model=public_model,
                upstream_model=upstream_model,
                upstream_status_code=response.status_code,
                upstream_request_body=request_body,
                response_body=response_text,
                error_text=error_text,
            )

        result = ChatCompletionStreamResult(
            stream=self._build_stream(response, client),
            public_model=public_model,
            upstream_model=upstream_model,
            upstream_status_code=response.status_code,
            upstream_request_body=request_body,
        )
        self._bind_stream_telemetry(result, response, client)
        return result

    def _build_stream(
        self,
        response: httpx.Response,
        client: httpx.AsyncClient,
    ) -> AsyncIterator[str]:
        async def event_stream() -> AsyncIterator[str]:
            try:
                async for line in response.aiter_lines():
                    if line:
                        yield f"{line}\n"
                    else:
                        yield "\n"
            finally:
                await response.aclose()
                await client.aclose()

        return event_stream()

    def _bind_stream_telemetry(
        self,
        result: ChatCompletionStreamResult,
        response: httpx.Response,
        client: httpx.AsyncClient,
    ) -> None:
        async def instrumented_stream() -> AsyncIterator[str]:
            seen_done = False
            try:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_value = line.removeprefix("data:").strip()
                        if data_value == "[DONE]":
                            seen_done = True
                            result.telemetry.completed = True
                        else:
                            result.telemetry.chunk_count += 1

                    if line:
                        yield f"{line}\n"
                    else:
                        yield "\n"

                if not seen_done:
                    result.telemetry.completed = True
                    yield "data: [DONE]\n\n"
            except httpx.HTTPError as exc:
                result.telemetry.error_text = f"Upstream stream interrupted: {exc}"
                yield f"data: {json.dumps(build_error_payload(result.telemetry.error_text), ensure_ascii=False)}\n\n"
                if not seen_done:
                    yield "data: [DONE]\n\n"
            finally:
                await response.aclose()
                await client.aclose()

        result.stream = instrumented_stream()

    def _build_chat_payload(
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

    def _build_response_payload(
        self,
        request: ResponseCreateRequest,
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

    def _build_url(self, endpoint: str) -> str:
        normalized_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        return f"{self.base_url}{normalized_endpoint}"

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

    def _provider_error(
        self,
        *,
        status_code: int,
        detail: Any,
        public_model: str | None,
        upstream_model: str | None,
        upstream_status_code: int | None,
        upstream_request_body: str | None,
        response_body: str | None,
        error_text: str | None,
    ) -> ProviderGatewayError:
        return ProviderGatewayError(
            status_code=status_code,
            detail=detail,
            public_model=public_model,
            upstream_model=upstream_model,
            upstream_status_code=upstream_status_code,
            upstream_request_body=upstream_request_body,
            response_body=response_body,
            error_text=error_text,
        )
