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


class SignalOut(BaseModel):
    signal_key: str
    status: str  # pass | fail | insufficient_data
    value: float | None
    band_label: str | None
    provenance: list[Provenance]


class LensScoreOut(BaseModel):
    model: str
    fiscal_year: int
    formula_version: str
    aggregate_value: float | None
    band_label: str | None
    applicability: str
    signals: list[SignalOut]


class CompanyOverviewOut(BaseModel):
    cik: str
    ticker: str
    name: str
    lenses_live: list[str]
    scores: list[LensScoreOut]


class CompanyCardOut(BaseModel):
    cik: str
    ticker: str
    name: str
