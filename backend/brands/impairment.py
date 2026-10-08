"""Materialize brand impairment at the level the filing supports (Story 13.4d, AD-1).

CPB charges write-downs to named brands; ZTS reports them only company-wide, under
a concept that covers every intangible; QSR reports none. A row per brand-year
records which of those is true (`level`) beside the figure, so no consumer ever
has to infer it — and a company-level charge is never attributed to a brand.

Values come only from filed member-level charges. Everywhere else the row is
`insufficient_data` with a declared reason code, never a zero: even CPB's
complete per-brand set (its charges sum exactly to the consolidated figure) would
make a "0 for Kettle" ThesisTrace's number, not the filer's (decision D-e).

Selection reuses 13.4c's identity resolution and its basis/tie rules, so a charge
is chosen exactly the way a carrying value is.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BrandFigure, CanonicalMemberFact
from brands.store import (
    INSUFFICIENT,
    OK,
    CarryingValueSpec,
    _basis,
    _Candidate,
    _choose,
    _Figure,
    _identity_axes,
    load_carrying_value_spec,
    parse_spec,
)
from canonicalization.mappings import DIMENSIONED_RULES, MAPPING_VERSION, resolve_brand_identity
from formulas.engine import load_spec, round_ratio, to_decimal

FORMULA_VERSION = "brand_impairment_v1"
LEVELS = ("brand", "filer_only", "none")
IMPAIRMENT_CONCEPT = "brand_intangible_impairment"
CARRYING_MODEL = "brand_carrying_value"

# What an absent charge means at each level. The code applies exactly these; the
# spec must declare exactly these (one place says what, the other says why).
NO_CHARGE_REASON = {
    "brand": "no_impairment_disclosed_for_brand",
    "filer_only": "impairment_reported_only_at_filer_level",
    "none": "filer_tags_no_impairment",
}
UNDECLARED = "impairment_level_undeclared"


@dataclass(frozen=True)
class ImpairmentSpec:
    common: CarryingValueSpec  # figure, inputs, basis, policy, rounding — 13.4c's checks
    row_set_from: str
    levels: dict[str, str]
    reasons: frozenset[str]


def parse_impairment_spec(formula) -> ImpairmentSpec:
    """13.4c's checks, then the level declarations against what is EXECUTED."""
    common = parse_spec(formula)
    raw = formula.raw
    version = formula.formula_version

    # The level check below is only meaningful for the IMPAIRMENT concept. Validating
    # whichever concepts `inputs` named let `brand_intangible_acquired` through, and
    # Rao's 2.8bn purchase value was stored as a write-down (Codex round, F1).
    if common.inputs != (IMPAIRMENT_CONCEPT,):
        raise ValueError(
            f"{version}: inputs must be exactly [{IMPAIRMENT_CONCEPT!r}], got "
            f"{list(common.inputs)} — any other concept would be stored as a charge"
        )

    row_set_from = raw.get("row_set_from")
    if not row_set_from:
        raise ValueError(f"{version}: declares no row_set_from")
    # "Loadable" is not enough: this spec loads too, and naming itself made last
    # night's impairment rows tonight's row set, so a vanished brand-year could never
    # be removed (Codex round, F2). The source must be a carrying-value model.
    source = load_carrying_value_spec(row_set_from)
    if row_set_from == version or source.formula.model != CARRYING_MODEL:
        raise ValueError(
            f"{version}: row_set_from {row_set_from!r} is model "
            f"{source.formula.model!r}; it must be a {CARRYING_MODEL!r} carrying-value spec"
        )

    levels = {cik: body["level"] for cik, body in (raw.get("levels") or {}).items()}
    bad = sorted({lvl for lvl in levels.values() if lvl not in LEVELS})
    if bad:
        raise ValueError(f"{version}: unknown level(s) {bad}; allowed {list(LEVELS)}")

    # A filer is `brand` exactly when a dimensioned rule maps a charge for it.
    rules = [r for r in DIMENSIONED_RULES if r.canonical_concept in common.inputs]
    if any(not r.issuers for r in rules):
        raise ValueError(
            f"{version}: an impairment rule applies to every filer, so no filer could be "
            "declared below `brand` without contradicting it"
        )
    mapped = {cik for r in rules for cik in r.issuers}
    for cik in sorted(mapped):
        if levels.get(cik) != "brand":
            raise ValueError(
                f"{version}: filer {cik} has a mapped per-brand impairment rule but is "
                f"declared {levels.get(cik)!r}, not 'brand'"
            )
    for cik, level in sorted(levels.items()):
        if level == "brand" and cik not in mapped:
            raise ValueError(
                f"{version}: filer {cik} is declared 'brand' but no dimensioned rule maps "
                "its impairment — it would never resolve a charge"
            )

    reasons = frozenset((raw.get("reasons") or {}).keys())
    applied = frozenset(NO_CHARGE_REASON.values()) | {UNDECLARED}
    if reasons != applied:
        raise ValueError(
            f"{version}: reasons must be exactly those the code applies; "
            f"undeclared {sorted(applied - reasons)}, unapplied {sorted(reasons - applied)}"
        )
    return ImpairmentSpec(common=common, row_set_from=row_set_from, levels=levels, reasons=reasons)


@lru_cache(maxsize=None)
def load_impairment_spec(formula_version: str = FORMULA_VERSION) -> ImpairmentSpec:
    return parse_impairment_spec(load_spec(formula_version))


async def materialize_brand_impairments(
    session: AsyncSession,
    issuer_cik: str,
    *,
    formula_version: str = FORMULA_VERSION,
) -> dict[str, int]:
    """Write this issuer's impairment rows; return what happened.

    Runs AFTER `materialize_brand_carrying_values`: its row set is the carrying-value
    brand-years that stage just wrote.
    """
    spec = load_impairment_spec(formula_version)
    common = spec.common
    carrying = load_carrying_value_spec(spec.row_set_from)
    level = spec.levels.get(issuer_cik)

    figures: dict[tuple[str, int], _Figure] = {}
    for row in (
        await session.execute(
            select(BrandFigure).where(
                BrandFigure.issuer_cik == issuer_cik,
                BrandFigure.figure == carrying.figure,
                BrandFigure.formula_version == carrying.formula.formula_version,
                BrandFigure.mapping_version == MAPPING_VERSION,
            )
        )
    ).scalars():
        figures[(row.brand_key, row.fiscal_year)] = _Figure(
            brand_key=row.brand_key, kind=row.kind, source_axis=row.source_axis,
            fiscal_year=row.fiscal_year,
        )

    unresolved = 0
    charges = (
        await session.execute(
            select(CanonicalMemberFact).where(
                CanonicalMemberFact.issuer_cik == issuer_cik,
                CanonicalMemberFact.canonical_concept.in_(common.inputs),
                CanonicalMemberFact.mapping_version == MAPPING_VERSION,
                CanonicalMemberFact.superseded.is_(False),
            )
        )
    ).scalars().all()
    identity_axes = _identity_axes(issuer_cik)
    for row in charges:
        identity = resolve_brand_identity(row.issuer_cik, row.member_key, row.context_key)
        if not identity:
            unresolved += 1
            continue
        key = (identity.brand_key, row.fiscal_year)
        figure = figures.get(key)
        if figure is None:  # a charge on a brand-year with no carrying value (D-g)
            figure = figures[key] = _Figure(
                brand_key=identity.brand_key, kind=identity.kind,
                source_axis=identity.source_axis, fiscal_year=row.fiscal_year,
            )
        basis, reason = _basis(row, identity_axes, common.basis)
        figure.candidates.append(_Candidate(row=row, basis=basis, reason=reason))

    written: list[tuple[str, int]] = []
    insufficient = 0
    for key, figure in sorted(figures.items()):
        values = {
            "issuer_cik": issuer_cik,
            "brand_key": figure.brand_key,
            "figure": common.figure,
            "fiscal_year": figure.fiscal_year,
            "formula_version": common.formula.formula_version,
            "mapping_version": MAPPING_VERSION,
            "kind": figure.kind,
            "source_axis": figure.source_axis,
            "level": level,
            "computed_at": func.now(),
            "caveats": [],
        }
        winner, reason = (None, None)
        if level is None:
            reason = UNDECLARED
        elif not figure.candidates:
            reason = NO_CHARGE_REASON[level]
        else:
            winner, reason = _choose(figure, common.basis)
        if winner is None:
            insufficient += 1
            values.update(
                basis=None, period_end=None, value=None, unit=None, status=INSUFFICIENT,
                reason=(reason or "unresolved")[:512], source_member_fact_id=None,
            )
        else:
            values.update(
                basis=winner.basis,
                period_end=winner.row.period_end,
                value=round_ratio(to_decimal(winner.row.value), common.formula),
                unit=winner.row.unit,
                status=OK,
                reason=None,
                source_member_fact_id=winner.row.id,
            )
        statement = pg_insert(BrandFigure).values(**values)
        statement = statement.on_conflict_do_update(
            constraint="uq_brand_figures_key",
            set_={
                column: statement.excluded[column]
                for column in values
                if column not in {
                    "issuer_cik", "brand_key", "figure", "fiscal_year",
                    "formula_version", "mapping_version",
                }
            },
        )
        await session.execute(statement)
        written.append(key)

    # Scoped to THIS figure and version pair: it can never remove a carrying value,
    # and 13.4c's own delete (scoped to its figure) can never remove these.
    stale = delete(BrandFigure).where(
        BrandFigure.issuer_cik == issuer_cik,
        BrandFigure.figure == common.figure,
        BrandFigure.formula_version == common.formula.formula_version,
        BrandFigure.mapping_version == MAPPING_VERSION,
    )
    if written:
        stale = stale.where(tuple_(BrandFigure.brand_key, BrandFigure.fiscal_year).not_in(written))
    removed = (await session.execute(stale)).rowcount or 0

    return {
        "written": len(written),
        "removed": removed,
        "unresolved": unresolved,
        "insufficient": insufficient,
    }
