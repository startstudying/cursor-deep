from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.deps import build_error_payload
from app.api.routes_chat import router as chat_router
from app.api.routes_desktop import router as desktop_router
from app.api.routes_health import router as health_router
from app.api.routes_models import router as models_router
from app.api.routes_responses import router as responses_router
from app.config import settings
from storage.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        init_db()
    except Exception as exc:
        print(f"[warning] failed to initialize sqlite log db: {exc}")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
if settings.enable_desktop_routes:
    app.include_router(desktop_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
app.include_router(responses_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers)

    if isinstance(detail, str):
        payload = build_error_payload(detail)
    else:
        payload = build_error_payload("Request failed.")

    return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=build_error_payload(f"Invalid request: {exc}"),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=build_error_payload(f"Internal server error: {exc}"),
    )
