"""FastAPI application exposing only the 3D world API."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


from src.paths import load_environment

load_environment()

from src import db
from src.api.observability import (
    REQUEST_ID_HEADER,
    attach_request_id,
    ensure_request_id,
    request_logging_middleware,
    unhandled_exception_handler,
    validation_exception_handler,
)
from src.api.world import router as world_router
from src.api.characters import router as character_router, pipeline_error_handler
from src.api.avatars import router as avatar_router
from src.api.avatar_factory import router as factory_router
from src.api.avatar_standard import router as standard_router
from src.api.avatar_blueprints import router as blueprint_router
from src.api.studio import router as studio_router
from src.services.character_pipeline import PipelineError
from src.auth import is_public_path
from src.runtime_identity import runtime_identity


logger = logging.getLogger(__name__)
_RUNTIME = runtime_identity()


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "*")
    origins = [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]
    return origins or ["*"]


app = FastAPI(
    title="3D Asset API",
    description="3D world asset generation, storage, and delivery",
    version="1.0.0",
)
app.include_router(studio_router, prefix='/api')
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)
app.middleware("http")(request_logging_middleware)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_exception_handler(PipelineError, pipeline_error_handler)


_API_KEY = os.getenv("API_KEY", "").strip()


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    request_id = ensure_request_id(request)
    if not _API_KEY or is_public_path(request.url.path) or request.method == "OPTIONS":
        return await call_next(request)
    key = (request.headers.get("x-api-key") or "").strip()
    if key == _API_KEY:
        return await call_next(request)
    return attach_request_id(
        JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized", "requestId": request_id},
        ),
        request_id,
    )


def health() -> dict:
    database = db.ping()
    status = "healthy"
    if database.get("configured") and not database.get("ok"):
        status = "degraded"
    return {"status": status, "connections": {"database": database}, "runtime": _RUNTIME}


@app.get("/health")
def root_health() -> dict:
    return health()


@app.get("/api/health")
def api_health() -> dict:
    return health()


app.include_router(world_router, prefix="/api")
app.include_router(character_router, prefix="/api")
app.include_router(avatar_router, prefix="/api")
app.include_router(factory_router, prefix="/api")
app.include_router(standard_router, prefix="/api")
app.include_router(blueprint_router, prefix="/api")
