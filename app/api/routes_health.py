from fastapi import APIRouter, Depends

from app.api.deps import require_gateway_bearer

router = APIRouter(dependencies=[Depends(require_gateway_bearer)])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
