"""Ops 5: SG&A is G&A + selling and marketing, never G&A alone.

The evidence for `sga_general_plus_selling` being an IDENTITY is AAPL, the one
universe filer that files the SG&A total and both parts (its FY2025 10-K began
disaggregating, with comparatives back to FY2023). The facts below are AAPL's
real filed figures, copied from the dev store's company facts, each from the 10-K
that originally filed it. The end-to-end tests run them through real
canonicalization, so the identity is pinned by the engine, not restated as
arithmetic on constants.
"""

from __future__ import annotations

from sqlalchemy import select

from app.models import CanonicalFact
from canonicalization.canonicalize import canonicalize_issuer
from canonicalization.mappings import DERIVATION_RULES, MAPPING_RULES, MAPPING_VERSION, seed_concept_mappings
from ingestion.company_facts import parse_company_facts
from raw_store.repository import persist_company_facts
from tests.conftest import requires_db

CIK = "0000320193"
FY25, FY26 = "0000320193-25-000079", "0000320193-26-000026"
FILINGS = {FY25: (2025, "2025-10-31"), FY26: (2026, "2026-11-03")}
PERIODS = {  # fiscal year -> (start, end)
    2023: ("2022-09-25", "2023-09-30"),
    2024: ("2023-10-01", "2024-09-28"),
    2025: ("2024-09-29", "2025-09-27"),
    2026: ("2025-09-28", "2026-09-26"),
}
# fiscal year -> (accession, G&A, selling and marketing, filed SG&A total)
AAPL = {
    2023: (FY25, 6_672_000_000, 18_260_000_000, 24_932_000_000),
    2024: (FY25, 7_458_000_000, 18_639_000_000, 26_097_000_000),
    2025: (FY25, 8_077_000_000, 19_524_000_000, 27_601_000_000),
    2026: (FY26, 8_640_000_000, 21_134_000_000, 29_774_000_000),
}


def _fact(fy: int, value: int) -> dict:
    accn = AAPL[fy][0]
    filing_fy, filed = FILINGS[accn]
    start, end = PERIODS[fy]
    return {"start": start, "end": end, "val": value, "accn": accn, "fy": filing_fy,
            "fp": "FY", "form": "10-K", "filed": filed}


def _payload(*, parts: bool = True, selling: bool = True, total: bool = False) -> dict:
    concepts: dict[str, list[dict]] = {}
    if parts:
        concepts["GeneralAndAdministrativeExpense"] = [_fact(fy, v[1]) for fy, v in AAPL.items()]
    if parts and selling:
        concepts["SellingAndMarketingExpense"] = [_fact(fy, v[2]) for fy, v in AAPL.items()]
    if total:
        concepts["SellingGeneralAndAdministrativeExpense"] = [_fact(fy, v[3]) for fy, v in AAPL.items()]
    return {
        "cik": int(CIK),
        "entityName": "Apple Inc.",
        "facts": {"us-gaap": {c: {"label": c, "units": {"USD": f}} for c, f in concepts.items()}},
    }


async def _sga_rows(db_session, payload: dict) -> dict[int, CanonicalFact]:
    parsed = parse_company_facts(payload)
    await persist_company_facts(db_session, parsed, ticker="AAPL")
    await seed_concept_mappings(db_session)
    await canonicalize_issuer(db_session, CIK)
    rows = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == CIK,
                CanonicalFact.canonical_concept == "sga",
                CanonicalFact.mapping_version == MAPPING_VERSION,
                CanonicalFact.superseded.is_(False),
            )
        )
    ).scalars().all()
    return {r.fiscal_year: r for r in rows}


def test_the_rule_is_a_declared_identity_over_the_two_parts() -> None:
    rule = next((r for r in DERIVATION_RULES if r.rule == "sga_general_plus_selling"), None)
    assert rule is not None
    assert rule.canonical_concept == "sga"
    assert rule.operation == "add"
    assert list(rule.operands) == ["general_and_administrative", "selling_and_marketing"]
    assert rule.provenance_from == "general_and_administrative"


def _us_gaap_sources(concept: str) -> list[str]:
    return [r.source_concept for r in MAPPING_RULES if r.canonical_concept == concept and r.source_taxonomy == "us-gaap"]


def test_g_and_a_alone_is_never_a_source_of_sga() -> None:
    """The v19 defect, pinned shut: G&A as an sga fallback gave CPB, OTEX, SHOP
    and MSFT part of SG&A, and QSR a different concept altogether."""
    assert _us_gaap_sources("sga") == ["SellingGeneralAndAdministrativeExpense"]
    assert _us_gaap_sources("general_and_administrative") == ["GeneralAndAdministrativeExpense"]


def test_advertising_is_never_summed_into_sga() -> None:
    """AdvertisingExpense is a note disclosure INSIDE selling and marketing at AAPL
    and MSFT; adding it would double count."""
    assert _us_gaap_sources("selling_and_marketing") == ["SellingAndMarketingExpense"]
    for concept in ("sga", "general_and_administrative", "selling_and_marketing"):
        assert "AdvertisingExpense" not in _us_gaap_sources(concept)


@requires_db
async def test_the_derivation_reproduces_aapls_filed_total_in_every_year(db_session) -> None:
    rows = await _sga_rows(db_session, _payload(parts=True, total=False))
    assert sorted(rows) == [2023, 2024, 2025, 2026], "every year must derive"
    for fy, row in rows.items():
        assert row.derivation == "sga_general_plus_selling"
        assert int(row.value) == AAPL[fy][3], f"FY{fy}: G&A + S&M must equal AAPL's filed SG&A total"


@requires_db
async def test_a_filed_total_wins_over_the_derivation(db_session) -> None:
    """AAPL's real situation: total and parts both filed. The filed line is used and
    nothing is derived (a derivation never overrides a filed value)."""
    rows = await _sga_rows(db_session, _payload(parts=True, total=True))
    assert sorted(rows) == [2023, 2024, 2025, 2026]
    assert all(r.derivation is None for r in rows.values())
    assert {fy: int(r.value) for fy, r in rows.items()} == {fy: v[3] for fy, v in AAPL.items()}


@requires_db
async def test_g_and_a_without_selling_resolves_no_sga(db_session) -> None:
    """QSR's shape: G&A with no selling line is not SG&A, so nothing resolves."""
    rows = await _sga_rows(db_session, _payload(parts=True, selling=False, total=False))
    # Positive control first: canonicalization DID run and resolved the G&A operand,
    # so the empty sga result below is a finding, not a pipeline that did nothing.
    ga = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == CIK,
                CanonicalFact.canonical_concept == "general_and_administrative",
                CanonicalFact.superseded.is_(False),
            )
        )
    ).scalars().all()
    assert len(ga) == 4
    assert rows == {}
