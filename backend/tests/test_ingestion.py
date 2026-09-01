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


def test_fiscal_year_end_ignores_a_subsequent_event_us_gaap_fact() -> None:
    """Regression guard: confirmed live 2026-09-01 against CPB's real FY2011 10-K
    (accn 0000950123-11-087197). A us-gaap, fp='FY' fact can still carry an `end`
    date AFTER the real fiscal-year-end without being dei — CPB tags
    LineOfCreditFacilityMaximumBorrowingCapacity at end=2011-09-30 (a financing
    disclosure dated near the filing date), two months after its real FYE of
    2011-07-31, which every other tagged concept on the same accession shares.
    The dei exclusion alone does not catch this; the parser must prefer the `end`
    date shared by the most us-gaap facts, not simply the latest one."""
    payload = {
        "cik": 1,
        "entityName": "Test Co",
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "end": "2011-07-31",  # the real fiscal-year-end
                                "val": 1000,
                                "accn": "0000000000-11-000001",
                                "fy": 2011,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2011-09-28",
                            }
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "end": "2011-07-31",
                                "val": 100,
                                "accn": "0000000000-11-000001",
                                "fy": 2011,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2011-09-28",
                            }
                        ]
                    }
                },
                "LineOfCreditFacilityMaximumBorrowingCapacity": {
                    "units": {
                        "USD": [
                            {
                                "end": "2011-09-30",  # subsequent-event disclosure, LATER than the real FYE
                                "val": 2000000000,
                                "accn": "0000000000-11-000001",
                                "fy": 2011,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2011-09-28",
                            }
                        ]
                    }
                },
            },
        },
    }
    parsed = parse_company_facts(payload)
    filing = parsed.filings["0000000000-11-000001"]
    assert filing.fiscal_year == 2011
    assert filing.fiscal_year_end == "2011-07-31"  # not 2011-09-30


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


# --- Multi-regime support: 40-F / ifrs-full (see canonicalization.taxonomies) ---


def _ifrs_payload() -> dict:
    """Minimal 40-F / ifrs-full payload shaped like a real Canadian MJDS filer.

    Mirrors the structure verified live 2026-07-29 against Cameco/BCE/Suncor:
    a single `ifrs-full` taxonomy, form "40-F", plus a `dei` cover-page fact
    dated to the FILING date to prove that exclusion still holds cross-regime.
    """
    return {
        "cik": 1009001,
        "entityName": "CAMECO CORPORATION",
        "facts": {
            "ifrs-full": {
                "Assets": {
                    "units": {
                        "CAD": [
                            {"fy": 2024, "fp": "FY", "form": "40-F", "accn": "0001009001-25-000001",
                             "end": "2024-12-31", "filed": "2025-02-20", "val": 9_000_000_000, "decimals": -3},
                            {"fy": 2023, "fp": "FY", "form": "40-F", "accn": "0001009001-24-000001",
                             "end": "2023-12-31", "filed": "2024-02-22", "val": 8_000_000_000, "decimals": -3},
                        ]
                    }
                },
                "ProfitLoss": {
                    "units": {
                        "CAD": [
                            {"fy": 2024, "fp": "FY", "form": "40-F", "accn": "0001009001-25-000001",
                             "start": "2024-01-01", "end": "2024-12-31", "filed": "2025-02-20",
                             "val": 500_000_000, "decimals": -3},
                        ]
                    }
                },
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            # Dated to the FILING date, deliberately AFTER the FYE.
                            {"fy": 2024, "fp": "FY", "form": "40-F", "accn": "0001009001-25-000001",
                             "end": "2025-02-20", "filed": "2025-02-20", "val": 435_000_000, "decimals": 0},
                        ]
                    }
                }
            },
        },
    }


def test_parse_accepts_40f_ifrs_full_filings() -> None:
    """40-F / ifrs-full facts are ingested, not silently dropped."""
    parsed = parse_company_facts(_ifrs_payload())
    assert parsed.cik == "0001009001"
    assert len(parsed.filings) == 2
    assert {f.form_type for f in parsed.filings.values()} == {"40-F"}
    taxonomies = {f.taxonomy for f in parsed.facts}
    assert "ifrs-full" in taxonomies


def test_dei_cover_page_exclusion_holds_for_ifrs_regime_too() -> None:
    """The `dei` exclusion is regime-agnostic.

    A cover-page fact dated to the filing date (2025-02-20) must not become the
    filing's fiscal_year_end — the same bug class that made SHOP's FY2024 read as
    2023-12-31 and CP's FY2025 as 2026-02-25 under us-gaap.
    """
    parsed = parse_company_facts(_ifrs_payload())
    fy2024 = next(f for f in parsed.filings.values() if f.fiscal_year == 2024)
    assert fy2024.fiscal_year_end == "2024-12-31"  # not the 2025-02-20 filing date
