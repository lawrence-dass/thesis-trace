"""Story 10.7 — a real defect found live during full-universe verification.

BCE's Piotroski FY2025 card (score 6, "Middle") rendered an expandable
explanation reading "...for FY2015 is 0.0 — classified Weak." — a different
fiscal year's text entirely. Root cause: `build_explanations` already
produced one `LensExplanation` per (model, fiscal_year) — every scored year,
not just the latest — but neither the dataclass nor the API response exposed
`fiscal_year`, so the frontend's `Map` keyed by model alone silently kept
only the last-iterated year's explanation and applied it to every card of
that model. These tests pin the data shape the frontend fix depends on:
each scored year gets its OWN, distinct explanation, and it is addressable
by fiscal year.
"""

from __future__ import annotations

from api.schemas import (
    CompanyOverviewOut,
    DataSourceOut,
    LensScoreOut,
    ReportFooterOut,
)
from explanation.template import build_explanations

_FOOTER = ReportFooterOut(
    sources=[DataSourceOut(name="SEC EDGAR company facts")],
    latest_accession_number=None,
    latest_filing_date=None,
    latest_filing_form=None,
    last_pipeline_run=None,
    mapping_version="concepts_v9",
    formula_versions=[],
)


def _lens(fiscal_year: int, aggregate_value: float, band_label: str) -> LensScoreOut:
    return LensScoreOut(
        model="piotroski",
        category="quality_health",
        fiscal_year=fiscal_year,
        formula_version="piotroski_v1",
        aggregate_value=aggregate_value,
        band_label=band_label,
        applicability="computed",
        signals=[],
    )


def _overview(scores: list[LensScoreOut]) -> CompanyOverviewOut:
    return CompanyOverviewOut(
        cik="0000000001",
        ticker="TEST",
        name="Test Co",
        lenses_live=["piotroski"],
        lenses_pending=[],
        verdict=[],
        scores=scores,
        data_quality=[],
        footer=_FOOTER,
    )


def test_each_scored_year_gets_its_own_explanation_carrying_its_own_fiscal_year() -> None:
    overview = _overview([_lens(2025, 6.0, "Middle"), _lens(2015, 0.0, "Weak")])
    lenses = build_explanations(overview)

    assert len(lenses) == 2
    by_year = {lens.fiscal_year: lens for lens in lenses}
    assert by_year[2025].fiscal_year == 2025
    assert by_year[2015].fiscal_year == 2015


def test_a_later_years_explanation_never_describes_an_earlier_years_figures() -> None:
    """The exact defect found live on BCE: the FY2025 card must never show
    FY2015's value or band in its explanation text, and vice versa."""
    overview = _overview([_lens(2025, 6.0, "Middle"), _lens(2015, 0.0, "Weak")])
    by_year = {lens.fiscal_year: lens for lens in build_explanations(overview)}

    assert "FY2025" in by_year[2025].text
    assert "6.0" in by_year[2025].text
    assert "Middle" in by_year[2025].text
    assert "FY2015" not in by_year[2025].text
    assert "Weak" not in by_year[2025].text

    assert "FY2015" in by_year[2015].text
    assert "0.0" in by_year[2015].text
    assert "Weak" in by_year[2015].text
    assert "FY2025" not in by_year[2015].text
