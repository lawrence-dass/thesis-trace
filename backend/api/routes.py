"""Public read-only endpoints (AD-10). All errors use the standard envelope;
a company outside the universe / with no scores yet returns a success-envelope
`not_available` state, never an error or a fabricated zero."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api import repository
from api.deps import get_session
from explanation.llm import polish, rewrite_enabled
from explanation.methodology import get_methodology
from explanation.template import build_explanations

router = APIRouter(prefix="/api", tags=["read"])


@router.get("/companies")
async def companies(session: AsyncSession = Depends(get_session)):
    return await repository.list_companies(session)


@router.get("/companies/{ticker}/overview")
async def company_overview(ticker: str, session: AsyncSession = Depends(get_session)):
    overview = await repository.get_company_overview(session, ticker)
    if overview is None:
        # Honest coverage: not an error, not a fabricated result.
        return JSONResponse(
            status_code=200,
            content={"state": "not_available", "ticker": ticker.upper(), "message": "Company not yet covered."},
        )
    return {"state": "ok", **overview.model_dump()}


@router.get("/companies/{ticker}/changes")
async def company_changes(
    ticker: str,
    since: datetime | None = None,
    session: AsyncSession = Depends(get_session),
):
    """What moved for a company (FR-22).

    `since` is an optional ISO-8601 instant. Omitted, it defaults to when the
    most recent filing was ingested, so the endpoint answers "what did the
    latest filing change?" — see `repository.get_company_changes` for why that
    beats comparing against the immediately-superseded run.

    CALLER NOTE: a `+00:00` offset must be percent-encoded (`%2B00:00`), because
    a bare `+` in a query string decodes to a space and the timestamp then fails
    to parse. JavaScript's `toISOString()` emits the `Z` form and is unaffected;
    Python's `datetime.isoformat()` emits the `+00:00` form and is. The request
    is rejected with 422 rather than silently falling back to the default pivot,
    which would answer a different question than the caller asked.

    Read-only (AD-1): nothing on this path can trigger scoring or ingestion.
    """
    changes = await repository.get_company_changes(session, ticker, since)
    if changes is None:
        return JSONResponse(
            status_code=200,
            content={"state": "not_available", "ticker": ticker.upper(), "message": "Company not yet covered."},
        )
    return {"state": "ok", **changes.model_dump()}


@router.get("/methodology/{model}")
async def methodology(model: str):
    meta = get_methodology(model.lower())
    if meta is None:
        return JSONResponse(status_code=200, content={"state": "not_available", "model": model})
    return {"state": "ok", **meta}


@router.get("/companies/{ticker}/explanation")
async def explanation(ticker: str, polish_text: bool = False, session: AsyncSession = Depends(get_session)):
    overview = await repository.get_company_overview(session, ticker)
    if overview is None:
        return JSONResponse(status_code=200, content={"state": "not_available", "ticker": ticker.upper()})
    lenses = build_explanations(overview)
    out = []
    for lens in lenses:
        text = await polish(lens.text) if polish_text else lens.text
        out.append({"model": lens.model, "text": text, "citations": lens.citations})
    return {"state": "ok", "ticker": overview.ticker, "llm_rewrite": rewrite_enabled() and polish_text, "explanations": out}
