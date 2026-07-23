"""Story 1.3 — ingestion parse + idempotent append (AD-2, AD-4, AD-9). Fixture-only."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from app.models import Filing, Issuer, RawFact
from ingestion.company_facts import parse_company_facts, zero_pad_cik
from raw_store.repository import persist_company_facts
from tests.conftest import requires_db

FIXTURE = Path(__file__).parent / "fixtures" / "shop_company_facts.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_parse_extracts_annual_facts_only() -> None:
    parsed = parse_company_facts(_payload())
    assert parsed.cik == "0001594805"
    assert parsed.entity_name == "Shopify Inc."
    # Two 10-K filings (FY2023, FY2024) in the fixture.
    assert len(parsed.filings) == 2
    # Every parsed fact is annual and carries a content hash.
    assert parsed.facts
    assert all(f.content_hash for f in parsed.facts)
    concepts = {f.concept for f in parsed.facts}
    assert {"Assets", "NetIncomeLoss", "EntityCommonStockSharesOutstanding"}.issubset(concepts)


def test_zero_pad_cik() -> None:
    assert zero_pad_cik(1594805) == "0001594805"


def test_fiscal_year_end_ignores_dei_cover_page_dates() -> None:
    """Regression guard: a dei cover-page fact (e.g. shares-outstanding-as-of-
    filing-date) commonly carries an `end` date *after* the filing's real
    fiscal-year-end — confirmed live 2026-07-22/23 against CP's actual FY2025
    10-K (dei end=2026-02-25, real FYE=2025-12-31). Since dei sorts before
    us-gaap in the real payload and a naive parse takes whichever entry it
    sees first (or even the max end across ALL taxonomies), this can silently
    misdate `fiscal_year_end` by ~2 months — corrupting every Tiingo/FX price
    lookup keyed off it. The parser must derive fiscal_year_end from us-gaap
    facts only."""
    payload = {
        "cik": 1,
        "entityName": "Test Co",
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "end": "2026-02-25",  # filing-date-dated, LATER than the real FYE
                                "val": 100,
                                "accn": "0000000000-26-000001",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-26",
                            }
                        ]
                    }
                }
            },
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "end": "2025-12-31",  # the real fiscal-year-end
                                "val": 1000,
                                "accn": "0000000000-26-000001",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-26",
                            }
                        ]
                    }
                }
            },
        },
    }
    parsed = parse_company_facts(payload)
    filing = parsed.filings["0000000000-26-000001"]
    assert filing.fiscal_year == 2025
    assert filing.fiscal_year_end == "2025-12-31"  # not 2026-02-25


@requires_db
async def test_persist_is_idempotent(db_session) -> None:
    parsed = parse_company_facts(_payload())

    first = await persist_company_facts(db_session, parsed, ticker="SHOP")
    assert first["raw_facts_added"] > 0
    assert first["filings_added"] == 2

    total_after_first = (await db_session.execute(select(func.count()).select_from(RawFact))).scalar_one()

    # Re-ingest the same payload — no new rows (AD-2/AD-9 replayable idempotency).
    second = await persist_company_facts(db_session, parsed, ticker="SHOP")
    assert second["raw_facts_added"] == 0
    assert second["filings_added"] == 0

    total_after_second = (await db_session.execute(select(func.count()).select_from(RawFact))).scalar_one()
    assert total_after_first == total_after_second

    issuer = await db_session.get(Issuer, "0001594805")
    assert issuer is not None and issuer.ticker == "SHOP"
    filings = (await db_session.execute(select(Filing))).scalars().all()
    assert {f.fiscal_year for f in filings} == {2023, 2024}
