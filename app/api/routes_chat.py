from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.providers.factory import get_chat_provider
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse

router = APIRouter(prefix="/v1/chat", tags=["chat"])


@router.post("/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    request: ChatCompletionRequest,
) -> ChatCompletionResponse | StreamingResponse:
    provider = get_chat_provider()

    if request.stream:
        stream = await provider.create_chat_completion_stream(request)
        # stream=true 时返回标准 SSE，便于兼容 OpenAI 风格客户端。
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return await provider.create_chat_completion(request)
