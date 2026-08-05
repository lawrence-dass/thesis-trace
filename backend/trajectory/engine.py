"""Direction of travel for an already-computed score (PRD OQ9, Story 5.5).

A ThesisTrace-authored PRESENTATION rule, not an academic model. It reads values
the pipeline already stored and annotates them with a direction; it never
computes, adjusts or re-derives a score. Every threshold it applies comes from
`formulas/specs/trajectory_v1.yaml`, where it is labelled as ours — the standing
rule being that a caveat may annotate a score but must never alter one.

The one thing that is easy to get wrong here, and the reason polarity is data
rather than code: "improving" is NOT "the number went up". Beneish and Sloan both
measure a RISK, so a falling value is the improvement. Treating all four models
alike would tell a reader that rising manipulation risk is good news.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "formulas" / "specs" / "trajectory_v1.yaml"


class Direction(str, enum.Enum):
    improving = "improving"
    stable = "stable"
    deteriorating = "deteriorating"
    #: No immediately-preceding fiscal year to compare against. Distinct from
    #: `stable` — we did not compare and find no movement, we could not compare
    #: at all (AD-16: absence is never a value).
    insufficient_history = "insufficient_history"


@dataclass(frozen=True)
class Trajectory:
    direction: Direction
    label: str
    from_fiscal_year: int | None
    to_fiscal_year: int
    from_value: Decimal | None
    to_value: Decimal | None
    #: Always populated, so a consumer cannot render a direction without saying
    #: whose judgment it is.
    attribution: str
    spec_version: str


class TrajectorySpecError(Exception):
    """The spec is missing, malformed, or is not a presentation rule."""


@lru_cache(maxsize=1)
def load_trajectory_spec() -> dict:
    """Load the versioned rule.

    Rejects anything that is not explicitly a ThesisTrace presentation rule, so
    this loader can never be pointed at one of the four academic model specs and
    quietly apply their thresholds as if they were ours (or vice versa).
    """
    if not SPEC_PATH.exists():
        raise TrajectorySpecError(f"Trajectory spec not found: {SPEC_PATH}")
    data = yaml.safe_load(SPEC_PATH.read_text())
    if data.get("kind") != "thesistrace_presentation_rule":
        raise TrajectorySpecError(
            f"{SPEC_PATH.name} is not a thesistrace_presentation_rule; refusing to load it "
            "as one. Academic model specs must not be applied as presentation rules."
        )
    for required in ("polarity", "materiality", "labels", "attribution", "spec_version"):
        if required not in data:
            raise TrajectorySpecError(f"Trajectory spec missing '{required}'")
    return data


ATTRIBUTION = load_trajectory_spec()["attribution"].strip()


def _spec_version() -> str:
    return load_trajectory_spec()["spec_version"]


def classify(
    model: str,
    *,
    to_fiscal_year: int,
    to_value: Decimal | float | None,
    from_fiscal_year: int | None = None,
    from_value: Decimal | float | None = None,
) -> Trajectory:
    """Direction of travel for one model between two consecutive fiscal years.

    Returns `insufficient_history` — never a defaulted `stable` — when there is
    no prior year, when either value is absent, or when the model has no declared
    polarity. A model whose polarity is undeclared gets no direction rather than
    an assumed one: guessing would be exactly the invented-judgment this rule
    exists to avoid.
    """
    spec = load_trajectory_spec()
    labels = spec["labels"]

    def _insufficient() -> Trajectory:
        return Trajectory(
            direction=Direction.insufficient_history,
            label=labels["insufficient_history"],
            from_fiscal_year=from_fiscal_year,
            to_fiscal_year=to_fiscal_year,
            from_value=_dec(from_value),
            to_value=_dec(to_value),
            attribution=ATTRIBUTION,
            spec_version=_spec_version(),
        )

    polarity = spec["polarity"].get(model)
    if polarity is None or from_value is None or to_value is None or from_fiscal_year is None:
        return _insufficient()

    # A gap in history is not a comparison. Comparing FY2021 against FY2024 and
    # calling it a trajectory would silently span three years.
    if to_fiscal_year - from_fiscal_year != 1:
        return _insufficient()

    prior, current = _dec(from_value), _dec(to_value)
    delta = current - prior
    threshold = Decimal(str(spec["materiality"].get(model, 0)))

    if abs(delta) < threshold:
        direction = Direction.stable
    else:
        rose = delta > 0
        better_when_higher = polarity["better"] == "higher"
        direction = (
            Direction.improving if rose == better_when_higher else Direction.deteriorating
        )

    return Trajectory(
        direction=direction,
        label=labels[direction.value],
        from_fiscal_year=from_fiscal_year,
        to_fiscal_year=to_fiscal_year,
        from_value=prior,
        to_value=current,
        attribution=ATTRIBUTION,
        spec_version=_spec_version(),
    )


def _dec(v) -> Decimal | None:
    if v is None:
        return None
    return v if isinstance(v, Decimal) else Decimal(str(v))


def trajectories_for_scores(scores) -> dict[tuple[str, int], Trajectory]:
    """Trajectory per (model, fiscal_year) over an already-loaded score list.

    Takes the runs the overview query has already fetched rather than issuing
    its own — the read path stays one pass over materialized rows (AD-1), and
    this cannot become an N+1.

    `scores` items need only `.model`, `.fiscal_year` and `.aggregate_value`.
    """
    by_model: dict[str, dict[int, object]] = {}
    for s in scores:
        by_model.setdefault(s.model, {})[s.fiscal_year] = s

    out: dict[tuple[str, int], Trajectory] = {}
    for model, years in by_model.items():
        for fy, score in years.items():
            prior = years.get(fy - 1)
            out[(model, fy)] = classify(
                model,
                to_fiscal_year=fy,
                to_value=score.aggregate_value,
                from_fiscal_year=(fy - 1) if prior is not None else None,
                from_value=prior.aggregate_value if prior is not None else None,
            )
    return out
