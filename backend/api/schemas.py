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
    # Why the caveat applies, when applicability is computed_with_caveat.
    caveat_reason: str | None = None


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


# --- Change detection (FR-22, Story 5.3) ---------------------------------


class ChangeProvenance(BaseModel):
    """Provenance for one ENDPOINT of a change.

    Separate from `Provenance` above because a change endpoint's accession can
    legitimately be absent — a value that did not exist at the prior endpoint
    has nothing to cite — whereas `Provenance` requires one.
    """

    accession_number: str | None
    canonical_concept: str | None = None
    fiscal_year: int | None = None
    period_end: str | None = None
    source_filing_form: str | None = None
    derivation: str | None = None


class SignalChangeOut(BaseModel):
    kind: str
    signal_key: str
    prior_status: str | None
    current_status: str | None
    prior_value: float | None
    current_value: float | None
    prior_band_label: str | None = None
    current_band_label: str | None = None


class FactChangeOut(BaseModel):
    kind: str
    signal_key: str
    canonical_concept: str
    prior_value: float | None
    current_value: float | None
    prior_provenance: ChangeProvenance | None
    current_provenance: ChangeProvenance | None


class DataQualityChangeOut(BaseModel):
    kind: str
    issue_type: str
    status: str
    raised_by: str
    accession_number: str | None
    detail: dict | None


class RunChangeOut(BaseModel):
    model: str
    fiscal_year: int
    #: Every kind of movement in this run. A band crossing and a within-band
    #: value move are distinct entries, never collapsed (FR-22).
    kinds: list[str]
    prior_accession_number: str | None
    current_accession_number: str
    prior_aggregate: float | None
    current_aggregate: float | None
    prior_band_label: str | None
    current_band_label: str | None
    prior_applicability: str | None
    current_applicability: str | None
    signal_changes: list[SignalChangeOut] = []
    fact_changes: list[FactChangeOut] = []
    #: Set when the two endpoints span a formula/mapping version change, meaning
    #: a moved number may be OUR doing rather than the company's.
    version_caveat: str | None = None


class CompanyChangesOut(BaseModel):
    cik: str
    ticker: str
    name: str
    since: str
    #: "explicit" when the caller passed `since`; "latest_filing" when defaulted
    #: to the instant before the most recent filing landed.
    since_basis: str
    since_accession: str | None = None
    #: Three-way and deliberately not a boolean. "no_prior_state" (nothing to
    #: compare against) must never render like "no_change" (compared, nothing
    #: moved), and neither may look like a failed load (FR-22).
    comparison_state: str  # changes | no_change | no_prior_state
    run_changes: list[RunChangeOut] = []
    data_quality_changes: list[DataQualityChangeOut] = []
