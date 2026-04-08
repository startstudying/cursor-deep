from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_gateway_bearer
from app.config import settings
from app.schemas.models import ModelCard, ModelsListResponse

router = APIRouter(prefix="/v1", tags=["models"])
_CREATED_AT = 1710000000


@router.get("/models", response_model=ModelsListResponse, dependencies=[Depends(require_gateway_bearer)])
def list_models() -> ModelsListResponse:
    return ModelsListResponse(
        object="list",
        data=[
            ModelCard(
                id=item["id"],
                object="model",
                created=_CREATED_AT,
                owned_by=item["owned_by"],
            )
            for item in settings.models_response_items()
        ],
    )
