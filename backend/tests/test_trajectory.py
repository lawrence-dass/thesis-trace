"""Story 5.5 — trajectory-over-level (PRD OQ9).

A ThesisTrace presentation rule, so the tests care about two things above all:
that POLARITY is respected per model (a falling Beneish M-score is an
improvement, a falling Piotroski F-score is not), and that the rule never
alters a score.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest
import yaml

from trajectory.engine import (
    SPEC_PATH,
    Direction,
    TrajectorySpecError,
    classify,
    load_trajectory_spec,
    trajectories_for_scores,
)


@dataclass
class FakeScore:
    model: str
    fiscal_year: int
    aggregate_value: Decimal | None


# --- Polarity: the thing most likely to be silently wrong ------------------


@pytest.mark.parametrize(
    "model,prior,current,expected",
    [
        # Higher-is-better models.
        ("piotroski", 5, 7, Direction.improving),
        ("piotroski", 7, 5, Direction.deteriorating),
        ("altman", 1.5, 3.0, Direction.improving),
        ("altman", 3.0, 1.5, Direction.deteriorating),
        # LOWER-is-better models — both measure a risk, so a falling value is
        # the improvement. Inverting these would tell a reader that rising
        # manipulation risk is good news.
        ("beneish", -1.5, -2.5, Direction.improving),
        ("beneish", -2.5, -1.5, Direction.deteriorating),
        ("sloan", 0.12, 0.02, Direction.improving),
        ("sloan", 0.02, 0.12, Direction.deteriorating),
    ],
)
def test_polarity_is_respected_per_model(model, prior, current, expected) -> None:
    t = classify(
        model, to_fiscal_year=2024, to_value=current, from_fiscal_year=2023, from_value=prior
    )
    assert t.direction is expected


def test_a_falling_number_is_not_universally_a_decline() -> None:
    """The single clearest statement of the polarity rule.

    Same directional move, opposite meanings, because the models measure
    opposite things.
    """
    piotroski = classify(
        "piotroski", to_fiscal_year=2024, to_value=5, from_fiscal_year=2023, from_value=7
    )
    beneish = classify(
        "beneish", to_fiscal_year=2024, to_value=-2.5, from_fiscal_year=2023, from_value=-1.5
    )
    assert piotroski.direction is Direction.deteriorating
    assert beneish.direction is Direction.improving


# --- Materiality and history ----------------------------------------------


def test_a_move_below_the_materiality_threshold_is_stable() -> None:
    t = classify("sloan", to_fiscal_year=2024, to_value=0.021, from_fiscal_year=2023, from_value=0.020)
    assert t.direction is Direction.stable


def test_no_prior_year_is_insufficient_history_not_stable(  ) -> None:
    """AD-16: absence is never a value. 'We could not compare' must not render
    as 'we compared and nothing moved'."""
    t = classify("altman", to_fiscal_year=2024, to_value=3.0)
    assert t.direction is Direction.insufficient_history
    assert t.direction is not Direction.stable


def test_a_gap_in_history_is_not_compared_across_the_gap() -> None:
    """FY2021 vs FY2024 is not a trajectory — it silently spans three years."""
    t = classify(
        "altman", to_fiscal_year=2024, to_value=3.0, from_fiscal_year=2021, from_value=1.0
    )
    assert t.direction is Direction.insufficient_history


def test_a_missing_value_yields_insufficient_history() -> None:
    t = classify(
        "piotroski", to_fiscal_year=2024, to_value=None, from_fiscal_year=2023, from_value=6
    )
    assert t.direction is Direction.insufficient_history


def test_an_undeclared_model_gets_no_direction_rather_than_an_assumed_one() -> None:
    """A future model with no declared polarity must not be guessed at."""
    t = classify(
        "some_future_model", to_fiscal_year=2024, to_value=9, from_fiscal_year=2023, from_value=1
    )
    assert t.direction is Direction.insufficient_history


# --- The rule must never alter a score ------------------------------------


def test_trajectory_never_changes_the_underlying_values() -> None:
    """The standing rule: a caveat may annotate a score, never alter one."""
    scores = [
        FakeScore("piotroski", 2023, Decimal("6")),
        FakeScore("piotroski", 2024, Decimal("8")),
    ]
    before = [(s.model, s.fiscal_year, s.aggregate_value) for s in scores]
    trajectories_for_scores(scores)
    after = [(s.model, s.fiscal_year, s.aggregate_value) for s in scores]
    assert before == after


def test_every_trajectory_carries_its_attribution() -> None:
    """A consumer must not be able to render a direction without saying whose
    judgment it is."""
    scores = [FakeScore("altman", 2023, Decimal("1.5")), FakeScore("altman", 2024, Decimal("3.0"))]
    for t in trajectories_for_scores(scores).values():
        assert t.attribution
        assert "ThesisTrace" in t.attribution
        assert t.spec_version == "trajectory_v1"


def test_trajectories_pair_consecutive_years_per_model(  ) -> None:
    scores = [
        FakeScore("piotroski", 2023, Decimal("5")),
        FakeScore("piotroski", 2024, Decimal("8")),
        FakeScore("altman", 2024, Decimal("3.0")),  # no FY2023 altman run
    ]
    out = trajectories_for_scores(scores)
    assert out[("piotroski", 2024)].direction is Direction.improving
    assert out[("piotroski", 2023)].direction is Direction.insufficient_history
    assert out[("altman", 2024)].direction is Direction.insufficient_history


# --- The spec is a presentation rule, and says so -------------------------


def test_spec_is_labelled_as_thesistrace_authored_not_academic() -> None:
    spec = load_trajectory_spec()
    assert spec["kind"] == "thesistrace_presentation_rule"
    assert spec["authored_by"] == "thesistrace"
    assert "ThesisTrace" in spec["attribution"]


def test_loader_refuses_an_academic_model_spec() -> None:
    """The four model specs carry published thresholds that are NOT ours.

    Loading one here would apply another author's numbers as though they were
    ThesisTrace presentation choices.
    """
    import trajectory.engine as eng

    original = eng.SPEC_PATH
    try:
        eng.SPEC_PATH = SPEC_PATH.parent / "sloan_v1.yaml"
        eng.load_trajectory_spec.cache_clear()
        with pytest.raises(TrajectorySpecError):
            eng.load_trajectory_spec()
    finally:
        eng.SPEC_PATH = original
        eng.load_trajectory_spec.cache_clear()


def test_every_declared_polarity_has_a_citation_and_a_materiality_threshold() -> None:
    """A direction without a stated basis is an unattributed judgment."""
    spec = yaml.safe_load(SPEC_PATH.read_text())
    for model, p in spec["polarity"].items():
        assert p["better"] in {"higher", "lower"}, model
        assert p.get("citation"), f"{model} declares polarity with no citation"
        assert model in spec["materiality"], f"{model} has polarity but no materiality threshold"


def test_materiality_thresholds_are_not_presented_as_published_figures() -> None:
    """These numbers are ours. The spec must say so, so nobody later cites them
    as Piotroski's or Sloan's."""
    spec = yaml.safe_load(SPEC_PATH.read_text())
    note = spec["materiality"]["note"].lower()
    assert "thesistrace" in note or "presentation" in note
