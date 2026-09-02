"""zts_stale_reverse_dcf_cash_gap (engineering-findings.yaml).

ZTS's primary cash tag (CashAndCashEquivalentsAtCarryingValue) was never tagged
past FY2018 — confirmed live against data.sec.gov. The committed
`zts_company_facts.json` fixture is trimmed to FY2023-2025 only (same trimmed-
fixture trap this project has hit before) and cannot exercise a FY2019 gap, so
this test injects the real, live-verified FY2019 raw fact directly instead of
widening the fixture: the value, accession and filing date are ZTS's actual
FY2019 10-K, 0001555280-20-000054, filed 2020-02-13, not synthetic.

Story 12.3 (2026-09-01) excluded ZTS from the restricted-cash-inclusive
fallback (CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents),
reasoning from the tag's name plus ZTS's own nonzero RestrictedCashCurrent —
never checked against ZTS's actual overlap-year values. Checked live
2026-09-02: the fallback equals ZTS's primary tag exactly in both years they
overlap (FY2017, FY2018) despite nonzero restricted cash both years, so it was
always safe — the exclusion had been silently freezing ZTS's ENTIRE
reverse-DCF card at FY2017 data. Removed in concepts_v12 (us-gaap_v11.yaml).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.models import CanonicalFact, Filing, RawFact
from canonicalization.canonicalize import canonicalize_issuer
from pipeline.run import run_issuer
from tests.conftest import requires_db

FIXTURES = Path(__file__).parent / "fixtures"
ZTS_CIK = "0001555280"

# ZTS's real FY2019 10-K: accession 0001555280-20-000054, filed 2020-02-13,
# fiscal_year_end 2019-12-31. Confirmed live 2026-09-02 against
# data.sec.gov's company-facts JSON for CIK 0001555280.
_FY2019_ACCESSION = "0001555280-20-000054"
_FY2019_RESTRICTED_INCLUSIVE_CASH = Decimal("1934000000")


async def _inject_fy2019_combined_cash_fact(db_session) -> None:
    db_session.add(
        Filing(
            accession_number=_FY2019_ACCESSION,
            issuer_cik=ZTS_CIK,
            form_type="10-K",
            filing_date=date(2020, 2, 13),
            fiscal_year=2019,
            fiscal_year_end=date(2019, 12, 31),
        )
    )
    db_session.add(
        RawFact(
            accession_number=_FY2019_ACCESSION,
            taxonomy="us-gaap",
            concept="CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            unit="USD",
            period_end=date(2019, 12, 31),
            value=_FY2019_RESTRICTED_INCLUSIVE_CASH,
            source="company_facts",
            content_hash="zts-fy2019-combined-cash",
            fetched_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        )
    )
    await db_session.flush()


@requires_db
async def test_zts_cash_and_equivalents_resolves_for_fy2019_via_the_fallback(db_session) -> None:
    payload = json.loads((FIXTURES / "zts_company_facts.json").read_text())
    await run_issuer(db_session, payload, ticker="ZTS")

    await _inject_fy2019_combined_cash_fact(db_session)
    await canonicalize_issuer(db_session, ZTS_CIK)

    fact = (
        await db_session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == ZTS_CIK,
                CanonicalFact.canonical_concept == "cash_and_equivalents",
                CanonicalFact.fiscal_year == 2019,
                CanonicalFact.superseded.is_(False),
            )
        )
    ).scalars().first()

    assert fact is not None, (
        "FY2019 cash_and_equivalents should now resolve via the restricted-cash-"
        "inclusive fallback — the primary tag never covers this year for ZTS"
    )
    assert fact.value == _FY2019_RESTRICTED_INCLUSIVE_CASH
