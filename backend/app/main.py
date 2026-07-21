"""FastAPI read-only query API entrypoint (AD-1, AD-10).

Phase-1 skeleton: exposes health checks only. Domain endpoints arrive in later
stories. All errors use the single documented envelope
`{error: {code, message, details}}` (ARCHITECTURE-SPINE.md Consistency Conventions).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import get_sessionmaker

app = FastAPI(title="ThesisTrace API", version="0.1.0")

# Public read-only endpoints (registered at import; DB access is per-request).
from api.routes import router as read_router  # noqa: E402

app.include_router(read_router)


def error_response(status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    """Build the single documented error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    return error_response(500, "internal_error", "An unexpected error occurred.", {"type": type(exc).__name__})


@app.get("/health")
async def health() -> dict:
    """Liveness check — no dependencies, always 200 when the app is up."""
    return {"status": "ok"}


@app.get("/health/db", response_model=None)
async def health_db() -> JSONResponse | dict:
    """Readiness check — proves the Supabase Postgres connection with SELECT 1 (AD-10 read-only)."""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        return error_response(503, "db_unconfigured", "DATABASE_URL is not configured.")
    try:
        async with sessionmaker() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — surface any connectivity failure as 503, never crash
        return error_response(503, "db_unavailable", "Database is unreachable.", {"type": type(exc).__name__})
    return {"status": "ok", "db": "ok"}
