"""Deterministic canonical-fact selection (AD-2, AD-3).

For each (issuer, canonical_concept, fiscal_year), choose one raw_fact by the
ordered rules:
  1. as-originally-filed  (fact from the filing whose fiscal_year == the period's
     year) over a restated comparative carried in a later filing;
  1a. within that tier, a same-year amendment (10-K/A or 40-F/A) over the original
     it amends; competing amendments remain ambiguous;
  2. concept priority (when several source XBRL concepts map to one canonical
     concept — e.g. shares_outstanding's CommonStockSharesOutstanding-first,
     WeightedAverageNumberOfSharesOutstandingBasic-fallback chain — the lower
     priority number wins outright rather than being compared for ambiguity
     against a fundamentally different measurement);
  3. higher `decimals` precision;
  4. earliest `fetched_at` as a stable final tiebreak.
Ambiguity (distinct values tied through rule 2 — including a Company-Facts-vs-
Inline-XBRL conflict on the *same* source concept, AD-4) writes a
`data_quality_issues` row with status needs_review — never a defaulted guess
(AD-3). Canonical facts are derived, never mutated in place; a mapping-version
change produces new rows (AD-2).

Both the source-concept mappings and the derivations this module applies are DATA,
loaded from `canonicalization/mappings/specs/*.yaml` — this module owns the
selection algorithm, not the rules it runs on.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CanonicalFact, DataQualityIssue, Filing, IssueStatus, RawFact
from canonicalization.mappings import (
    DERIVATION_RULES,
    MAPPING_VERSION,
    SOURCE_EXCLUDED_ISSUERS,
    SOURCE_PRIORITY,
    SOURCE_TO_CANONICAL,
)
from canonicalization.taxonomies import ORIGINAL_ANNUAL_FORM_TYPES, is_amendment

# A 10-K's own accession routinely tags BOTH the true annual duration figure
# AND quarterly sub-periods under the exact same (fy, fp="FY") label — e.g. a
# "selected quarterly financial data" footnote disclosure. Confirmed live
# 2026-07-23 against CP's us-gaap:Revenues, fy=2016: the accession carries
# Q1-Q4 facts (~90-day spans) alongside the genuine full-year fact (~365-day
# span), all sharing fy=2016/fp=FY/form=10-K — grouping by period_end.year
# alone can't tell them apart and both land in the same candidate pool.
# Filtering to full-year spans before grouping resolves the true annual figure
# cleanly instead of flagging it ambiguous_selection against a quarter.
_MIN_FULL_YEAR_DAYS = 300  # excludes quarterly (~90d) and half-year (~180d) spans

# A new-accounting-standard adoption (e.g. ASC 606/842) is commonly disclosed
# with a cumulative-effect balance "as of the beginning of the year" — an
# instantaneous fact dated the FIRST day of the fiscal year, alongside the true
# closing balance dated the LAST day, both under the same fy/calendar year.
# Confirmed live 2026-07-23: QSR's FY2018 10-K tags us-gaap:Assets at both
# end=2018-01-01 (val=21,308,000,000, the Jan-1 opening/adjusted balance) and
# end=2018-12-31 (val=20,141,000,000, the true closing balance) — grouping by
# period_end.year alone puts both in fiscal_year=2018 and neither AD-3 tiebreak
# can separate them, spuriously flagging a cleanly resolvable case as
# ambiguous_selection. A fact only belongs in the annual bucket if its
# period_end actually falls near the issuer's own recognized fiscal-year-end
# day-of-year (tolerant of the odd few-day shift — e.g. OTEX's 2011 10-K FYE
# landed on 2011-07-07, not its usual June 30).
_FYE_DAY_TOLERANCE = 10


def _is_full_year_duration(rf: RawFact) -> bool:
    """True for instantaneous facts (no period_start — balance-sheet items like
    total_assets, unaffected by this filter) and for duration facts whose span
    is a genuine fiscal year rather than a quarterly/partial-period breakdown."""
    if rf.period_start is None or rf.period_end is None:
        return True
    return (rf.period_end - rf.period_start).days >= _MIN_FULL_YEAR_DAYS


def _day_of_year(month: int, day: int) -> int:
    return date(2001, month, day).toordinal() - date(2001, 1, 1).toordinal()


def _issuer_fye_day(filings: dict[str, Filing]) -> int | None:
    """The most common day-of-year among this issuer's own ORIGINAL annual
    fiscal-year-ends (never an amendment — its own fiscal_year_end can be
    unreliable, per the collision fix in pipeline.run._primary_filing_per_year).
    Regime-agnostic: 10-K for us-gaap filers, 40-F for IFRS filers."""
    counts = Counter(
        _day_of_year(f.fiscal_year_end.month, f.fiscal_year_end.day)
        for f in filings.values()
        if f.form_type in ORIGINAL_ANNUAL_FORM_TYPES
    )
    return counts.most_common(1)[0][0] if counts else None


def _matches_fiscal_year_end(rf: RawFact, fye_day: int | None) -> bool:
    if fye_day is None or rf.period_end is None:
        return True
    actual = _day_of_year(rf.period_end.month, rf.period_end.day)
    return abs(actual - fye_day) <= _FYE_DAY_TOLERANCE


async def canonicalize_issuer(
    session: AsyncSession, issuer_cik: str, *, mapping_version: str = MAPPING_VERSION
) -> dict[str, int]:
    """Build canonical_facts for one issuer. Returns counts (facts, ambiguities).

    Idempotent across passes, and amendment-aware across passes: a key already
    written is skipped only while the same raw fact still wins its selection.
    When a later pass finds a different winner with a different figure — the
    production shape being a 10-K/A restating a year the daily pipeline
    canonicalized months earlier — the old row is SUPERSEDED (never mutated or
    deleted) and the restated value becomes current, so the next scoring pass
    references the new fact and the prior run's inputs still resolve to the
    old one (AD-2, AD-6, AD-19). Tracked as `canonical_facts_amendment_gap`.
    """
    counts = {"canonical_facts_added": 0, "canonical_facts_superseded": 0, "ambiguities_flagged": 0}

    filings = {
        f.accession_number: f
        for f in (
            await session.execute(select(Filing).where(Filing.issuer_cik == issuer_cik))
        ).scalars()
    }
    accns = list(filings)
    if not accns:
        return counts

    raw_facts = (
        await session.execute(select(RawFact).where(RawFact.accession_number.in_(accns)))
    ).scalars().all()

    # (concept, fiscal_year) ambiguities THIS module has already recorded for the
    # issuer. Without this the insert below has no idempotency key, which is the
    # anti-pattern `run_validation` was given a dedup for in PR #22 — the one
    # writer that was missed. It does not bite in daily operation, because an
    # already-canonicalized issuer is skipped wholesale before reaching here; it
    # bites on a MAPPING-VERSION BUMP, which re-resolves every concept and so
    # re-flags every unresolvable one. Found 2026-08-21 by rendering SHOP's page
    # after the concepts_v9 bump: 24 identical "Ambiguous source selection" rows
    # for SHOP and 18 for CP, with BCE's and OTEX's four apiece doubled to eight.
    #
    # Deliberately IGNORES status, so a `dismissed` issue is not resurrected as a
    # fresh `needs_review` one — the same requirement recorded for validation.
    existing_ambiguities = {
        (d.get("canonical_concept"), d.get("fiscal_year"))
        for d in (
            await session.execute(
                select(DataQualityIssue.detail)
                .join(Filing, Filing.accession_number == DataQualityIssue.accession_number)
                .where(
                    Filing.issuer_cik == issuer_cik,
                    DataQualityIssue.raised_by == "canonicalization",
                    DataQualityIssue.issue_type == "ambiguous_selection",
                )
            )
        ).scalars()
        if d
    }

    # Group candidate raw_facts by (canonical_concept, fiscal_year).
    fye_day = _issuer_fye_day(filings)
    grouped: dict[tuple[str, int], list[RawFact]] = defaultdict(list)
    for rf in raw_facts:
        canonical = SOURCE_TO_CANONICAL.get((rf.taxonomy, rf.concept))
        if canonical is None or rf.period_end is None:
            continue
        if not _is_full_year_duration(rf):
            continue
        if not _matches_fiscal_year_end(rf, fye_day):
            continue
        if issuer_cik in SOURCE_EXCLUDED_ISSUERS.get((rf.taxonomy, rf.concept), frozenset()):
            continue
        grouped[(canonical, rf.period_end.year)].append(rf)

    # CURRENT canonical rows for this version. Keyed to the row, not just the
    # key, because idempotency is "the same raw fact still wins", not "the key
    # exists": the latter froze whichever value was written first and dropped
    # every later restatement (`canonical_facts_amendment_gap`).
    existing: dict[tuple[str, str, int], CanonicalFact] = {
        (f.issuer_cik, f.canonical_concept, f.fiscal_year): f
        for f in (
            await session.execute(
                select(CanonicalFact).where(
                    CanonicalFact.issuer_cik == issuer_cik,
                    CanonicalFact.mapping_version == mapping_version,
                    CanonicalFact.superseded.is_(False),
                )
            )
        ).scalars()
    }

    for (canonical, fiscal_year), candidates in grouped.items():
        current = existing.get((issuer_cik, canonical, fiscal_year))

        def rank(rf: RawFact) -> tuple:
            filing = filings[rf.accession_number]
            originally_filed = filing.fiscal_year == fiscal_year
            # Within the originally-filed tier an amendment of THAT year (10-K/A,
            # 40-F/A) outranks the original it amends: the filer has explicitly
            # restated the figure, and AD-6 requires the restated value to be the
            # one a new score_run references. This is the filer's own
            # supersession, not a guess — two competing amendments of the same
            # year still fall through to the ambiguity flag below. A restated
            # COMPARATIVE inside a later year's filing stays in the lower tier
            # (AD-3 rule 1) regardless of that filing's form type.
            amends_this_year = originally_filed and is_amendment(filing.form_type)
            concept_priority = SOURCE_PRIORITY.get((rf.taxonomy, rf.concept), 0)
            return (
                0 if originally_filed else 1,  # originally filed first
                0 if amends_this_year else 1,  # ...and its amendment over the original
                concept_priority,  # lower-priority source concept wins outright
                -(rf.decimals if rf.decimals is not None else -9),  # higher decimals first
                rf.fetched_at,  # stable
            )

        candidates.sort(key=rank)
        best = candidates[0]
        # Tie tier = (originally_filed, amends_this_year, concept_priority) — a
        # lower-priority concept never contends for "ambiguous" against a
        # higher-priority one (they measure different things); decimals/fetched_at
        # remain pure tiebreaks within a genuinely tied tier, so two same-priority
        # facts with different values (incl. a company_facts-vs-inline_xbrl conflict
        # on the same concept, AD-4) are still correctly flagged.
        top_tier = [c for c in candidates if rank(c)[:3] == rank(best)[:3]]
        distinct_values = {c.value for c in top_tier}

        if len(distinct_values) > 1:
            # Rules cannot separate conflicting values — flag, do not guess (AD-3).
            # A previously resolved row stays current: superseding it with a
            # guess would be worse than leaving the flagged conflict for review.
            if (canonical, fiscal_year) in existing_ambiguities:
                continue
            existing_ambiguities.add((canonical, fiscal_year))
            session.add(
                DataQualityIssue(
                    accession_number=best.accession_number,
                    issue_type="ambiguous_selection",
                    detail={
                        "canonical_concept": canonical,
                        "fiscal_year": fiscal_year,
                        "values": sorted(str(v) for v in distinct_values),
                    },
                    status=IssueStatus.needs_review,
                    raised_by="canonicalization",
                )
            )
            counts["ambiguities_flagged"] += 1
            continue

        if current is not None:
            if current.selected_from_raw_fact_id == best.id:
                continue  # same winner as the last pass — nothing to do
            # A different raw fact won, but the figure and its measurement
            # metadata are unchanged (a re-filed identical value, a
            # higher-precision duplicate): leave the original in place rather
            # than rewrite provenance for no semantic change. A derived row is
            # the exception — a filed figure is the stronger evidential class
            # and replaces it whatever the value (AD-3).
            if (
                current.derivation is None
                and Decimal(str(current.value)) == Decimal(str(best.value))
                and current.unit == best.unit
                and current.period_end == best.period_end
            ):
                continue

        replacement = CanonicalFact(
            issuer_cik=issuer_cik,
            accession_number=best.accession_number,
            canonical_concept=canonical,
            fiscal_year=fiscal_year,
            period_end=best.period_end,
            value=best.value,
            unit=best.unit,
            mapping_version=mapping_version,
            selected_from_raw_fact_id=best.id,
        )
        if current is not None:
            await _supersede(session, current, replacement)
            counts["canonical_facts_superseded"] += 1
        else:
            session.add(replacement)
        counts["canonical_facts_added"] += 1

    await session.flush()
    # A filing metadata correction can make a previously selected raw-fact
    # group disappear (most notably when its fiscal-year-end is corrected).
    # Retire direct facts that no longer have any eligible source candidate;
    # otherwise current-fact readers would keep scoring a row the selector can
    # no longer justify. Derived rows are reconciled below, after operands have
    # been refreshed.
    grouped_keys = set(grouped)
    for (_existing_issuer, canonical, fiscal_year), current in existing.items():
        if current.derivation is None and (canonical, fiscal_year) not in grouped_keys:
            await _retire_current_fact(session, current)
            counts["canonical_facts_superseded"] += 1

    counts["derived_facts_added"] = await _apply_derivations(
        session, issuer_cik, mapping_version=mapping_version, counts=counts
    )
    await session.flush()
    return counts


async def _apply_derivations(
    session: AsyncSession, issuer_cik: str, *, mapping_version: str, counts: dict[str, int] | None = None
) -> int:
    """Compute canonical concepts a filer never tagged directly, per the rules
    declared in `canonicalization/mappings/specs/derivations_v1.yaml`. Returns the
    number of derived facts added.

    A rule fires only when its target concept is genuinely absent for that fiscal
    year and every operand resolved — it never overrides a directly-tagged value
    (AD-3). Each derived row records `derivation=<rule name>` rather than a bare
    flag, so the read API can say WHAT was computed and the UI never implies a
    filed line item. Its accession_number/period_end are anchored to the rule's
    `provenance_from` operand: the same balance-sheet date, a faithful provenance
    root for a value with no single source line.

    A derived row is only as current as its operands. When an amendment
    supersedes an operand (see `canonicalize_issuer`), the rule is re-evaluated
    and a derived row whose value or provenance anchor moved is superseded by a
    fresh one — never edited in place — so it carries the same append-only
    guarantee as a filed fact. Supersessions are tallied into `counts`.

    Rules are applied against the facts as SELECTED, not against each other's
    output — a derivation never consumes another derivation's result. Chaining
    would compound weak provenance invisibly, so it stays a deliberate decision
    rather than an emergent one."""
    if not DERIVATION_RULES:
        return 0

    needed = {c for r in DERIVATION_RULES for c in (r.canonical_concept, *r.operands)}
    facts = (
        await session.execute(
            select(CanonicalFact).where(
                CanonicalFact.issuer_cik == issuer_cik,
                CanonicalFact.mapping_version == mapping_version,
                CanonicalFact.superseded.is_(False),
                CanonicalFact.canonical_concept.in_(needed),
            )
        )
    ).scalars().all()

    by_year: dict[int, dict[str, CanonicalFact]] = defaultdict(dict)
    for f in facts:
        by_year[f.fiscal_year][f.canonical_concept] = f

    # Which source concept each selected fact actually came from, for rules whose
    # operands are only valid when they measure the right thing (see requires_source).
    source_of = await _source_concepts(session, facts) if any(r.requires_source for r in DERIVATION_RULES) else {}

    added = 0
    for rule in DERIVATION_RULES:
        for fiscal_year, concepts in by_year.items():
            target = concepts.get(rule.canonical_concept)
            if target is not None and target.derivation is None:
                continue  # directly tagged — never override a filed value
            operands = [concepts.get(name) for name in rule.operands]
            if any(operand is None for operand in operands):
                if target is not None:
                    # A previously derived target is no longer valid when an
                    # operand disappears after supersession. Do not leave the
                    # old value in the current-facts view; there is no
                    # replacement row because the rule cannot be evaluated.
                    await _retire_current_fact(session, target)
                    if counts is not None:
                        counts["canonical_facts_superseded"] += 1
                continue
            if not _sources_satisfy(rule, concepts, source_of):
                if target is not None:
                    # An amendment can deliberately move an operand from an
                    # allowed source tag to a disallowed one. The derivation
                    # must then disappear from current facts rather than
                    # continue exposing the value computed from the old
                    # measurement basis.
                    await _retire_current_fact(session, target)
                    if counts is not None:
                        counts["canonical_facts_superseded"] += 1
                continue

            left, right = operands
            if rule.operation == "subtract":
                value = Decimal(str(left.value)) - Decimal(str(right.value))
            elif rule.operation == "add":
                value = Decimal(str(left.value)) + Decimal(str(right.value))
            else:  # pragma: no cover - load_mapping_spec rejects unknown operations
                raise ValueError(f"unsupported derivation operation: {rule.operation!r}")

            anchor = concepts[rule.provenance_from]
            if (
                target is not None
                and Decimal(str(target.value)) == value
                and target.accession_number == anchor.accession_number
            ):
                continue  # operands unchanged since this row was derived

            derived = CanonicalFact(
                issuer_cik=issuer_cik,
                accession_number=anchor.accession_number,
                canonical_concept=rule.canonical_concept,
                fiscal_year=fiscal_year,
                period_end=anchor.period_end,
                value=value,
                unit=anchor.unit,
                mapping_version=mapping_version,
                derivation=rule.rule,
                selected_from_raw_fact_id=None,
            )
            if target is not None:
                await _supersede(session, target, derived)
                if counts is not None:
                    counts["canonical_facts_superseded"] += 1
            else:
                session.add(derived)
            added += 1
    return added


async def _supersede(session: AsyncSession, old: CanonicalFact, new: CanonicalFact) -> None:
    """Retire `old` in favour of `new` without ever holding two CURRENT rows.

    The uniqueness guard is a partial index over `NOT superseded`, checked per
    statement, and SQLAlchemy's unit of work emits INSERTs before UPDATEs within
    one flush — so the retirement must reach the database BEFORE the insert,
    and the back-reference (an FK to the new row's id) only after it. Three
    small flushes on a rare path, in exchange for the invariant never being
    false even transiently."""
    old.superseded = True
    await session.flush()
    session.add(new)
    await session.flush()
    old.superseded_by = new.id


async def _retire_current_fact(session: AsyncSession, fact: CanonicalFact) -> None:
    """Remove an invalid current fact from the current view without inventing a
    replacement.

    ``superseded_by`` remains NULL intentionally: the fact lost its eligible
    source or its derivation stopped being valid, so there is no new canonical
    row to point at. The prior row remains queryable for historical provenance.
    """
    fact.superseded = True
    await session.flush()


async def _source_concepts(
    session: AsyncSession, facts: list[CanonicalFact]
) -> dict[uuid.UUID, str]:
    """canonical_fact.id -> the source XBRL concept it was selected from.

    A derived fact has no source concept (selected_from_raw_fact_id is None) and is
    simply absent from the mapping, so it can never satisfy a requires_source
    constraint — correct, since a rule constrained to a specific filed tag must not
    be fed another computed value."""
    raw_ids = {f.selected_from_raw_fact_id: f.id for f in facts if f.selected_from_raw_fact_id}
    if not raw_ids:
        return {}
    rows = (
        await session.execute(select(RawFact.id, RawFact.concept).where(RawFact.id.in_(raw_ids)))
    ).all()
    return {raw_ids[raw_id]: concept for raw_id, concept in rows}


def _sources_satisfy(
    rule, concepts: dict[str, CanonicalFact], source_of: dict[uuid.UUID, str]
) -> bool:
    """True when every constrained operand resolved from an allowed source concept.

    Guards against an operand that is canonically correct but measures the wrong
    thing — Suncor's inventories-only cogs would overstate a derived gross profit.
    """
    for operand, allowed in rule.requires_source:
        if source_of.get(concepts[operand].id) not in allowed:
            return False
    return True
