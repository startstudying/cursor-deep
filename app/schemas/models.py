from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str


class ModelsListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]
