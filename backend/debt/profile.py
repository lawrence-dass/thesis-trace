"""Year-by-year debt maturity profile (Story 5.7).

Enrichment, not a metric. It relays a filer's own published repayment schedule;
it classifies nothing, scores nothing, and applies no thresholds.

Three things here are easy to get wrong, and all three are decided by the spec
rather than by code:

  * IT DOES NOT RECONCILE TO `total_debt`, even when the ladder is complete.
    These buckets are undiscounted contractual principal; `total_debt` is a
    balance-sheet carrying amount net of discount and issue costs. QSR FY2023's
    complete ladder sums to 13,043M against a filed total of 12,921M. This
    module therefore exposes NO total and no share-of-total, and a test asserts
    that no such attribute ever appears — because the natural way to render six
    buckets is a stacked bar summing to 100%, and that would be a lie.

  * A PROFILE MUST BE CONTIGUOUS FROM YEAR ONE AND REACH AT LEAST YEAR 2. Any
    other shape is a schedule with a hole in it or a single figure dressed as a
    schedule, and both render as complete unless refused. Four real shapes make
    this concrete:
      - OTEX tags year 1 and thereafter and never the years between (FY2012-2020).
      - OTEX tags year 1 and NOTHING else once its thereafter tag stops
        (FY2011, FY2021-2025) — the length-one case, which contiguity alone
        admits. See `_is_a_renderable_schedule` for why that is not redundant.
      - CP FY2012 tags years 2-5 but no year 1, which would render as though
        nothing at all falls due within twelve months.
      - AD-3 can drop a single bucket as `ambiguous_selection`, punching an
        invisible hole into an otherwise well-covered filer-year.
    A MISSING TAIL is the one permitted absence, and it is reported as
    `truncated` rather than hidden. Every other pattern yields no profile.

  * ABSENCE RENDERS NOTHING. This is a deliberate, scoped exception to the AD-16
    convention that absence is shown rather than hidden. AD-16 governs a signal
    inside a model that was attempted; this is supplementary disclosure detail
    that five of seven filers structurally cannot produce, so a "missing" badge
    would assert a deficiency that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "formulas" / "specs" / "debt_maturity_profile_v2.yaml"


class MaturityProfileSpecError(Exception):
    """The spec is missing, malformed, or is not a presentation rule."""


@lru_cache(maxsize=1)
def load_profile_spec() -> dict:
    """Load the versioned rule.

    Rejects anything that is not explicitly a ThesisTrace presentation rule, so
    this loader can never be pointed at one of the four academic model specs.
    """
    if not SPEC_PATH.exists():
        raise MaturityProfileSpecError(f"Maturity profile spec not found: {SPEC_PATH}")
    data = yaml.safe_load(SPEC_PATH.read_text())
    if data.get("kind") != "thesistrace_presentation_rule":
        raise MaturityProfileSpecError(
            f"{SPEC_PATH.name} is not a thesistrace_presentation_rule; refusing to load it "
            "as one. Academic model specs must not be applied as presentation rules."
        )
    for required in ("buckets", "basis", "truncation", "absence", "attribution", "spec_version"):
        if required not in data:
            raise MaturityProfileSpecError(f"Maturity profile spec missing {required!r}")

    # Shape checks, not just presence. Without these a malformed spec fails later
    # and asymmetrically — a missing `truncation.message` raises only on the
    # filer-years that happen to be truncated, so CP would 500 while QSR was fine.
    buckets = data["buckets"]
    if not isinstance(buckets, dict) or not buckets:
        raise MaturityProfileSpecError("buckets must be a non-empty mapping of concept -> label")
    if not isinstance(data["truncation"], dict) or not data["truncation"].get("message"):
        raise MaturityProfileSpecError("truncation.message is required — it is published to readers")
    if data["basis"].get("reconciles_to_total_debt") is not False:
        raise MaturityProfileSpecError(
            "basis.reconciles_to_total_debt must be declared false — the ladder is "
            "undiscounted principal and does not sum to the carrying amount."
        )

    # Both admission rules are declared in the spec AND implemented in
    # `_is_a_renderable_schedule`. Pinning them here keeps the two from drifting:
    # a spec that quietly dropped one would otherwise still load while the code
    # went on enforcing it, leaving the published rule and the actual behaviour
    # disagreeing with nothing to say which is right. v1 shipped only the first of
    # these and rendered a one-row schedule for OTEX in six fiscal years.
    for rule in ("requires_contiguous_from_year_one", "requires_at_least_one_middle_year"):
        if data.get(rule) is not True:
            raise MaturityProfileSpecError(
                f"{rule} must be declared true — it is enforced by "
                "_is_a_renderable_schedule and the spec is what publishes it."
            )

    # Bucket ORDER is load-bearing: the last key is the tail whose absence means
    # truncation, and contiguity is checked by position. Reordering the mapping
    # would silently repoint truncation detection at the wrong bucket, so the
    # expected first and last keys are pinned here rather than assumed.
    keys = list(buckets)
    if keys[0] != "debt_maturity_year_1" or keys[-1] != "debt_maturity_thereafter":
        raise MaturityProfileSpecError(
            f"buckets must run from debt_maturity_year_1 to debt_maturity_thereafter, got "
            f"{keys[0]!r}..{keys[-1]!r} — order drives truncation and contiguity detection"
        )
    return data


#: Ordered, from the spec. Order is the render order AND the contiguity order.
PROFILE_CONCEPTS: tuple[str, ...] = tuple(load_profile_spec()["buckets"])
#: The bucket whose absence means the schedule is truncated — the ONE permitted gap.
TAIL_CONCEPT = PROFILE_CONCEPTS[-1]

ATTRIBUTION = load_profile_spec()["attribution"].strip()


@dataclass(frozen=True)
class MaturityBucket:
    canonical_concept: str
    label: str
    value: Decimal
    #: Provenance (AD-19) — a value with no resolvable source is not shown as fact.
    accession_number: str
    fiscal_year: int


@dataclass(frozen=True)
class MaturityProfile:
    """Deliberately exposes no total and no share-of-total. See module docstring."""

    fiscal_year: int
    buckets: tuple[MaturityBucket, ...]
    #: True when the filer published no "after year five" figure for this year,
    #: so what is shown is only part of the debt.
    truncated: bool
    truncation_message: str | None
    #: The filer's own reporting currency. CP files in CAD, and this rule shows
    #: ABSOLUTE amounts rather than a ratio, so the unit cannot be assumed.
    unit: str
    attribution: str
    spec_version: str


def _dec(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))


def profile_for_facts(facts) -> dict[int, MaturityProfile]:
    """Maturity profile per fiscal year over an already-loaded canonical-fact list.

    Takes facts the caller has already fetched rather than issuing its own query,
    so the read path stays one pass over materialized rows (AD-1) and this cannot
    become an N+1.

    Returns an entry ONLY for years that yield a real schedule. A year with no
    middle bucket is omitted entirely rather than returned empty — the caller
    renders nothing for it, which is the point.

    `facts` items need `.canonical_concept`, `.fiscal_year`, `.value`, and — for
    provenance — `.accession_number` and `.unit`.
    """
    spec = load_profile_spec()
    labels = spec["buckets"]

    by_year: dict[int, dict[str, object]] = {}
    for fact in facts:
        if fact.canonical_concept in PROFILE_CONCEPTS:
            by_year.setdefault(fact.fiscal_year, {})[fact.canonical_concept] = fact

    profiles: dict[int, MaturityProfile] = {}
    for fiscal_year, found in by_year.items():
        present = [c for c in PROFILE_CONCEPTS if c in found]
        if not _is_a_renderable_schedule(present):
            continue

        buckets = tuple(
            MaturityBucket(
                canonical_concept=concept,
                label=labels[concept],
                value=_dec(found[concept].value),
                accession_number=getattr(found[concept], "accession_number", ""),
                fiscal_year=fiscal_year,
            )
            for concept in present
        )
        # A bucket with no resolvable accession is not shown as fact (AD-19).
        if any(not b.accession_number for b in buckets):
            continue

        truncated = TAIL_CONCEPT not in found
        profiles[fiscal_year] = MaturityProfile(
            fiscal_year=fiscal_year,
            buckets=buckets,
            truncated=truncated,
            truncation_message=spec["truncation"]["message"].strip() if truncated else None,
            unit=_single_unit(found),
            attribution=ATTRIBUTION,
            spec_version=spec["spec_version"],
        )
    return profiles


def _is_a_renderable_schedule(present: list[str]) -> bool:
    """Two conditions, and BOTH are load-bearing (spec v2).

    1. CONTIGUOUS FROM YEAR ONE. Only the tail may be absent. Every other shape
       renders as a complete schedule while omitting a bucket: CP FY2012's missing
       year 1 (which would read as nothing falling due within twelve months), or a
       single bucket dropped upstream by an AD-3 ambiguous_selection.

    2. REACHES AT LEAST YEAR 2. A lone year-1 bucket satisfies (1) — it is a
       contiguous prefix of length one — but it is not a schedule, and it renders
       as a one-row table restating the near-term debt card above it with a
       different measurement basis.

    Condition 2 is not redundant, and the history matters: it was removed during
    Story 5.7's code review on the grounds that contiguity subsumed it. It does
    not. The two rules disagree on exactly one shape, length one, and that shape
    is live — OTEX hits it in six fiscal years and rendered a bogus schedule in
    every one of them until 2026-08-05. A subsumption claim needs a test at the
    boundary where the two rules differ, which is why one now exists.
    """
    if not present or present[0] != PROFILE_CONCEPTS[0]:
        return False
    if len(present) < 2:
        return False
    expected = PROFILE_CONCEPTS[: len(present)]
    return tuple(present) == expected


def _single_unit(found: dict) -> str:
    """The filer's reporting currency, or "" when the buckets disagree.

    Not `next(iter(...))`: dict order here follows fact-iteration order, which the
    repository query does not constrain, so an arbitrary bucket would decide the
    label on the whole card. A genuine disagreement between buckets is reported as
    unknown rather than guessed — these are absolute amounts, and CP files in CAD.
    """
    units = {getattr(f, "unit", "") or "" for f in found.values()}
    units.discard("")
    return units.pop() if len(units) == 1 else ""
