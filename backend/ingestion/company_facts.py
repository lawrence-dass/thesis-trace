"""Parse a SEC EDGAR Company Facts payload into structured facts.

Pure functions — no network, no DB — so they are fully unit-testable against a
committed fixture. The live fetch lives in `ingestion.edgar`; persistence lives
in `raw_store.repository`. Company Facts is the primary source; Inline XBRL is
the fallback for omitted facts (AD-4).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedFiling:
    accession_number: str
    form_type: str
    filing_date: str  # ISO date
    fiscal_year: int
    fiscal_year_end: str  # ISO date


@dataclass(frozen=True)
class ParsedFact:
    accession_number: str
    taxonomy: str
    concept: str
    unit: str
    period_start: str | None
    period_end: str | None
    value: float
    fiscal_year: int
    source: str
    content_hash: str


@dataclass
class ParsedCompanyFacts:
    cik: str
    entity_name: str
    filings: dict[str, ParsedFiling] = field(default_factory=dict)
    facts: list[ParsedFact] = field(default_factory=list)


def _content_hash(taxonomy: str, concept: str, unit: str, start: str | None, end: str | None, value: float) -> str:
    payload = f"{taxonomy}|{concept}|{unit}|{start or ''}|{end or ''}|{value}"
    return hashlib.sha256(payload.encode()).hexdigest()


def zero_pad_cik(cik: int | str) -> str:
    return str(cik).zfill(10)


def parse_company_facts(payload: dict, *, source: str = "company_facts") -> ParsedCompanyFacts:
    """Flatten a Company Facts payload into filings + individual facts.

    Only annual 10-K / 10-K/A facts (fp == 'FY') are kept — Phase 1 scores from
    annual filings (PRD FR-3/FR-4/FR-6/FR-7).
    """
    result = ParsedCompanyFacts(cik=zero_pad_cik(payload["cik"]), entity_name=payload.get("entityName", ""))

    for taxonomy, concepts in payload.get("facts", {}).items():
        for concept, concept_body in concepts.items():
            for unit, entries in concept_body.get("units", {}).items():
                for entry in entries:
                    if entry.get("fp") != "FY":
                        continue
                    if entry.get("form") not in ("10-K", "10-K/A"):
                        continue
                    accn = entry["accn"]
                    end = entry.get("end")
                    fy = int(entry["fy"])
                    if accn not in result.filings:
                        result.filings[accn] = ParsedFiling(
                            accession_number=accn,
                            form_type=entry["form"],
                            filing_date=entry.get("filed", end),
                            fiscal_year=fy,
                            fiscal_year_end=end,
                        )
                    value = float(entry["val"])
                    result.facts.append(
                        ParsedFact(
                            accession_number=accn,
                            taxonomy=taxonomy,
                            concept=concept,
                            unit=unit,
                            period_start=entry.get("start"),
                            period_end=end,
                            value=value,
                            fiscal_year=fy,
                            source=source,
                            content_hash=_content_hash(taxonomy, concept, unit, entry.get("start"), end, value),
                        )
                    )
    return result
