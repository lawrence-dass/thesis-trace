"""Public read-only endpoints (AD-10). All errors use the standard envelope;
a company outside the universe / with no scores yet returns a success-envelope
`not_available` state, never an error or a fabricated zero."""

from __future__ import annotations

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
