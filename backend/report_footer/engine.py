"""Provenance and freshness footer (Story 10.6, D12).

Pure assembly over already-resolved values — no query, no ThesisTrace
classification, unlike `rewards_risks` or `debt`. There is no versioned
presentation-rule spec here because nothing in this module originates a
judgment: every field is either read straight from stored data or a
structural presence check (does this issuer have a MarketPrice row at all).

The one rule worth pinning with a test: A SOURCE THE FILER DOES NOT USE IS
ABSENT, NEVER LISTED GENERICALLY (the story's own AC wording). `sources` is
built by APPENDING only when the caller's own flag says the source was
actually used — never by listing all three and marking one "not used" — so
there is no path that could silently list Bank of Canada FX for a USD
reporter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class DataSource:
    name: str
    detail: str | None = None


@dataclass(frozen=True)
class FormulaVersion:
    model: str
    version: str


@dataclass(frozen=True)
class ReportFooter:
    sources: list[DataSource]
    latest_accession_number: str | None
    latest_filing_date: date | None
    latest_filing_form: str | None
    last_pipeline_run: datetime | None
    mapping_version: str
    formula_versions: list[FormulaVersion]


def build_report_footer(
    *,
    latest_accession_number: str | None,
    latest_filing_date: date | None,
    latest_filing_form: str | None,
    has_market_price: bool,
    uses_cad: bool,
    last_pipeline_run: datetime | None,
    mapping_version: str,
    formula_versions: list[FormulaVersion],
) -> ReportFooter:
    """Assemble the footer from values the caller has already resolved.

    `has_market_price` and `uses_cad` are presence checks the caller makes
    against stored rows (a MarketPrice existence query; any fetched
    canonical fact reporting in CAD) — this function only decides how those
    checks translate into the sources list, never whether to query for them.
    """
    sources = [DataSource(name="SEC EDGAR company facts")]
    if has_market_price:
        sources.append(DataSource(name="Tiingo market close"))
    if uses_cad:
        sources.append(DataSource(name="Bank of Canada FX", detail="USD/CAD"))

    return ReportFooter(
        sources=sources,
        latest_accession_number=latest_accession_number,
        latest_filing_date=latest_filing_date,
        latest_filing_form=latest_filing_form,
        last_pipeline_run=last_pipeline_run,
        mapping_version=mapping_version,
        formula_versions=formula_versions,
    )
