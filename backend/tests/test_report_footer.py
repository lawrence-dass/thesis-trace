"""Story 10.6 — provenance and freshness footer (D12).

No versioned presentation-rule spec backs this module (unlike rewards_risks
or debt), since nothing here is a ThesisTrace classification — every field is
either read straight from stored data or a structural presence check. The
one rule worth pinning: a source the filer does not use is ABSENT, never
listed generically (the story's own AC wording) — tested from both
directions so a future edit can't silently start showing an unused source.
"""

from __future__ import annotations

from datetime import date, datetime

from report_footer.engine import FormulaVersion, build_report_footer


def _footer(**overrides):
    defaults = dict(
        latest_accession_number="0001-25-000001",
        latest_filing_date=date(2026, 2, 27),
        latest_filing_form="10-K",
        has_market_price=False,
        uses_cad=False,
        last_pipeline_run=datetime(2026, 8, 27, 6, 0, 0),
        mapping_version="concepts_v9",
        formula_versions=[FormulaVersion(model="piotroski", version="piotroski_v1")],
    )
    defaults.update(overrides)
    return build_report_footer(**defaults)


def test_edgar_is_always_present_for_a_covered_issuer() -> None:
    footer = _footer(has_market_price=False, uses_cad=False)
    names = [s.name for s in footer.sources]
    assert names == ["SEC EDGAR company facts"]


def test_tiingo_appears_only_when_a_market_price_row_exists() -> None:
    with_price = _footer(has_market_price=True)
    without_price = _footer(has_market_price=False)
    assert "Tiingo market close" in [s.name for s in with_price.sources]
    assert "Tiingo market close" not in [s.name for s in without_price.sources]


def test_bank_of_canada_fx_appears_only_for_a_cad_reporting_filer() -> None:
    cad_filer = _footer(uses_cad=True)
    usd_filer = _footer(uses_cad=False)
    assert "Bank of Canada FX" in [s.name for s in cad_filer.sources]
    assert "Bank of Canada FX" not in [s.name for s in usd_filer.sources]


def test_a_usd_filer_never_lists_a_source_it_does_not_use() -> None:
    # The AC's own wording: absent, not listed generically as "not used".
    footer = _footer(has_market_price=False, uses_cad=False)
    assert len(footer.sources) == 1
    assert footer.sources[0].name == "SEC EDGAR company facts"


def test_a_cad_filer_with_a_market_price_lists_all_three_sources() -> None:
    footer = _footer(has_market_price=True, uses_cad=True)
    names = {s.name for s in footer.sources}
    assert names == {"SEC EDGAR company facts", "Tiingo market close", "Bank of Canada FX"}


def test_absent_latest_filing_carries_through_as_none_not_a_default() -> None:
    footer = _footer(
        latest_accession_number=None, latest_filing_date=None, latest_filing_form=None
    )
    assert footer.latest_accession_number is None
    assert footer.latest_filing_date is None
    assert footer.latest_filing_form is None


def test_no_pipeline_run_ever_recorded_is_none_not_a_fabricated_date() -> None:
    footer = _footer(last_pipeline_run=None)
    assert footer.last_pipeline_run is None


def test_formula_versions_and_mapping_version_pass_through_unmodified() -> None:
    versions = [
        FormulaVersion(model="piotroski", version="piotroski_v1"),
        FormulaVersion(model="altman", version="altman_v1"),
    ]
    footer = _footer(mapping_version="concepts_v9", formula_versions=versions)
    assert footer.mapping_version == "concepts_v9"
    assert footer.formula_versions == versions
