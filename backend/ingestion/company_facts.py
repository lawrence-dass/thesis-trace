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

    A single accession's facts span multiple (fy, end) pairs — its own primary/
    current period plus one or more prior-year comparatives carried for
    disclosure, PLUS `dei` cover-page facts (e.g. shares-outstanding-as-of-
    filing-date) whose `end` is dated to the filing date, *after* the true
    fiscal-year-end. Confirmed live 2026-07-22/23, two compounding bugs:
    (1) a naive single pass picking whichever entry is encountered first (dict/
    list iteration order — `dei` sorts before `us-gaap` in the payload) can
    associate an entirely wrong (fy, end) with an accession (SHOP's FY2024 10-K
    was recorded as fiscal_year_end=2023-12-31, a full year off); (2) even a
    "take the latest end date" fix is wrong if `dei` facts are included in that
    comparison, since a cover-page fact's filing-date-dated `end` is later than
    the real fiscal-year-end and wins the max spuriously (CP FY2025 came out as
    fiscal_year_end=2026-02-25 instead of 2025-12-31). Fixed by restricting the
    (fy, end) candidate pool to `us-gaap` facts only — genuine financial-
    statement periods never carry a cover-page "as of filing date" style
    entry — then taking the latest end among those (the filing's own current
    period; comparatives are always for an earlier period).
    """
    result = ParsedCompanyFacts(cik=zero_pad_cik(payload["cik"]), entity_name=payload.get("entityName", ""))

    filing_meta: dict[str, dict] = {}  # accn -> {form_type, filed, candidates: [(fy, end)]}
    all_entries: list[tuple[str, str, str, dict]] = []  # (taxonomy, concept, unit, entry)

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
                    meta = filing_meta.setdefault(
                        accn,
                        {"form_type": entry["form"], "filed": entry.get("filed", end), "candidates": [], "fallback": []},
                    )
                    if taxonomy == "us-gaap":  # never dei — see docstring
                        meta["candidates"].append((fy, end))
                    else:
                        # Rare: an accession (e.g. a narrow 10-K/A amending only a
                        # cover-page/footnote disclosure) with zero us-gaap FY facts.
                        # Still needs a Filing row or its raw_facts orphan the FK —
                        # fall back to any taxonomy rather than dropping the filing.
                        meta["fallback"].append((fy, end))
                    all_entries.append((taxonomy, concept, unit, entry))

    for accn, meta in filing_meta.items():
        candidates = meta["candidates"] or meta["fallback"]
        fy, end = max(candidates, key=lambda pair: pair[1])  # latest end = the filing's own primary period
        result.filings[accn] = ParsedFiling(
            accession_number=accn,
            form_type=meta["form_type"],
            filing_date=meta["filed"],
            fiscal_year=fy,
            fiscal_year_end=end,
        )

    for taxonomy, concept, unit, entry in all_entries:
        end = entry.get("end")
        value = float(entry["val"])
        result.facts.append(
            ParsedFact(
                accession_number=entry["accn"],
                taxonomy=taxonomy,
                concept=concept,
                unit=unit,
                period_start=entry.get("start"),
                period_end=end,
                value=value,
                fiscal_year=int(entry["fy"]),
                source=source,
                content_hash=_content_hash(taxonomy, concept, unit, entry.get("start"), end, value),
            )
        )
    return result
