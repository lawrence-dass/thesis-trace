"""SQLAlchemy models — the materialized state the pipeline writes and the read API queries.

Conventions (ARCHITECTURE-SPINE.md):
- Every financial figure is NUMERIC/DECIMAL, never float (AD-15).
- Internal PKs are UUID, except `issuers` (CIK string) and `filings` (accession_number
  string) — natural external keys.
- DATE for fiscal/filing dates; TIMESTAMPTZ for computed_at/fetched_at.
- `raw_facts` is append-only, keyed by (accession_number, content_hash) (AD-2).
- `score_results` follows the canonical shape (AD-18); statuses are tri-state (AD-16);
  applicability tracks sector scope (AD-20).
- `data_quality_issues` has one row shape + closed status enum (AD-17).

Scope (Story 1.2): only the tables the Piotroski + Sloan (EDGAR-only) slice needs.
`market_prices` is intentionally NOT here — it lands in Story 2.1 (Altman/Tiingo).
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Model(str, enum.Enum):
    piotroski = "piotroski"
    altman = "altman"
    beneish = "beneish"
    sloan = "sloan"


class SignalStatus(str, enum.Enum):
    """Tri-state per AD-16 — a missing input is insufficient_data, never a defaulted 0."""

    pass_ = "pass"
    fail = "fail"
    insufficient_data = "insufficient_data"


class Applicability(str, enum.Enum):
    """Sector-scope applicability per AD-20/D6."""

    computed = "computed"
    excluded_out_of_scope = "excluded_out_of_scope"
    computed_with_caveat = "computed_with_caveat"


class IssueStatus(str, enum.Enum):
    """Closed status enum per AD-17."""

    needs_review = "needs_review"
    resolved = "resolved"
    dismissed = "dismissed"


# --- Natural-key entities ---------------------------------------------------


class Issuer(Base):
    __tablename__ = "issuers"

    cik: Mapped[str] = mapped_column(String(10), primary_key=True)  # zero-padded CIK
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(128))
    is_financial_sector: Mapped[bool] = mapped_column(default=False)  # excludes Altman/Beneish (D6)
    is_capital_intensive: Mapped[bool] = mapped_column(default=False)  # Altman caveat (D6)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filings: Mapped[list["Filing"]] = relationship(back_populates="issuer")


class Filing(Base):
    __tablename__ = "filings"

    accession_number: Mapped[str] = mapped_column(String(25), primary_key=True)
    issuer_cik: Mapped[str] = mapped_column(ForeignKey("issuers.cik"), index=True)
    form_type: Mapped[str] = mapped_column(String(12))  # 10-K, 10-K/A, 10-Q
    filing_date: Mapped[date] = mapped_column(Date)
    fiscal_year: Mapped[int] = mapped_column()
    fiscal_year_end: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    issuer: Mapped["Issuer"] = relationship(back_populates="filings")


# --- Append-only raw store (AD-2) -------------------------------------------


class RawFact(Base):
    __tablename__ = "raw_facts"
    __table_args__ = (
        UniqueConstraint("accession_number", "content_hash", name="uq_raw_facts_accession_hash"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    accession_number: Mapped[str] = mapped_column(ForeignKey("filings.accession_number"), index=True)
    taxonomy: Mapped[str] = mapped_column(String(32))  # us-gaap, dei
    # 256, not 128: real XBRL custom-extension concept names exceed 128 chars
    # (e.g. a 140-char CP stock-compensation tag, confirmed live 2026-07-21).
    concept: Mapped[str] = mapped_column(String(256), index=True)
    unit: Mapped[str | None] = mapped_column(String(32))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    value: Mapped[float | None] = mapped_column(Numeric(28, 6))  # NUMERIC, never float (AD-15)
    decimals: Mapped[int | None] = mapped_column()
    dimensions: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(32))  # company_facts | inline_xbrl
    content_hash: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- Versioned canonicalization (AD-2, AD-3) --------------------------------


class ConceptMapping(Base):
    __tablename__ = "concept_mappings"
    __table_args__ = (
        UniqueConstraint(
            "mapping_version", "canonical_concept", "source_taxonomy", "source_concept",
            name="uq_concept_mappings_version_key",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    mapping_version: Mapped[str] = mapped_column(String(32), index=True)
    canonical_concept: Mapped[str] = mapped_column(String(128), index=True)
    source_taxonomy: Mapped[str] = mapped_column(String(32))
    source_concept: Mapped[str] = mapped_column(String(128))
    priority: Mapped[int] = mapped_column(default=0)  # lower wins in selection (AD-3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CanonicalFact(Base):
    __tablename__ = "canonical_facts"
    __table_args__ = (
        UniqueConstraint(
            "issuer_cik", "canonical_concept", "fiscal_year", "mapping_version",
            name="uq_canonical_facts_key",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    issuer_cik: Mapped[str] = mapped_column(ForeignKey("issuers.cik"), index=True)
    accession_number: Mapped[str] = mapped_column(ForeignKey("filings.accession_number"))
    canonical_concept: Mapped[str] = mapped_column(String(128), index=True)
    fiscal_year: Mapped[int] = mapped_column(index=True)
    period_end: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Numeric(28, 6))  # NUMERIC (AD-15)
    unit: Mapped[str | None] = mapped_column(String(32))
    mapping_version: Mapped[str] = mapped_column(String(32))
    # NULL = read directly from a filed XBRL tag. Non-NULL = computed by
    # ThesisTrace from other canonical facts, naming the rule that produced it
    # (e.g. "assets_minus_equity"). A derived value is a WEAKER evidential class
    # than a filed one: its accession_number is a faithful provenance root (the
    # same balance-sheet date) but no single line item in that filing states it.
    # Surfaced through the read API so a citation can never imply "this figure
    # appears in this filing" when it does not (FR-8, AD-19).
    derivation: Mapped[str | None] = mapped_column(String(64))
    selected_from_raw_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("raw_facts.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- Append-only scoring (AD-5, AD-6, AD-16, AD-18) -------------------------


class ScoreRun(Base):
    __tablename__ = "score_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    issuer_cik: Mapped[str] = mapped_column(ForeignKey("issuers.cik"), index=True)
    model: Mapped[Model] = mapped_column(Enum(Model, native_enum=False, length=16))
    fiscal_year: Mapped[int] = mapped_column(index=True)
    formula_version: Mapped[str] = mapped_column(String(32))  # references the spec by string (AD-5)
    accession_number: Mapped[str] = mapped_column(ForeignKey("filings.accession_number"))
    aggregate_value: Mapped[float | None] = mapped_column(Numeric(28, 6))
    applicability: Mapped[Applicability] = mapped_column(
        Enum(Applicability, native_enum=False, length=24), default=Applicability.computed
    )
    # Why a caveat applies, when applicability is computed_with_caveat. Stored
    # rather than inferred so the explanation layer never attaches one model's
    # reasoning to another (Altman's caveat is capital intensity; Beneish's is an
    # out-of-calibration input). NULL for computed / excluded runs.
    caveat_reason: Mapped[str | None] = mapped_column(String(512))
    superseded: Mapped[bool] = mapped_column(default=False)  # amendment supersedes, never mutates (AD-6)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("score_runs.id"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    results: Mapped[list["ScoreResult"]] = relationship(back_populates="run")
    inputs: Mapped[list["ScoreInput"]] = relationship(back_populates="run")


class MarketPrice(Base):
    """Persisted period-end close prices (AD-14). Altman joins through this table;
    it never calls Tiingo live during a read. Tiingo is the only market-data
    provider in Phase 1 (D7 exception)."""

    __tablename__ = "market_prices"
    __table_args__ = (
        UniqueConstraint("issuer_cik", "price_date", "source", name="uq_market_prices_key"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    issuer_cik: Mapped[str] = mapped_column(ForeignKey("issuers.cik"), index=True)
    price_date: Mapped[date] = mapped_column(Date)
    close_price: Mapped[float] = mapped_column(Numeric(28, 6))  # NUMERIC (AD-15)
    source: Mapped[str] = mapped_column(String(16), default="tiingo")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FxRate(Base):
    """Persisted historical FX rates (AD-11 currency fix, 2026-07-23). Confirmed
    live: some Phase-1 filers (CP) report all financial-statement figures in a
    non-USD currency (CAD), while Tiingo's price is always USD — Altman's X4
    (market value of equity / total liabilities) would otherwise silently divide
    mismatched currencies. Source is the Bank of Canada Valet API (free, no key,
    the authoritative central-bank rate for this exact pair) — never a live call
    during a read (AD-1), same discipline as market_prices."""

    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("currency_pair", "rate_date", "source", name="uq_fx_rates_key"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    currency_pair: Mapped[str] = mapped_column(String(8), index=True)  # e.g. "USDCAD"
    rate_date: Mapped[date] = mapped_column(Date)
    rate: Mapped[float] = mapped_column(Numeric(18, 8))  # NUMERIC (AD-15)
    source: Mapped[str] = mapped_column(String(32), default="bank_of_canada")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScoreInput(Base):
    __tablename__ = "score_inputs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    score_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("score_runs.id"), index=True)
    signal_key: Mapped[str] = mapped_column(String(64))
    canonical_fact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("canonical_facts.id"))
    market_price_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("market_prices.id"))  # Altman (AD-14)
    fx_rate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fx_rates.id"))  # Altman currency fix (AD-11, AD-19)

    run: Mapped["ScoreRun"] = relationship(back_populates="inputs")


class ScoreResult(Base):
    """Canonical result shape per AD-18: one row per model per signal/component."""

    __tablename__ = "score_results"
    __table_args__ = (
        UniqueConstraint("score_run_id", "signal_key", name="uq_score_results_run_signal"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    score_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("score_runs.id"), index=True)
    model: Mapped[Model] = mapped_column(Enum(Model, native_enum=False, length=16))
    signal_key: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Numeric(28, 6))  # NUMERIC (AD-15)
    status: Mapped[SignalStatus] = mapped_column(Enum(SignalStatus, native_enum=False, length=24))
    band_label: Mapped[str | None] = mapped_column(String(48))  # computed backend (AD-8/AD-12)
    threshold_ref: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["ScoreRun"] = relationship(back_populates="results")


# --- Materialized reverse DCF (AD-1) ----------------------------------------


class ReverseDcfRun(Base):
    """One filer's latest resolvable reverse DCF, computed on the WRITE path (AD-1).

    Exists because the read path used to call `reverse_dcf_for_issuer` directly, so
    every page load re-solved the DCF and all 35 sensitivity cells. AD-1 is a
    structural CQRS rule — "all computation runs in the scheduled batch pipeline; the
    read path only queries materialized Postgres and never computes a score" — so the
    fix is to move the work, not to make it reproducible.

    ONE ROW PER ISSUER, not per year. `reverse_dcf_for_issuer` chooses the latest
    fully reproducible fiscal year itself; the pipeline stores whichever year it
    chose. `fiscal_year` is in the key so a re-run that picks a DIFFERENT year cannot
    collide with the old row, and the writer deletes any other year for the same
    (issuer, spec_version) so "the stored row is the chosen year" stays an invariant.

    Rates are NUMERIC(18, 10): the solver's tolerance is 1e-7, so the money-shaped
    NUMERIC(28, 6) used elsewhere would round the answer coarser than the bisection
    that produced it.
    """

    __tablename__ = "reverse_dcf_runs"
    __table_args__ = (
        UniqueConstraint(
            "issuer_cik", "fiscal_year", "spec_version", name="uq_reverse_dcf_runs_key"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    issuer_cik: Mapped[str] = mapped_column(ForeignKey("issuers.cik"), index=True)
    fiscal_year: Mapped[int] = mapped_column(index=True)
    spec_version: Mapped[str] = mapped_column(String(32))

    implied_growth: Mapped[float | None] = mapped_column(Numeric(18, 10))
    insufficient_data: Mapped[bool] = mapped_column(default=False)
    # Long because the overview concatenates the solver's reason with the market
    # resolution's reason when both apply (AD-16: absence explains itself).
    reason: Mapped[str | None] = mapped_column(String(512))

    # Operands, so the stored result stays independently recomputable (finding 3.5).
    enterprise_value: Mapped[float | None] = mapped_column(Numeric(28, 6))
    free_cash_flow: Mapped[float | None] = mapped_column(Numeric(28, 6))
    market_cap: Mapped[float | None] = mapped_column(Numeric(28, 6))
    total_debt: Mapped[float | None] = mapped_column(Numeric(28, 6))
    cash_and_equivalents: Mapped[float | None] = mapped_column(Numeric(28, 6))

    # The assumptions that produced it. Without these the number means nothing.
    discount_rate: Mapped[float] = mapped_column(Numeric(18, 10))
    terminal_growth: Mapped[float] = mapped_column(Numeric(18, 10))
    horizon_years: Mapped[int] = mapped_column()
    #: Caveat IDs. Stored as data rather than inferred downstream from a shared enum
    #: — the recurring bug class where one model's display logic reaches another.
    caveats: Mapped[list | None] = mapped_column(JSONB)
    attribution: Mapped[str] = mapped_column(String(1024))

    # The exact persisted market/FX rows market capitalisation was derived from.
    market_price_date: Mapped[date | None] = mapped_column(Date)
    market_price_source: Mapped[str | None] = mapped_column(String(32))
    fx_rate: Mapped[float | None] = mapped_column(Numeric(18, 8))
    fx_rate_date: Mapped[date | None] = mapped_column(Date)
    fx_rate_source: Mapped[str | None] = mapped_column(String(32))

    # Sensitivity band. `has_grid` distinguishes "no grid at all" (operands missing,
    # `grid_for` returned None) from "a grid where no cell resolved" — collapsing
    # those would let an unsolvable filer look like an unattempted one.
    has_grid: Mapped[bool] = mapped_column(default=False)
    grid_low: Mapped[float | None] = mapped_column(Numeric(18, 10))
    grid_high: Mapped[float | None] = mapped_column(Numeric(18, 10))
    resolved_cells: Mapped[int] = mapped_column(default=0)
    total_cells: Mapped[int] = mapped_column(default=0)

    # The filer's OWN achieved growth, for comparison against the implied rate. The
    # window adapts per filer (IFRS 40-F history starts ~FY2017), so it is reported
    # rather than promised — hence the explicit from/to years.
    historical_revenue_cagr: Mapped[float | None] = mapped_column(Numeric(18, 10))
    historical_from_fiscal_year: Mapped[int | None] = mapped_column()
    historical_to_fiscal_year: Mapped[int | None] = mapped_column()

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    cells: Mapped[list["ReverseDcfCell"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ReverseDcfCell(Base):
    """One (discount rate, terminal growth) pair of the sensitivity grid.

    A CELL THAT FAILED IS STORED, NOT DROPPED — omitting it would let the grid imply
    its own coverage is complete. A failed cell has a NULL `implied_growth` and a
    `reason`, exactly like the in-memory `SensitivityCell`.
    """

    __tablename__ = "reverse_dcf_cells"
    __table_args__ = (
        UniqueConstraint(
            "reverse_dcf_run_id", "discount_rate", "terminal_growth",
            name="uq_reverse_dcf_cells_key",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    reverse_dcf_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reverse_dcf_runs.id", ondelete="CASCADE"), index=True
    )
    discount_rate: Mapped[float] = mapped_column(Numeric(18, 10))
    terminal_growth: Mapped[float] = mapped_column(Numeric(18, 10))
    implied_growth: Mapped[float | None] = mapped_column(Numeric(18, 10))
    reason: Mapped[str | None] = mapped_column(String(512))

    run: Mapped["ReverseDcfRun"] = relationship(back_populates="cells")


# --- Data-quality tracking (AD-3, AD-17) ------------------------------------


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"

    id: Mapped[uuid.UUID] = _uuid_pk()
    accession_number: Mapped[str | None] = mapped_column(ForeignKey("filings.accession_number"))
    canonical_fact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("canonical_facts.id"))
    issue_type: Mapped[str] = mapped_column(String(64))  # ambiguous_selection, identity_violation, source_conflict
    detail: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, native_enum=False, length=16), default=IssueStatus.needs_review
    )
    raised_by: Mapped[str] = mapped_column(String(32))  # canonicalization | validation
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
