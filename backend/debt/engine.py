"""Near-term debt share (PRD OQ9, Story 5.6).

A ThesisTrace-authored PRESENTATION rule, not an academic model. It divides two
canonical facts and classifies the result into bands that are ours; it never
adjusts a model score and is never blended into one. Every threshold comes from
`formulas/specs/near_term_debt_share_v1.yaml`, where it is labelled as ours.

Two things here are easy to get wrong, and both are decided by data rather than
by code:

  * A FILED ZERO IS A VALUE. Cameco reports a current portion of exactly zero in
    four fiscal years — none of its debt matured within twelve months. That is a
    real 0.0%, not missing data. Only an ABSENT operand is insufficient_data.
    AD-16 forbids defaulting an absence to zero; it does not licence discarding a
    zero the filer actually reported.

  * THE DENOMINATOR IS NEVER `long_term_debt` ALONE. That concept is the
    NONCURRENT half for most filers, so dividing by it would overstate the share
    (and for CP it is a lease-inclusive total, so it would not even be consistent
    year to year). The denominator is the `total_debt` canonical concept, which is
    either filed directly or built by the total_debt_current_plus_noncurrent
    identity in derivations_v3.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "formulas" / "specs" / "near_term_debt_share_v1.yaml"

NUMERATOR_CONCEPT = "near_term_debt"
DENOMINATOR_CONCEPT = "total_debt"


class NearTermDebtShareSpecError(Exception):
    """The spec is missing, malformed, or is not a presentation rule."""


@dataclass(frozen=True)
class NearTermDebtShare:
    fiscal_year: int
    #: None exactly when the figure is insufficient_data.
    value: Decimal | None
    label: str
    tone: str | None
    near_term_debt: Decimal | None
    total_debt: Decimal | None
    insufficient_data: bool
    #: Always populated, so a consumer cannot render the figure without saying
    #: whose judgment the bands represent.
    attribution: str
    spec_version: str


@lru_cache(maxsize=1)
def load_spec() -> dict:
    """Load the versioned rule.

    Rejects anything that is not explicitly a ThesisTrace presentation rule, so
    this loader can never be pointed at one of the four academic model specs and
    quietly apply their thresholds as if they were ours (or vice versa).
    """
    if not SPEC_PATH.exists():
        raise NearTermDebtShareSpecError(f"Near-term debt share spec not found: {SPEC_PATH}")
    data = yaml.safe_load(SPEC_PATH.read_text())
    if data.get("kind") != "thesistrace_presentation_rule":
        raise NearTermDebtShareSpecError(
            f"{SPEC_PATH.name} is not a thesistrace_presentation_rule; refusing to load it "
            "as one. Academic model specs must not be applied as presentation rules."
        )
    for required in ("bands", "labels", "attribution", "spec_version", "formula", "polarity"):
        if required not in data:
            raise NearTermDebtShareSpecError(f"Near-term debt share spec missing {required!r}")

    tiers = data["bands"].get("tiers")
    if not tiers:
        raise NearTermDebtShareSpecError("Near-term debt share spec declares no bands.tiers")
    if tiers[-1].get("max") is not None:
        raise NearTermDebtShareSpecError(
            "The last band must have a null max — without an open-ended top tier a "
            "sufficiently high share would fall through and be reported as no band at all."
        )

    # The formula is published on the methodology page AND applied here. If the two
    # drift apart, the page describes a calculation the code is not doing.
    formula = data["formula"]
    if formula.get("numerator") != NUMERATOR_CONCEPT or formula.get("denominator") != DENOMINATOR_CONCEPT:
        raise NearTermDebtShareSpecError(
            f"Spec declares {formula.get('numerator')!r} / {formula.get('denominator')!r} but the "
            f"engine reads {NUMERATOR_CONCEPT!r} / {DENOMINATOR_CONCEPT!r}"
        )
    return data


ATTRIBUTION = load_spec()["attribution"].strip()


def _band(value: Decimal) -> tuple[str, str]:
    for tier in load_spec()["bands"]["tiers"]:
        ceiling = tier.get("max")
        if ceiling is None or value <= Decimal(str(ceiling)):
            return tier["label"], tier["tone"]
    raise AssertionError("unreachable — load_spec guarantees an open-ended final tier")


def _dec(v) -> Decimal | None:
    if v is None:
        return None
    return v if isinstance(v, Decimal) else Decimal(str(v))


def compute(
    *,
    fiscal_year: int,
    near_term_debt: Decimal | float | None,
    total_debt: Decimal | float | None,
) -> NearTermDebtShare:
    """The near-term share for one filer-year.

    Returns insufficient_data — never a defaulted 0.0 — when either operand is
    absent, or when total debt is zero (a company with no debt has no maturity
    profile to report; dividing would be undefined, and calling it 0% would imply
    a well-spread schedule that does not exist).
    """
    spec = load_spec()
    numerator, denominator = _dec(near_term_debt), _dec(total_debt)

    if numerator is None or denominator is None or denominator == 0:
        return NearTermDebtShare(
            fiscal_year=fiscal_year,
            value=None,
            label=spec["labels"]["insufficient_data"],
            tone=None,
            near_term_debt=numerator,
            total_debt=denominator,
            insufficient_data=True,
            attribution=ATTRIBUTION,
            spec_version=spec["spec_version"],
        )

    value = numerator / denominator
    label, tone = _band(value)
    return NearTermDebtShare(
        fiscal_year=fiscal_year,
        value=value,
        label=label,
        tone=tone,
        near_term_debt=numerator,
        total_debt=denominator,
        insufficient_data=False,
        attribution=ATTRIBUTION,
        spec_version=spec["spec_version"],
    )


def shares_for_facts(facts) -> dict[int, NearTermDebtShare]:
    """Near-term share per fiscal year over an already-loaded canonical-fact list.

    Takes facts the caller has already fetched rather than issuing its own query —
    the read path stays one pass over materialized rows (AD-1), and this cannot
    become an N+1.

    `facts` items need only `.canonical_concept`, `.fiscal_year` and `.value`.
    """
    by_year: dict[int, dict[str, object]] = {}
    for fact in facts:
        if fact.canonical_concept in (NUMERATOR_CONCEPT, DENOMINATOR_CONCEPT):
            by_year.setdefault(fact.fiscal_year, {})[fact.canonical_concept] = fact.value

    return {
        fiscal_year: compute(
            fiscal_year=fiscal_year,
            near_term_debt=concepts.get(NUMERATOR_CONCEPT),
            total_debt=concepts.get(DENOMINATOR_CONCEPT),
        )
        for fiscal_year, concepts in by_year.items()
    }
