"""Rewards and risks: the strongest already-computed positives and negatives
(Story 10.3, D12).

A ThesisTrace-authored PRESENTATION rule, not an academic model. It SELECTS
which of the four models' own published bands is reward- or risk-worthy, and
selects open (non-dismissed) data-quality issues as risks — it never computes
a new figure, never reclassifies a band, and never uses free text or an LLM.
Every selection and every sentence shape comes from
`formulas/specs/rewards_risks_v1.yaml`, where it is labelled as ours.

Reads objects the caller has already fetched (get_company_overview's
`verdict` and `data_quality` lists) — no new query, same shape as
`trajectory.engine.trajectories_for_scores`.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "formulas" / "specs" / "rewards_risks_v1.yaml"

# Category (already on every VerdictItem, FR-5/FR-8) -> report section anchor
# (Story 10.1). Not spec data: this is plumbing that maps an existing
# classification onto an existing page anchor, not a ThesisTrace judgment
# about a company's numbers.
SECTION_FOR_CATEGORY = {
    "quality_health": "financial-health",
    "integrity": "integrity-evidence",
}
# Data-quality issues are homed under Integrity & Evidence regardless of
# which model's inputs raised them (Story 10.5's own placement decision).
DATA_QUALITY_SECTION = "integrity-evidence"


class RewardRiskKind(str, enum.Enum):
    reward = "reward"
    risk = "risk"


@dataclass(frozen=True)
class RewardRiskItem:
    kind: RewardRiskKind
    text: str
    section: str
    #: Populated for a model-band bullet; None for a data-quality bullet.
    model: str | None
    fiscal_year: int | None
    #: Populated for a data-quality bullet; None for a model-band bullet.
    accession_number: str | None
    attribution: str
    spec_version: str


class RewardsRisksSpecError(Exception):
    """The spec is missing, malformed, or is not a presentation rule."""


@lru_cache(maxsize=1)
def load_rewards_risks_spec() -> dict:
    """Load the versioned rule.

    Rejects anything that is not explicitly a ThesisTrace presentation rule,
    so this loader can never be pointed at one of the four academic model
    specs and quietly apply their bands as if this rule invented them.
    """
    if not SPEC_PATH.exists():
        raise RewardsRisksSpecError(f"Rewards/risks spec not found: {SPEC_PATH}")
    data = yaml.safe_load(SPEC_PATH.read_text())
    if data.get("kind") != "thesistrace_presentation_rule":
        raise RewardsRisksSpecError(
            f"{SPEC_PATH.name} is not a thesistrace_presentation_rule; refusing to load it "
            "as one. Academic model specs must not be applied as presentation rules."
        )
    for required in (
        "reward_bands",
        "risk_bands",
        "model_label",
        "band_reward_template",
        "band_risk_template",
        "data_quality_risk_template_singular",
        "data_quality_risk_template_plural",
        "attribution",
        "spec_version",
    ):
        if required not in data:
            raise RewardsRisksSpecError(f"Rewards/risks spec missing '{required}'")
    return data


def _attribution() -> str:
    return load_rewards_risks_spec()["attribution"].strip()


def _spec_version() -> str:
    return load_rewards_risks_spec()["spec_version"]


def rewards_risks_for_overview(verdict, data_quality) -> list[RewardRiskItem]:
    """Rewards and risks over an already-built Verdict and data-quality list.

    `verdict` items need `.model`, `.category`, `.fiscal_year`,
    `.aggregate_value`, `.band_label`. `data_quality` items need
    `.issue_type`, `.accession_number`. Duck-typed, like
    `trajectories_for_scores`, so this stays decoupled from the API schema
    layer — the read path is one pass over rows the caller already fetched
    (AD-1), never a second query.
    """
    spec = load_rewards_risks_spec()
    reward_bands = spec["reward_bands"]
    risk_bands = spec["risk_bands"]
    model_label = spec["model_label"]
    attribution = _attribution()
    spec_version = _spec_version()

    items: list[RewardRiskItem] = []

    for v in verdict:
        if v.aggregate_value is None or not v.band_label:
            # No value to plot is not a headline positive or negative — the
            # glyph and the Verdict grid already say "Insufficient data"
            # everywhere this belongs; repeating it here would pad the list
            # rather than surface a real signal.
            continue
        label = model_label.get(v.model, v.model)
        section = SECTION_FOR_CATEGORY.get(v.category, "financial-health")
        if v.band_label == reward_bands.get(v.model):
            items.append(
                RewardRiskItem(
                    kind=RewardRiskKind.reward,
                    text=spec["band_reward_template"].format(
                        model_label=label, band_label=v.band_label, fiscal_year=v.fiscal_year
                    ),
                    section=section,
                    model=v.model,
                    fiscal_year=v.fiscal_year,
                    accession_number=None,
                    attribution=attribution,
                    spec_version=spec_version,
                )
            )
        elif v.band_label == risk_bands.get(v.model):
            items.append(
                RewardRiskItem(
                    kind=RewardRiskKind.risk,
                    text=spec["band_risk_template"].format(
                        model_label=label, band_label=v.band_label, fiscal_year=v.fiscal_year
                    ),
                    section=section,
                    model=v.model,
                    fiscal_year=v.fiscal_year,
                    accession_number=None,
                    attribution=attribution,
                    spec_version=spec_version,
                )
            )

    # ONE bullet per DISTINCT issue_type, counting every open row of that
    # type — a filer can carry many genuinely different rows (different
    # concept/fiscal-year pairs) sharing one issue_type, and a bullet each
    # would flood a ten-second summary with near-identical text. No single
    # accession_number is attached to a multi-row bullet — the section link
    # is the citation; Integrity & Evidence lists every row individually.
    counts: dict[str, int] = {}
    for dq in data_quality:
        counts[dq.issue_type] = counts.get(dq.issue_type, 0) + 1
    for issue_type, count in counts.items():
        template = (
            spec["data_quality_risk_template_singular"]
            if count == 1
            else spec["data_quality_risk_template_plural"]
        )
        items.append(
            RewardRiskItem(
                kind=RewardRiskKind.risk,
                text=template.format(issue_type=issue_type, count=count),
                section=DATA_QUALITY_SECTION,
                model=None,
                fiscal_year=None,
                accession_number=None,
                attribution=attribution,
                spec_version=spec_version,
            )
        )

    return items
