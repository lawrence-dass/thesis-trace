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
    concept: Mapped[str] = mapped_column(String(128), index=True)
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


class ScoreInput(Base):
    __tablename__ = "score_inputs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    score_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("score_runs.id"), index=True)
    signal_key: Mapped[str] = mapped_column(String(64))
    canonical_fact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("canonical_facts.id"))
    market_price_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("market_prices.id"))  # Altman (AD-14)

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
