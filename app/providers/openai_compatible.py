from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.providers.base import ChatProvider
from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionChoiceMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    UpstreamChatCompletionResponse,
)


class OpenAICompatibleProvider(ChatProvider):
    def __init__(self, base_url: str, api_key: str, default_model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model

    async def create_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        self._validate_config()

        payload = self._build_payload(request, stream=False)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._build_headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Upstream request failed: {exc}",
            ) from exc

        if response.status_code >= 400:
            detail = self._extract_error_detail(response)
            raise HTTPException(status_code=response.status_code, detail=detail)

        data = UpstreamChatCompletionResponse.model_validate(response.json())
        return self._build_response(data)

    async def create_chat_completion_stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[str]:
        self._validate_config()

        client = httpx.AsyncClient(timeout=None)
        payload = self._build_payload(request, stream=True)

        try:
            req = client.build_request(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._build_headers(accept_sse=True),
                json=payload,
            )
            # 先检查上游状态码，再把流交给 FastAPI，避免回包后才发现上游报错。
            response = await client.send(req, stream=True)
        except httpx.HTTPError as exc:
            await client.aclose()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Upstream request failed: {exc}",
            ) from exc

        if response.status_code >= 400:
            await response.aread()
            detail = self._extract_error_detail(response)
            await response.aclose()
            await client.aclose()
            raise HTTPException(status_code=response.status_code, detail=detail)

        async def event_stream() -> AsyncIterator[str]:
            seen_done = False
            try:
                # 按行透传 SSE，尽量保持 data: / 空行分隔格式不变，方便兼容 OpenAI 客户端。
                async for line in response.aiter_lines():
                    if line.startswith("data:") and line.removeprefix("data:").strip() == "[DONE]":
                        seen_done = True

                    if line:
                        yield f"{line}\n"
                    else:
                        yield "\n"

                # 部分兼容接口不会主动补 [DONE]，这里兜底补齐，降低客户端适配成本。
                if not seen_done:
                    yield "data: [DONE]\n\n"
            except httpx.HTTPError as exc:
                error_payload = {
                    "error": {
                        "message": f"Upstream stream interrupted: {exc}",
                        "type": "upstream_error",
                    }
                }
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                await response.aclose()
                await client.aclose()

        return event_stream()

    def _build_payload(self, request: ChatCompletionRequest, *, stream: bool) -> dict[str, Any]:
        payload = request.model_dump(exclude_none=True)
        payload["model"] = request.model or self.default_model
        payload["stream"] = stream
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
                detail="OPENAI_BASE_URL is not configured.",
            )
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OPENAI_API_KEY is not configured.",
            )
        if not self.default_model:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OPENAI_MODEL is not configured.",
            )

    def _extract_error_detail(self, response: httpx.Response) -> Any:
        try:
            payload = response.json()
        except ValueError:
            return response.text or "Upstream returned an error."

        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            return payload["error"].get("message") or payload
        return payload

    def _build_response(
        self,
        data: UpstreamChatCompletionResponse,
    ) -> ChatCompletionResponse:
        choices: list[ChatCompletionChoice] = []
        for choice in data.choices:
            message = choice.get("message") or {}
            choices.append(
                ChatCompletionChoice(
                    index=choice.get("index", 0),
                    message=ChatCompletionChoiceMessage(
                        role="assistant",
                        content=message.get("content") or "",
                    ),
                    finish_reason=choice.get("finish_reason"),
                )
            )

        usage = None
        if data.usage is not None:
            usage = ChatCompletionUsage(
                prompt_tokens=int(data.usage.get("prompt_tokens", 0)),
                completion_tokens=int(data.usage.get("completion_tokens", 0)),
                total_tokens=int(data.usage.get("total_tokens", 0)),
            )

        return ChatCompletionResponse(
            id=data.id,
            object="chat.completion",
            created=data.created,
            model=data.model,
            choices=choices,
            usage=usage,
        )
