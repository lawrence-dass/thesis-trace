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


class TrajectoryOut(BaseModel):
    """Direction of travel for an already-computed score.

    A ThesisTrace presentation rule (PRD OQ9), NOT part of the academic model —
    `attribution` carries that statement and is displayed wherever a direction
    is. Shown alongside the level, never instead of it, and never blended in.
    """

    direction: str  # improving | stable | deteriorating | insufficient_history
    label: str
    from_fiscal_year: int | None
    to_fiscal_year: int
    from_value: float | None
    to_value: float | None
    attribution: str
    spec_version: str


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
    # Direction of travel vs the immediately preceding fiscal year (Story 5.5).
    # None only if the rule could not be applied at all.
    trajectory: TrajectoryOut | None = None


class NearTermDebtShareOut(BaseModel):
    """Share of long-term debt falling due within twelve months (Story 5.6).

    A ThesisTrace presentation rule, not a model — it sits alongside the scores and
    is never blended into one, which is why it is its own field rather than another
    entry in `scores`.
    """

    fiscal_year: int
    #: None exactly when insufficient_data. A genuinely filed zero is 0.0, not None
    #: (Cameco reports exactly zero in four fiscal years).
    share: float | None
    band_label: str
    tone: str | None
    near_term_debt: float | None
    total_debt: float | None
    insufficient_data: bool
    #: Travels with the figure so the UI cannot render the bands without saying
    #: whose judgment they are, and states the short-term-borrowings exclusion.
    attribution: str
    spec_version: str


class MaturityBucketOut(BaseModel):
    canonical_concept: str
    label: str
    value: float
    #: Provenance (AD-19).
    accession_number: str
    fiscal_year: int


class MaturityProfileOut(BaseModel):
    """A filer's own published year-by-year repayment schedule (Story 5.7).

    Deliberately carries NO total and no share-of-total. These buckets are
    undiscounted contractual principal and do not reconcile to `total_debt`,
    which is a carrying amount — QSR FY2023's complete ladder sums to 13,043M
    against a filed 12,921M. Offering a total here would invite the stacked-bar
    rendering that asserts a reconciliation which does not hold.
    """

    fiscal_year: int
    buckets: list[MaturityBucketOut]
    #: True when no "after year 5" figure was published, so this is part of the debt.
    truncated: bool
    truncation_message: str | None
    #: The filer's own currency — CP reports in CAD and these are absolute amounts.
    unit: str
    attribution: str
    spec_version: str


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


class ReverseDcfOperandOut(BaseModel):
    """One input to the reverse DCF, with enough to recompute and to cite it.

    Closes risk-assessment finding 3.5 for this feature: a reader can reconstruct
    enterprise value and free cash flow from the response rather than taking the
    engine's word for them.
    """

    name: str
    value: float
    #: Provenance (AD-19). Absent for a value ThesisTrace COMPUTED rather than read —
    #: market capitalisation is shares x price, and free cash flow is a subtraction,
    #: so neither has a single filed line to point at. `derived_from` says which
    #: canonical concepts it came from instead, so a computed number never wears a
    #: filed-line citation.
    accession_number: str | None = None
    derived_from: list[str] = []


class SensitivityCellOut(BaseModel):
    """One (discount rate, terminal growth) pair.

    A cell that did not resolve is KEPT with its reason rather than omitted — a grid
    with holes silently implies its own coverage is complete.
    """

    discount_rate: float
    terminal_growth: float
    implied_growth: float | None
    reason: str | None = None


class ReverseDcfOut(BaseModel):
    """What growth today's price implies (Epic 6).

    Deliberately carries NO fair value, target price or upside, and the grid carries
    no midpoint. Running the model backwards exists precisely to avoid producing a
    valuation, and a central estimate would become the headline and undo the band.
    """

    fiscal_year: int
    #: None exactly when insufficient_data.
    implied_growth: float | None
    insufficient_data: bool
    #: Why there is no figure. Always present when insufficient_data (AD-16).
    reason: str | None
    #: The band across the declared assumption grid. THE RANGE IS THE ANSWER —
    #: every real band is ~30 percentage points wide and two cross zero, so the
    #: point figure alone would overstate what is known.
    range_low: float | None
    range_high: float | None
    sensitivity: list[SensitivityCellOut] = []
    resolved_cells: int
    total_cells: int
    #: The assumptions that produced it. Without these the number means nothing.
    discount_rate: float
    terminal_growth: float
    horizon_years: int
    operands: list[ReverseDcfOperandOut] = []
    #: The filer's OWN achieved revenue growth, over the window stated below. The
    #: comparison is the entire point: is the price asking for something this
    #: business has ever done?
    historical_revenue_cagr: float | None
    historical_from_fiscal_year: int | None
    historical_to_fiscal_year: int | None
    #: Annotations that never alter the figure (capital intensity, interest
    #: classification). Text comes from the spec, not inferred downstream.
    caveats: list[str] = []
    attribution: str
    spec_version: str


class CompanyOverviewOut(BaseModel):
    cik: str
    ticker: str
    name: str
    lenses_live: list[str]
    lenses_pending: list[str]
    verdict: list[VerdictItem]
    scores: list[LensScoreOut]
    #: Newest fiscal year first. Empty when the filer resolves no year at all.
    near_term_debt_share: list[NearTermDebtShareOut] = []
    #: Newest fiscal year first. EMPTY for most of the universe by structure —
    #: the frontend must render nothing at all rather than a "missing" state
    #: (Story 5.7, a deliberate scoped exception to the AD-16 display convention).
    debt_maturity_profile: list[MaturityProfileOut] = []
    #: Latest resolvable fiscal year only — the grid is 35 solves, so a per-year
    #: series would be a different cost class. None when the filer resolves no year.
    reverse_dcf: ReverseDcfOut | None = None
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
