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

  * A PROFILE NEEDS A MIDDLE YEAR. OTEX tags a next-twelve-months bucket and a
    thereafter bucket and never the years between. Rendering those two alone
    would imply a schedule with a hole in it, so OTEX gets no profile at all.

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

SPEC_PATH = Path(__file__).resolve().parent.parent / "formulas" / "specs" / "debt_maturity_profile_v1.yaml"


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
    if data["basis"].get("reconciles_to_total_debt") is not False:
        raise MaturityProfileSpecError(
            "basis.reconciles_to_total_debt must be declared false — the ladder is "
            "undiscounted principal and does not sum to the carrying amount."
        )
    return data


#: Ordered, from the spec. Order is the render order.
PROFILE_CONCEPTS: tuple[str, ...] = tuple(load_profile_spec()["buckets"])
#: The bucket whose absence means the schedule is truncated.
TAIL_CONCEPT = PROFILE_CONCEPTS[-1]
#: A schedule needs at least one of these to be a schedule rather than two ends.
MIDDLE_CONCEPTS = frozenset(PROFILE_CONCEPTS[1:-1])

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
        # Two ends without a middle is not a schedule (OTEX). Omit the year.
        if spec.get("requires_a_middle_year", True) and not (MIDDLE_CONCEPTS & set(found)):
            continue

        buckets = tuple(
            MaturityBucket(
                canonical_concept=concept,
                label=labels[concept],
                value=_dec(found[concept].value),
                accession_number=getattr(found[concept], "accession_number", ""),
                fiscal_year=fiscal_year,
            )
            for concept in PROFILE_CONCEPTS
            if concept in found
        )
        truncated = TAIL_CONCEPT not in found
        anchor = next(iter(found.values()))
        profiles[fiscal_year] = MaturityProfile(
            fiscal_year=fiscal_year,
            buckets=buckets,
            truncated=truncated,
            truncation_message=spec["truncation"]["message"].strip() if truncated else None,
            unit=getattr(anchor, "unit", "") or "",
            attribution=ATTRIBUTION,
            spec_version=spec["spec_version"],
        )
    return profiles
