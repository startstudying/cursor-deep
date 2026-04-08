from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.api import routes_chat
from app.config import settings
from app.providers import openai_compatible
from app.providers.base import (
    ChatCompletionResult,
    ChatCompletionStreamResult,
    StreamTelemetry,
)
from app.providers.openai_compatible import OpenAICompatibleProvider


class _LogRecorder:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def safe_record_chat(self, **kwargs: Any) -> None:
        self.records.append(kwargs)


class _FakeChatProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create_chat_completion(self, request: Any) -> ChatCompletionResult:
        self.calls.append({"kind": "json", "request": request})
        return ChatCompletionResult(
            data={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
            },
            public_model="cursor-proxy",
            upstream_model="gpt-4o-mini",
            upstream_status_code=200,
            response_body='{"ok":true}',
            upstream_request_body='{"model":"gpt-4o-mini"}',
        )

    async def create_chat_completion_stream(self, request: Any) -> ChatCompletionStreamResult:
        self.calls.append({"kind": "stream", "request": request})
        telemetry = StreamTelemetry()

        async def event_stream() -> AsyncIterator[str]:
            telemetry.chunk_count += 1
            yield 'data: {"id":"chunk-1","choices":[{"delta":{"content":"hello"}}]}\n\n'
            telemetry.completed = True
            yield 'data: [DONE]\n\n'

        return ChatCompletionStreamResult(
            stream=event_stream(),
            public_model="cursor-proxy",
            upstream_model="gpt-4o-mini",
            upstream_status_code=200,
            upstream_request_body='{"model":"gpt-4o-mini","stream":true}',
            telemetry=telemetry,
        )


class _AsyncClientStub:
    def __init__(
        self,
        *,
        response: httpx.Response | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.response = response
        self.exception = exception

    async def __aenter__(self) -> _AsyncClientStub:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        return None

    async def post(self, *args: Any, **kwargs: Any) -> httpx.Response:
        if self.exception is not None:
            raise self.exception
        if self.response is None:
            raise AssertionError("response or exception must be provided")
        return self.response


class _AsyncClientFactory:
    def __init__(
        self,
        *,
        response: httpx.Response | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.response = response
        self.exception = exception

    def __call__(self, *args: Any, **kwargs: Any) -> _AsyncClientStub:
        return _AsyncClientStub(response=self.response, exception=self.exception)


def _build_client(monkeypatch: Any) -> TestClient:
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    return TestClient(main_module.app)


def _configure_real_provider_route(
    monkeypatch: Any,
    *,
    response: httpx.Response | None = None,
    exception: Exception | None = None,
) -> tuple[TestClient, _LogRecorder]:
    client = _build_client(monkeypatch)
    recorder = _LogRecorder()
    provider = OpenAICompatibleProvider(
        base_url="https://upstream.test/v1",
        api_key="upstream-key",
        default_model="gpt-4o-mini",
        request_timeout_seconds=30,
    )

    monkeypatch.setattr(settings, "gateway_api_key", "test-token")
    monkeypatch.setattr(settings, "default_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "model_map", {"cursor-proxy": "gpt-4o-mini"})
    monkeypatch.setattr(routes_chat, "_log_service", recorder)
    monkeypatch.setattr(routes_chat, "get_chat_provider", lambda: provider)
    monkeypatch.setattr(
        openai_compatible.httpx,
        "AsyncClient",
        _AsyncClientFactory(response=response, exception=exception),
    )
    return client, recorder


def _chat_request_payload(*, stream: bool = False) -> dict[str, Any]:
    payload = {
        "model": "cursor-proxy",
        "messages": [{"role": "user", "content": "hi"}],
    }
    if stream:
        payload["stream"] = True
    return payload


def test_models_endpoint_lists_public_models(monkeypatch: Any) -> None:
    client = _build_client(monkeypatch)
    monkeypatch.setattr(settings, "gateway_api_key", "test-token")
    monkeypatch.setattr(settings, "app_name", "cursor-deep-plus")
    monkeypatch.setattr(
        settings,
        "model_map",
        {"cursor-proxy": "gpt-4o-mini", "cursor-fast": "gpt-4.1-mini"},
    )

    response = client.get(
        "/v1/models",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "list"
    assert [item["id"] for item in payload["data"]] == ["cursor-proxy", "cursor-fast"]
    assert all(item["owned_by"] == "cursor-deep-plus" for item in payload["data"])


def test_chat_completion_requires_bearer_token(monkeypatch: Any) -> None:
    client = _build_client(monkeypatch)
    monkeypatch.setattr(settings, "gateway_api_key", "test-token")

    response = client.post(
        "/v1/chat/completions",
        json=_chat_request_payload(),
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "invalid bearer token"


def test_chat_completion_returns_json_and_records_log(monkeypatch: Any) -> None:
    client = _build_client(monkeypatch)
    recorder = _LogRecorder()
    provider = _FakeChatProvider()

    monkeypatch.setattr(settings, "gateway_api_key", "test-token")
    monkeypatch.setattr(routes_chat, "_log_service", recorder)
    monkeypatch.setattr(routes_chat, "get_chat_provider", lambda: provider)

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-token", "User-Agent": "pytest"},
        json={
            **_chat_request_payload(),
            "user": "alice",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "chat.completion"
    assert provider.calls[0]["kind"] == "json"
    assert provider.calls[0]["request"].model == "cursor-proxy"

    assert len(recorder.records) == 1
    record = recorder.records[0]
    assert record["requested_model"] == "cursor-proxy"
    assert record["public_model"] == "cursor-proxy"
    assert record["upstream_model"] == "gpt-4o-mini"
    assert record["request_message_count"] == 1
    assert record["request_user"] == "alice"
    assert record["stream"] is False
    assert record["gateway_status_code"] == 200


def test_chat_completion_streams_and_records_completion(monkeypatch: Any) -> None:
    client = _build_client(monkeypatch)
    recorder = _LogRecorder()
    provider = _FakeChatProvider()

    monkeypatch.setattr(settings, "gateway_api_key", "test-token")
    monkeypatch.setattr(routes_chat, "_log_service", recorder)
    monkeypatch.setattr(routes_chat, "get_chat_provider", lambda: provider)

    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-token"},
        json=_chat_request_payload(stream=True),
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert 'data: {"id":"chunk-1"' in body
    assert 'data: [DONE]' in body
    assert provider.calls[0]["kind"] == "stream"

    assert len(recorder.records) == 1
    record = recorder.records[0]
    assert record["stream"] is True
    assert record["response_chunk_count"] == 1
    assert record["stream_completed"] is True
    assert record["gateway_status_code"] == 200


def test_chat_completion_returns_timeout_error_and_records_log(monkeypatch: Any) -> None:
    client, recorder = _configure_real_provider_route(
        monkeypatch,
        exception=httpx.ReadTimeout("timed out"),
    )

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-token"},
        json=_chat_request_payload(),
    )

    assert response.status_code == 504
    assert response.json()["error"]["message"] == "Upstream request timed out."

    assert len(recorder.records) == 1
    record = recorder.records[0]
    assert record["requested_model"] == "cursor-proxy"
    assert record["public_model"] == "cursor-proxy"
    assert record["upstream_model"] == "gpt-4o-mini"
    assert record["upstream_status_code"] is None
    assert record["gateway_status_code"] == 504
    assert record["response_body_truncated"] is None
    assert record["error_text"].startswith("Upstream timeout:")


@pytest.mark.parametrize(
    ("status_code", "body", "content_type", "expected_message"),
    [
        (429, '{"error":{"message":"rate limited"}}', "application/json", "rate limited"),
        (500, "server exploded", "text/plain", "server exploded"),
    ],
)
def test_chat_completion_returns_upstream_http_errors_and_records_log(
    monkeypatch: Any,
    status_code: int,
    body: str,
    content_type: str,
    expected_message: str,
) -> None:
    request = httpx.Request("POST", "https://upstream.test/v1/chat/completions")
    upstream_response = httpx.Response(
        status_code,
        text=body,
        headers={"Content-Type": content_type},
        request=request,
    )
    client, recorder = _configure_real_provider_route(
        monkeypatch,
        response=upstream_response,
    )

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-token"},
        json=_chat_request_payload(),
    )

    assert response.status_code == status_code
    assert response.json()["error"]["message"] == expected_message

    assert len(recorder.records) == 1
    record = recorder.records[0]
    assert record["upstream_status_code"] == status_code
    assert record["gateway_status_code"] == status_code
    assert record["error_text"] == expected_message
    assert record["response_body_truncated"] == body


def test_chat_completion_returns_invalid_json_error_and_records_log(monkeypatch: Any) -> None:
    request = httpx.Request("POST", "https://upstream.test/v1/chat/completions")
    upstream_response = httpx.Response(
        200,
        text="not-json",
        headers={"Content-Type": "application/json"},
        request=request,
    )
    client, recorder = _configure_real_provider_route(
        monkeypatch,
        response=upstream_response,
    )

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-token"},
        json=_chat_request_payload(),
    )

    assert response.status_code == 502
    assert response.json()["error"]["message"] == "Upstream returned invalid JSON."

    assert len(recorder.records) == 1
    record = recorder.records[0]
    assert record["upstream_status_code"] == 200
    assert record["gateway_status_code"] == 502
    assert record["error_text"] == "Upstream returned invalid JSON."
    assert record["response_body_truncated"] == "not-json"
