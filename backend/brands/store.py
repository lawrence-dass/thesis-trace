"""Materialize each brand's carrying value per fiscal year (Story 13.4c, AD-1).

Reads the FILED per-member rows canonicalization stored in
`canonical_member_facts`, resolves each to the brand it is about through 13.4a's
`resolve_brand_identity`, and writes ONE figure per brand-year into
`brand_figures`. Runs on the write path only; nothing on the read path computes
this series, so a fresh database has none until the pipeline runs.

What this computes is a SELECTION, not arithmetic — the values are the filer's own
— and every selection rule lives in `formulas/specs/brand_carrying_value_v1.yaml`:

  * which concepts are read: the spec's `inputs`, used as the query filter itself;
  * the BASIS of a value, from the context's qualifier axes (anything undeclared is
    insufficient_data, never a guessed basis);
  * which row wins when several resolve to one brand-year (declared precedence; a
    tie that disagrees is insufficient_data — never a pick, never a sum);
  * the `pre_acquisition_comparative` caveat, which annotates and never alters.

Residual and total rows are materialized as their own series under their own
brand key. Nothing here adds named brands together: CPB FY2021's filed total is
2,549m while its named brands plus residual reach 2,867m (us-gaap_v16).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BrandFigure, CanonicalMemberFact
from canonicalization.mappings import (
    BRAND_MEMBERS,
    DIMENSIONED_RULES,
    MAPPING_VERSION,
    SEGMENT_BRAND_MEMBERS,
    resolve_brand_identity,
)
from formulas.engine import FormulaSpec, load_spec, round_ratio, to_decimal

FORMULA_VERSION = "brand_carrying_value_v1"
OK = "ok"
INSUFFICIENT = "insufficient_data"
PRE_ACQUISITION = "pre_acquisition_comparative"


@dataclass(frozen=True)
class BasisRules:
    unqualified: str
    qualifiers: dict[tuple[str, str], str]  # (axis, member) -> basis
    precedence: tuple[str, ...]


@dataclass(frozen=True)
class CarryingValueSpec:
    formula: FormulaSpec
    figure: str
    inputs: tuple[str, ...]
    basis: BasisRules
    caveats: frozenset[str]


def _identity_axes(issuer_cik: str | None = None) -> frozenset[str]:
    """Axes that carry IDENTITY — for one filer, or for any filer when None.

    Derived from what the pipeline executes (`DIMENSIONED_RULES`) and from the
    identity declarations 13.4a's resolver reads, never from this spec. Anything
    else in a stored context is a qualifier.
    """
    axes: set[str] = set()
    for rule in DIMENSIONED_RULES:
        if issuer_cik is None or not rule.issuers or issuer_cik in rule.issuers:
            axes.add(rule.axis)
    for segment in SEGMENT_BRAND_MEMBERS:
        if issuer_cik is None or segment.issuer_cik == issuer_cik:
            axes.add(segment.axis)
    for member in BRAND_MEMBERS:
        if member.brand_axis and (issuer_cik is None or member.issuer_cik == issuer_cik):
            axes.add(member.brand_axis)
    return frozenset(axes)


def parse_spec(formula: FormulaSpec) -> CarryingValueSpec:
    """Validate the spec against what the pipeline really does, then freeze it.

    Each check compares a declaration with something EXECUTED, not with another
    line of the same file — a validator that only cross-checks declarations passes
    a consistent mistake (validated_against_a_declaration_is_not_validated).
    """
    raw = formula.raw
    version = formula.formula_version
    # Absence is always explicit here (AD-16). Validate the declaration against
    # the branch below that actually writes it, not merely another YAML field.
    if raw.get("missing_data_policy") != INSUFFICIENT or formula.missing_data_policy != INSUFFICIENT:
        raise ValueError(f"{version}: missing_data_policy must be {INSUFFICIENT!r}")
    inputs = tuple(raw.get("inputs") or ())
    if not inputs:
        raise ValueError(f"{version}: declares no inputs")
    produced = {rule.canonical_concept for rule in DIMENSIONED_RULES}
    unproduced = sorted(set(inputs) - produced)
    if unproduced:
        raise ValueError(
            f"{version}: inputs {unproduced} are produced by no dimensioned rule — "
            "the materializer would read nothing for them"
        )

    basis_raw = raw.get("basis") or {}
    identity = _identity_axes()
    qualifiers: dict[tuple[str, str], str] = {}
    for entry in basis_raw.get("qualifiers") or ():
        if entry["axis"] in identity:
            raise ValueError(
                f"{version}: basis qualifier {entry['axis']} is an identity axis — it "
                "names WHICH brand a row is, so it cannot also decide the value's basis"
            )
        qualifiers[(entry["axis"], entry["member"])] = entry["basis"]
    unqualified = basis_raw.get("unqualified")
    precedence = tuple(basis_raw.get("precedence") or ())
    declared_bases = {unqualified, *qualifiers.values()}
    if not unqualified or set(precedence) != declared_bases or len(precedence) != len(
        declared_bases
    ):
        raise ValueError(
            f"{version}: basis precedence {list(precedence)} must order every declared "
            f"basis exactly once: {sorted(b for b in declared_bases if b)}"
        )

    caveats = frozenset((raw.get("caveats") or {}).keys())
    unknown = caveats - {PRE_ACQUISITION}
    if unknown:
        raise ValueError(f"{version}: caveats {sorted(unknown)} are applied by no code")

    return CarryingValueSpec(
        formula=formula,
        figure=raw["figure"],
        inputs=inputs,
        basis=BasisRules(unqualified=unqualified, qualifiers=qualifiers, precedence=precedence),
        caveats=caveats,
    )


@lru_cache(maxsize=None)
def load_carrying_value_spec(formula_version: str = FORMULA_VERSION) -> CarryingValueSpec:
    return parse_spec(load_spec(formula_version))


@dataclass
class _Candidate:
    row: CanonicalMemberFact
    basis: str | None
    reason: str | None


@dataclass
class _Figure:
    brand_key: str
    kind: str
    source_axis: str
    fiscal_year: int
    candidates: list[_Candidate] = field(default_factory=list)


def _basis(row: CanonicalMemberFact, identity_axes: frozenset[str], rules: BasisRules):
    """(basis, None) for a declared shape, or (None, reason) naming what is not."""
    qualifiers = sorted(
        (str(axis), str(member))
        for axis, member in (row.context_key or {}).items()
        if axis not in identity_axes
    )
    if not qualifiers:
        return rules.unqualified, None
    if len(qualifiers) == 1 and qualifiers[0] in rules.qualifiers:
        return rules.qualifiers[qualifiers[0]], None
    return None, f"context qualifier(s) {qualifiers} declare no basis in the spec"


def _choose(figure: _Figure, rules: BasisRules) -> tuple[_Candidate | None, str | None]:
    """The one winning candidate, or (None, reason). Never a pick, never a sum."""
    # AC 5 applies to the whole brand-year. Precedence can choose between known
    # bases, but must never hide an unexplained measurement beside the winner.
    unknown = [c for c in figure.candidates if c.basis is None]
    if unknown:
        return None, "; ".join(sorted({c.reason for c in unknown if c.reason}))
    declared = figure.candidates
    for basis in rules.precedence:
        tier = [c for c in declared if c.basis == basis]
        if not tier:
            continue
        values = {Decimal(str(c.row.value)) for c in tier}
        if len(values) == 1:
            # Several rows with ONE value (e.g. two contexts restating it) agree;
            # cite the earliest-stored for a stable provenance pointer.
            return min(tier, key=lambda c: str(c.row.id)), None
        ids = sorted(str(c.row.id) for c in tier)
        return None, f"{len(tier)} {basis} rows disagree for this brand-year: {ids}"
    return None, "no candidate carries a declared basis"


async def materialize_brand_carrying_values(
    session: AsyncSession,
    issuer_cik: str,
    *,
    formula_version: str = FORMULA_VERSION,
) -> dict[str, int]:
    """Write this issuer's per-brand carrying values; return what happened."""
    spec = load_carrying_value_spec(formula_version)
    rows = (
        await session.execute(
            select(CanonicalMemberFact).where(
                CanonicalMemberFact.issuer_cik == issuer_cik,
                CanonicalMemberFact.canonical_concept.in_(spec.inputs),
                CanonicalMemberFact.mapping_version == MAPPING_VERSION,
                CanonicalMemberFact.superseded.is_(False),
            )
        )
    ).scalars().all()

    identity_axes = _identity_axes(issuer_cik)
    figures: dict[tuple[str, int], _Figure] = {}
    unresolved = 0
    for row in rows:
        # Resolved under the CURRENT spec, and only current-version rows are read,
        # so identity and facts come from one version (closes
        # deferred_version_blind_resolution for materialized figures).
        identity = resolve_brand_identity(row.issuer_cik, row.member_key, row.context_key)
        if not identity:
            unresolved += 1
            continue
        key = (identity.brand_key, row.fiscal_year)
        figure = figures.get(key)
        if figure is None:
            figure = figures[key] = _Figure(
                brand_key=identity.brand_key,
                kind=identity.kind,
                source_axis=identity.source_axis,
                fiscal_year=row.fiscal_year,
            )
        basis, reason = _basis(row, identity_axes, spec.basis)
        figure.candidates.append(_Candidate(row=row, basis=basis, reason=reason))

    chosen: dict[tuple[str, int], tuple[_Candidate | None, str | None]] = {
        key: _choose(figure, spec.basis) for key, figure in figures.items()
    }
    pre_acquisition = _pre_acquisition_years(chosen) if PRE_ACQUISITION in spec.caveats else set()

    written: list[tuple[str, int]] = []
    insufficient = 0
    for key, figure in sorted(figures.items()):
        winner, reason = chosen[key]
        values = {
            "issuer_cik": issuer_cik,
            "brand_key": figure.brand_key,
            "figure": spec.figure,
            "fiscal_year": figure.fiscal_year,
            "formula_version": spec.formula.formula_version,
            "mapping_version": MAPPING_VERSION,
            "kind": figure.kind,
            "source_axis": figure.source_axis,
            "computed_at": func.now(),
        }
        if winner is None:
            insufficient += 1
            values.update(
                basis=None, period_end=None, value=None, unit=None, status=INSUFFICIENT,
                reason=(reason or "unresolved")[:512], caveats=[],
                source_member_fact_id=None,
            )
        else:
            values.update(
                basis=winner.basis,
                period_end=winner.row.period_end,
                # Through the shared engine (AD-15). A filed amount at the storage
                # scale quantizes to itself; a test pins that.
                value=round_ratio(to_decimal(winner.row.value), spec.formula),
                unit=winner.row.unit,
                status=OK,
                reason=None,
                caveats=[PRE_ACQUISITION] if key in pre_acquisition else [],
                source_member_fact_id=winner.row.id,
            )
        statement = pg_insert(BrandFigure).values(**values)
        # Refresh every non-key column: a partial update would let a brand-year that
        # turned insufficient keep last night's value beside tonight's reason.
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

    # A brand-year that stopped resolving under the SAME versions must not linger
    # beside tonight's set. Other version pairs are history and are never touched.
    stale = delete(BrandFigure).where(
        BrandFigure.issuer_cik == issuer_cik,
        BrandFigure.figure == spec.figure,
        BrandFigure.formula_version == spec.formula.formula_version,
        BrandFigure.mapping_version == MAPPING_VERSION,
    )
    if written:
        stale = stale.where(
            tuple_(BrandFigure.brand_key, BrandFigure.fiscal_year).not_in(written)
        )
    removed = (await session.execute(stale)).rowcount or 0

    return {
        "written": len(written),
        "removed": removed,
        "unresolved": unresolved,
        "insufficient": insufficient,
    }


def _pre_acquisition_years(chosen) -> set[tuple[str, int]]:
    """Brand-years matching the spec's pre_acquisition_comparative rule.

    A resolved filed zero in the brand's EARLIEST materialized year, with a later
    resolved value > 0. Insufficient years still establish the series start, but
    cannot supply a numeric baseline or prove a later positive.
    """
    by_brand: dict[str, list[tuple[int, Decimal | None]]] = defaultdict(list)
    for (brand_key, year), (winner, _) in chosen.items():
        value = Decimal(str(winner.row.value)) if winner is not None else None
        by_brand[brand_key].append((year, value))
    flagged: set[tuple[str, int]] = set()
    for brand_key, series in by_brand.items():
        series.sort(key=lambda item: item[0])
        first_year, first_value = series[0]
        if first_value == 0 and any(value is not None and value > 0 for _, value in series[1:]):
            flagged.add((brand_key, first_year))
    return flagged
