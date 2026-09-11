"""Live SEC EDGAR client (AD-9).

Live network fetches are not exercised in the test suite because they would hit
SEC's servers. Tests use committed fixtures via `company_facts.parse_company_facts`
and mocked responses for the request-policy behavior.
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
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_nodash}/index.json"
ARCHIVE_FILE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_nodash}/{filename}"
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


async def _fetch_json(url: str, *, max_retries: int = 3) -> dict:
    """Shared JSON GET with AD-9 throttle + backoff."""
    headers = {"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate"}
    delay = 1.0
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
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


async def _fetch_text(url: str, *, max_retries: int = 3) -> str:
    """Shared text GET with the same throttle + backoff as JSON requests."""
    headers = {"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate"}
    delay = 1.0
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        for attempt in range(1, max_retries + 1):
            await _throttle()
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code in (429, 503) and attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
    raise RuntimeError(f"EDGAR fetch failed after {max_retries} attempts: {url}")


async def fetch_submissions(cik: str, *, max_retries: int = 3) -> dict:
    """Filing history for a zero-padded CIK (form types, accessions, dates)."""
    return await _fetch_json(SUBMISSIONS_URL.format(cik=str(cik).zfill(10)), max_retries=max_retries)


def latest_annual_original(submissions: dict, *, form_type: str = "10-K") -> tuple[str, str]:
    """Return (accession_number, filing_date) of the newest ORIGINAL annual filing.

    Matches `form` EXACTLY and orders by filing date, never by accession number.

    `max(accession_number)` over `form LIKE '10-K%'` returns the 10-K/A, whose
    XBRL instance carries only the amended portion — typically 12-13 KB with ~7
    contexts, which is visually indistinguishable from a failed download and
    makes a filer look like it reports no segments or intangibles at all. That
    trap bit twice in one session on 2026-09-08 (SHOP and CP); SHOP's
    0001594805-26-000011 is an amendment while its real 10-K is
    0001594805-26-000007. Recorded in `acquisition_epic_scoped_to_us_gaap_filers`
    and in project-context.md's anti-patterns.
    """
    recent = submissions["filings"]["recent"]
    candidates = [
        (accn, filed)
        for accn, form, filed in zip(
            recent["accessionNumber"], recent["form"], recent["filingDate"], strict=True
        )
        if form == form_type  # EXACT — '10-K/A' must not match
    ]
    if not candidates:
        raise RuntimeError(f"no original {form_type} found in recent submissions")
    return max(candidates, key=lambda c: c[1])


async def fetch_instance_document(cik: str, accession_number: str, *, max_retries: int = 3) -> str:
    """Fetch a filing's Inline XBRL instance document as text (AD-4).

    Resolves the instance from the filing's own index rather than guessing the
    filename: the convention is `<ticker>-<yyyymmdd>_htm.xml`, but the ticker
    stem is the filer's choice and the date is the period end, not the filing
    date, so constructing it is a guess that fails silently.
    """
    cik_int = str(int(cik))
    accn_nodash = accession_number.replace("-", "")
    index = await _fetch_json(
        FILING_INDEX_URL.format(cik_int=cik_int, accn_nodash=accn_nodash), max_retries=max_retries
    )
    names = [item["name"] for item in index["directory"]["item"]]
    instances = [n for n in names if n.endswith("_htm.xml")]
    if not instances:
        raise RuntimeError(f"no Inline XBRL instance in {accession_number} (files: {len(names)})")
    url = ARCHIVE_FILE_URL.format(cik_int=cik_int, accn_nodash=accn_nodash, filename=instances[0])
    return await _fetch_text(url, max_retries=max_retries)
