from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResponseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str | None = None
    input: Any
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = Field(default=None, ge=1)
    tools: list[dict[str, Any]] | None = None
    user: str | None = None
