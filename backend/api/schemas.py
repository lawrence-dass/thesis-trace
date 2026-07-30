"""Read-API response schemas (Pydantic). Presentation-agnostic; the frontend
renders exactly what these carry (AD-8). Provenance travels with every value (AD-19)."""

from __future__ import annotations

from pydantic import BaseModel


class Provenance(BaseModel):
    accession_number: str
    canonical_concept: str
    fiscal_year: int
    period_end: str | None
    source_filing_form: str | None = None
    # None = the figure is a filed XBRL tag in that accession. A value names the
    # rule ThesisTrace used to COMPUTE it from other canonical facts (e.g.
    # "assets_minus_equity"). Consumers must not present a derived figure as
    # though a line item in the filing states it (FR-8, AD-19).
    derivation: str | None = None


class SignalOut(BaseModel):
    signal_key: str
    status: str  # pass | fail | insufficient_data
    value: float | None
    band_label: str | None
    provenance: list[Provenance]


class LensScoreOut(BaseModel):
    model: str
    category: str  # quality_health | integrity
    fiscal_year: int
    formula_version: str
    aggregate_value: float | None
    band_label: str | None
    applicability: str
    signals: list[SignalOut]


class DataQualityOut(BaseModel):
    issue_type: str
    status: str
    raised_by: str
    accession_number: str | None
    detail: dict | None


class VerdictItem(BaseModel):
    """One model's own published, cited classification — never blended (AD-12)."""

    model: str
    category: str
    fiscal_year: int
    aggregate_value: float | None
    band_label: str | None
    applicability: str
    # Which of the model's own sub-signals are insufficient_data for this
    # fiscal year — populated only when aggregate_value is None so the UI can
    # explain WHY a score didn't compute (e.g. "missing gmi, sgai") rather than
    # showing a bare dash with no reason (AD-16 tri-state, surfaced not hidden).
    missing_signals: list[str] = []


class CompanyOverviewOut(BaseModel):
    cik: str
    ticker: str
    name: str
    lenses_live: list[str]
    lenses_pending: list[str]
    verdict: list[VerdictItem]
    scores: list[LensScoreOut]
    data_quality: list[DataQualityOut]


class CompanyCardOut(BaseModel):
    cik: str
    ticker: str
    name: str
    last_updated: str | None
