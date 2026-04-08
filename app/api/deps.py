from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import settings


def build_error_payload(
    message: str,
    error_type: str = "gateway_error",
) -> dict[str, dict[str, str]]:
    return {
        "error": {
            "message": message,
            "type": error_type,
        }
    }


def _invalid_bearer_token_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=build_error_payload("invalid bearer token"),
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_gateway_bearer(
    authorization: str | None = Header(default=None),
) -> None:
    if not settings.gateway_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=build_error_payload("GATEWAY_API_KEY is not configured."),
        )

    if not authorization:
        raise _invalid_bearer_token_exception()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or token != settings.gateway_api_key:
        raise _invalid_bearer_token_exception()
