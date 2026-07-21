"""Live SEC EDGAR client (AD-9).

NOT exercised in the test suite — a live fetch requires network and would hit
SEC's servers. Tests use committed fixtures via `company_facts.parse_company_facts`.
Enforces SEC fair-access discipline: identifying User-Agent, <=10 req/s, retry
with backoff. Ingestion is replayable and made idempotent downstream by
(accession_number, content_hash) in raw_store (AD-2, AD-9).
"""

from __future__ import annotations

import asyncio
import time

import httpx

from app.config import get_settings

COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_MIN_INTERVAL_SECONDS = 0.15  # <= ~6-7 req/s, safely under SEC's 10 req/s ceiling (AD-9)
_last_request_ts = 0.0


async def _throttle() -> None:
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < _MIN_INTERVAL_SECONDS:
        await asyncio.sleep(_MIN_INTERVAL_SECONDS - elapsed)
    _last_request_ts = time.monotonic()


def _user_agent() -> str:
    contact = get_settings().edgar_contact
    if not contact:
        raise RuntimeError("EDGAR_CONTACT env var is required for SEC fair-access (AD-9).")
    return contact


async def fetch_company_facts(cik: str, *, max_retries: int = 3) -> dict:
    """Fetch the Company Facts JSON for a zero-padded CIK, with throttle + backoff."""
    url = COMPANY_FACTS_URL.format(cik=str(cik).zfill(10))
    headers = {"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate"}
    delay = 1.0
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(1, max_retries + 1):
            await _throttle()
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 503) and attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
    raise RuntimeError(f"EDGAR fetch failed after {max_retries} attempts: {url}")
