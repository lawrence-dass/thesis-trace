"""Parse a SEC EDGAR Company Facts payload into structured facts.

Pure functions — no network, no DB — so they are fully unit-testable against a
committed fixture. The live fetch lives in `ingestion.edgar`; persistence lives
in `raw_store.repository`. Company Facts is the primary source; Inline XBRL is
the fallback for omitted facts (AD-4).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from canonicalization.taxonomies import ANNUAL_FORM_TYPES, FINANCIAL_TAXONOMIES


_MIN_FULL_YEAR_DAYS = 300  # keep in step with canonicalization's duration guard


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


def _is_full_year_period(start: str | None, end: str | None) -> bool:
    """Return whether a fact describes a full-year statement period."""
    if not start or not end:
        return False
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days >= _MIN_FULL_YEAR_DAYS
    except ValueError:
        return False


def parse_company_facts(payload: dict, *, source: str = "company_facts") -> ParsedCompanyFacts:
    """Flatten a Company Facts payload into filings + individual facts.

    Only annual facts (fp == 'FY' or the equivalent annual 10-K ``Q4`` label) on
    a supported annual form are kept — Phase 1 scores from annual filings
    (PRD FR-3/FR-4/FR-6/FR-7). Supported forms and financial taxonomies are
    declared in canonicalization.taxonomies. A few valid annual filings, such as
    ZTS's FY2014 10-K, label their annual facts ``Q4`` rather than ``FY``; the
    annual form gate and downstream full-year-duration filter still distinguish
    them from quarterly filings.

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
    entry. For annual duration facts, the latest full-year statement period is
    preferred over instant facts, so a subsequent-event disclosure dated before
    filing cannot win merely by being later than the statement period.
    """
    result = ParsedCompanyFacts(cik=zero_pad_cik(payload["cik"]), entity_name=payload.get("entityName", ""))

    filing_meta: dict[str, dict] = {}  # accn -> {form_type, filed, candidates: [(fy, end)]}
    all_entries: list[tuple[str, str, str, dict]] = []  # (taxonomy, concept, unit, entry)

    for taxonomy, concepts in payload.get("facts", {}).items():
        for concept, concept_body in concepts.items():
            for unit, entries in concept_body.get("units", {}).items():
                for entry in entries:
                    if entry.get("fp") not in {"FY", "Q4"}:
                        continue
                    if entry.get("form") not in ANNUAL_FORM_TYPES:
                        continue
                    accn = entry["accn"]
                    end = entry.get("end")
                    fy = int(entry["fy"])
                    meta = filing_meta.setdefault(
                        accn,
                        {
                            "form_type": entry["form"],
                            "filed": None,
                            "candidates": [],
                            "statement_periods": [],
                            "fallback": [],
                        },
                    )
                    # Company Facts normally repeats `filed` on every entry, but
                    # do not let an entry that omits it hide a later entry that
                    # supplies the accession's actual filing date.
                    if meta["filed"] is None and entry.get("filed") is not None:
                        meta["filed"] = entry["filed"]
                    if taxonomy in FINANCIAL_TAXONOMIES:  # never dei — see docstring
                        pair = (fy, end)
                        meta["candidates"].append(pair)
                        if _is_full_year_period(entry.get("start"), end):
                            meta["statement_periods"].append(pair)
                    else:
                        # Rare: an accession (e.g. a narrow 10-K/A amending only a
                        # cover-page/footnote disclosure) with zero financial-taxonomy
                        # FY facts.
                        # Still needs a Filing row or its raw_facts orphan the FK —
                        # fall back to any taxonomy rather than dropping the filing.
                        meta["fallback"].append((fy, end))
                    all_entries.append((taxonomy, concept, unit, entry))

    for accn, meta in filing_meta.items():
        candidates = meta["candidates"] or meta["fallback"]
        # Drop any candidate whose `end` is AFTER the accession's own `filed` date before
        # taking the latest end. A genuine financial-statement period can never end after
        # the report covering it was filed, so end > filed is proof of something else — a
        # subsequent-event or financing-arrangement disclosure dated near the filing date,
        # still genuinely us-gaap and annual-labelled, so not excluded by the dei fix above.
        # Confirmed live 2026-09-01: CPB's FY2011 10-K (accn 0000950123-11-087197, filed
        # 2011-09-28) tags LineOfCreditFacilityMaximumBorrowingCapacity at end=2011-09-30 —
        # two days AFTER the filing date, and two months after the real FYE of 2011-07-31
        # that every other us-gaap concept on the accession carries. A plurality-of-count
        # heuristic was tried and rejected: CPB's earliest 10-K (accn 0000950123-10-090083)
        # legitimately carries MORE facts for its FY2009 comparative (95) than for its own
        # FY2010 current period (89), so "most common end wins" picks the wrong year. The
        # filed-date bound has no such failure mode — a comparative period's end is always
        # well before the filing date, never after it.
        filed = meta["filed"]
        if filed is None:
            # Company Facts normally supplies `filed`; preserve the existing
            # latest-period behavior when a malformed/legacy payload does not.
            valid = [pair for pair in candidates if pair[1] is not None]
        else:
            valid = [
                pair for pair in candidates
                if pair[1] is not None
                and (
                    pair[1] < filed
                    or (pair[1] == filed and pair in meta["statement_periods"])
                )
            ]
        statement_periods = [pair for pair in valid if pair in meta["statement_periods"]]
        if statement_periods:
            valid = statement_periods
        if not valid:
            # Do not silently put a future-dated disclosure back into the
            # candidate pool. Failing closed keeps an invalid Filing from being
            # persisted with a fabricated fiscal year-end (and makes the source
            # data problem visible to the ingestion caller).
            raise ValueError(
                f"No financial period for accession {accn} ends before or on "
                f"its filing date {filed}"
            )
        fy, end = max(valid, key=lambda pair: pair[1])  # latest end = the filing's own primary period
        result.filings[accn] = ParsedFiling(
            accession_number=accn,
            form_type=meta["form_type"],
            filing_date=filed or end,
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
