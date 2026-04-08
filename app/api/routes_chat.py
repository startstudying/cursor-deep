from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.api.deps import require_gateway_bearer
from app.providers.factory import get_chat_provider
from app.schemas.chat import ChatCompletionRequest

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat/completions", dependencies=[Depends(require_gateway_bearer)], response_model=None)
async def create_chat_completion(
    request: ChatCompletionRequest,
) -> Response:
    provider = get_chat_provider()

    if request.stream:
        stream = await provider.create_chat_completion_stream(request)
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    response = await provider.create_chat_completion(request)
    return JSONResponse(content=response)
