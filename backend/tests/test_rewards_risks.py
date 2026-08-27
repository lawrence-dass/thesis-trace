"""Story 10.3 — rewards and risks derived from computed signals (D12).

A ThesisTrace presentation rule, so the tests care about three things above
all: it selects from ALREADY-published bands rather than inventing a new
classification, an empty result is honest (never padded), and the spec's
declared inputs cover what the engine actually reads (the piotroski_v1
inputs lesson — a formula spec's `inputs` list is load-bearing, not
documentation).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from rewards_risks.engine import (
    SPEC_PATH,
    RewardRiskKind,
    RewardsRisksSpecError,
    load_rewards_risks_spec,
    rewards_risks_for_overview,
)

ENGINE_PATH = Path(__file__).resolve().parents[1] / "rewards_risks" / "engine.py"


@dataclass
class FakeVerdict:
    model: str
    category: str
    fiscal_year: int
    aggregate_value: float | None
    band_label: str | None


@dataclass
class FakeDataQuality:
    issue_type: str
    accession_number: str | None = None


# --- Selection: only the model's OWN published reward/risk band fires ------


def test_a_reward_band_produces_one_reward_bullet() -> None:
    verdict = [FakeVerdict("piotroski", "quality_health", 2025, 9, "Strong")]
    items = rewards_risks_for_overview(verdict, [])
    assert len(items) == 1
    assert items[0].kind is RewardRiskKind.reward
    assert items[0].model == "piotroski"
    assert items[0].fiscal_year == 2025
    assert items[0].section == "financial-health"
    assert "Piotroski F-Score" in items[0].text
    assert "Strong" in items[0].text
    assert "2025" in items[0].text


def test_a_risk_band_produces_one_risk_bullet() -> None:
    verdict = [FakeVerdict("beneish", "integrity", 2024, -1.2, "Manipulation risk flagged")]
    items = rewards_risks_for_overview(verdict, [])
    assert len(items) == 1
    assert items[0].kind is RewardRiskKind.risk
    assert items[0].section == "integrity-evidence"
    assert "Beneish M-Score" in items[0].text


def test_a_middle_band_produces_nothing() -> None:
    """Not every band is headline-worthy — a Piotroski 'Middle' is neither the
    model's best nor its worst published band."""
    verdict = [FakeVerdict("piotroski", "quality_health", 2025, 5, "Middle")]
    assert rewards_risks_for_overview(verdict, []) == []


@pytest.mark.parametrize(
    "model,category,band,expected_kind",
    [
        ("piotroski", "quality_health", "Strong", RewardRiskKind.reward),
        ("piotroski", "quality_health", "Weak", RewardRiskKind.risk),
        ("altman", "quality_health", "Safe", RewardRiskKind.reward),
        ("altman", "quality_health", "Distress", RewardRiskKind.risk),
        ("beneish", "integrity", "No manipulation flag", RewardRiskKind.reward),
        ("beneish", "integrity", "Manipulation risk flagged", RewardRiskKind.risk),
        ("sloan", "integrity", "Low accruals (higher quality)", RewardRiskKind.reward),
        ("sloan", "integrity", "High accruals (lower quality)", RewardRiskKind.risk),
    ],
)
def test_every_model_s_own_reward_and_risk_band_is_recognized(
    model, category, band, expected_kind
) -> None:
    verdict = [FakeVerdict(model, category, 2025, 1.0, band)]
    items = rewards_risks_for_overview(verdict, [])
    assert len(items) == 1
    assert items[0].kind is expected_kind


# --- Absence handling (AD-16): no value is not a headline finding ----------


def test_a_null_aggregate_value_never_produces_a_bullet_even_with_a_band_string() -> None:
    """A caveated-but-unresolved run can still carry a stale band_label from a
    prior computation path; the null value must win regardless (mirrors the
    same precedence VerdictGlyph's axisState already applies)."""
    verdict = [FakeVerdict("piotroski", "quality_health", 2025, None, "Strong")]
    assert rewards_risks_for_overview(verdict, []) == []


def test_no_band_label_never_produces_a_bullet() -> None:
    verdict = [FakeVerdict("sloan", "integrity", 2025, 0.01, None)]
    assert rewards_risks_for_overview(verdict, []) == []


# --- Data-quality issues: always a risk, never a reward ---------------------


def test_an_open_data_quality_issue_produces_one_singular_risk_bullet() -> None:
    dq = [FakeDataQuality(issue_type="ambiguous_selection", accession_number="0000000000-26-000001")]
    items = rewards_risks_for_overview([], dq)
    assert len(items) == 1
    assert items[0].kind is RewardRiskKind.risk
    assert items[0].section == "integrity-evidence"
    assert items[0].text == "1 open data-quality issue: ambiguous_selection."


def test_many_rows_of_the_same_issue_type_collapse_to_one_counted_bullet() -> None:
    """A filer can carry many genuinely distinct rows (different concept/
    fiscal-year pairs) sharing one issue_type — one bullet per row would
    flood a ten-second summary with near-identical text (found live on CP:
    9 real, distinct ambiguous_selection rows)."""
    dq = [FakeDataQuality(issue_type="ambiguous_selection") for _ in range(9)]
    items = rewards_risks_for_overview([], dq)
    assert len(items) == 1
    assert items[0].text == "9 open data-quality issues: ambiguous_selection."
    # No single accession is attached to a multi-row bullet — the section
    # link is the citation, not one arbitrarily-chosen row's accession.
    assert items[0].accession_number is None


def test_distinct_issue_types_get_their_own_bullet_each() -> None:
    dq = [
        FakeDataQuality(issue_type="ambiguous_selection"),
        FakeDataQuality(issue_type="ambiguous_selection"),
        FakeDataQuality(issue_type="some_future_issue_type"),
    ]
    items = rewards_risks_for_overview([], dq)
    texts = {i.text for i in items}
    assert texts == {
        "2 open data-quality issues: ambiguous_selection.",
        "1 open data-quality issue: some_future_issue_type.",
    }


# --- Honest empty state ------------------------------------------------------


def test_a_company_with_nothing_qualifying_returns_an_empty_list_not_padded_bullets() -> None:
    verdict = [
        FakeVerdict("piotroski", "quality_health", 2025, 5, "Middle"),
        FakeVerdict("altman", "quality_health", 2025, None, None),
    ]
    assert rewards_risks_for_overview(verdict, []) == []


# --- Attribution travels with every item ------------------------------------


def test_every_bullet_carries_the_spec_s_attribution_and_version() -> None:
    verdict = [FakeVerdict("altman", "quality_health", 2025, 4.0, "Safe")]
    dq = [FakeDataQuality(issue_type="ambiguous_selection")]
    items = rewards_risks_for_overview(verdict, dq)
    assert len(items) == 2
    for item in items:
        assert item.spec_version == "rewards_risks_v1"
        assert "ThesisTrace's own selection" in item.attribution


# --- Loader guards -----------------------------------------------------------


def test_loader_rejects_a_spec_that_is_not_a_presentation_rule(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "not_a_rule.yaml"
    bad.write_text("kind: model_formula\nspec_version: x\n")
    monkeypatch.setattr("rewards_risks.engine.SPEC_PATH", bad)
    load_rewards_risks_spec.cache_clear()
    try:
        with pytest.raises(RewardsRisksSpecError):
            load_rewards_risks_spec()
    finally:
        load_rewards_risks_spec.cache_clear()


def test_spec_file_declares_itself_a_presentation_rule() -> None:
    assert SPEC_PATH.exists()
    spec = load_rewards_risks_spec()
    assert spec["kind"] == "thesistrace_presentation_rule"


# --- The piotroski_v1 inputs lesson, applied here ---------------------------


def test_declared_inputs_cover_what_the_engine_actually_reads() -> None:
    """`inputs` in rewards_risks_v1.yaml is not documentation — the same class
    of bug that let piotroski_v1.yaml under-declare its inputs for months
    (found 2026-08-02) applies to any spec with a declared-inputs list.

    Deliberately coarse, like the model-spec version of this test: it greps
    engine.py's source for `v.<attr>` / `dq.<attr>` attribute reads rather
    than executing it, so it can over-report but never silently under-check.
    """
    source = ENGINE_PATH.read_text()
    verdict_attrs = set(re.findall(r"\bv\.([a-z_]+)\b", source))
    dq_attrs = set(re.findall(r"\bdq\.([a-z_]+)\b", source))

    declared = set(load_rewards_risks_spec()["inputs"])
    declared_verdict = {i.removeprefix("verdict.") for i in declared if i.startswith("verdict.")}
    declared_dq = {i.removeprefix("data_quality.") for i in declared if i.startswith("data_quality.")}

    assert verdict_attrs - declared_verdict == set(), (
        f"engine reads verdict.{sorted(verdict_attrs - declared_verdict)} "
        "which rewards_risks_v1.yaml does not declare"
    )
    assert dq_attrs - declared_dq == set(), (
        f"engine reads data_quality.{sorted(dq_attrs - declared_dq)} "
        "which rewards_risks_v1.yaml does not declare"
    )
