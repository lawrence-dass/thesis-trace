"""Rewards and risks: the strongest already-computed positives and negatives
(Story 10.3, D12).

A ThesisTrace-authored PRESENTATION rule, not an academic model. It SELECTS
which of the four models' own published bands is reward- or risk-worthy, and
selects open (`needs_review`) data-quality issues as risks — it never computes
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
from string import Formatter

import yaml

from formulas.engine import load_spec as load_formula_spec

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
OPEN_DATA_QUALITY_STATUS = "needs_review"
SUPPORTED_MODELS = ("piotroski", "altman", "beneish", "sloan")


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
    #: Grouped data-quality bullets intentionally have no single accession;
    #: the section link is their citation. Model-band bullets likewise point to
    #: the section containing the cited score and its input provenance.
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
    try:
        data = yaml.safe_load(SPEC_PATH.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise RewardsRisksSpecError(f"Could not load rewards/risks spec: {exc}") from exc
    if not isinstance(data, dict):
        raise RewardsRisksSpecError("Rewards/risks spec must be a YAML mapping")
    if data.get("kind") != "thesistrace_presentation_rule":
        raise RewardsRisksSpecError(
            f"{SPEC_PATH.name} is not a thesistrace_presentation_rule; refusing to load it "
            "as one. Academic model specs must not be applied as presentation rules."
        )
    for required in (
        "inputs",
        "reward_bands",
        "risk_bands",
        "model_label",
        "band_reward_template",
        "band_risk_template",
        "data_quality_risk_template_singular",
        "data_quality_risk_template_plural",
        "rationale",
        "attribution",
        "spec_version",
    ):
        if required not in data:
            raise RewardsRisksSpecError(f"Rewards/risks spec missing '{required}'")

    for field in ("reward_bands", "risk_bands", "model_label"):
        if not isinstance(data[field], dict):
            raise RewardsRisksSpecError(f"Rewards/risks spec field '{field}' must be a mapping")
    if not isinstance(data["inputs"], list) or not all(
        isinstance(item, str) and item.strip() for item in data["inputs"]
    ):
        raise RewardsRisksSpecError("Rewards/risks spec field 'inputs' must be a list of text paths")
    for field in (
        "band_reward_template",
        "band_risk_template",
        "data_quality_risk_template_singular",
        "data_quality_risk_template_plural",
        "rationale",
        "attribution",
        "spec_version",
    ):
        if not isinstance(data[field], str) or not data[field].strip():
            raise RewardsRisksSpecError(f"Rewards/risks spec field '{field}' must be non-empty text")

    required_template_fields = {
        "band_reward_template": {"model_label", "band_label", "fiscal_year", "caveat_suffix"},
        "band_risk_template": {"model_label", "band_label", "fiscal_year", "caveat_suffix"},
        "data_quality_risk_template_singular": {"issue_type"},
        "data_quality_risk_template_plural": {"issue_type", "count"},
    }
    for field, expected in required_template_fields.items():
        try:
            names = {name for _, name, _, _ in Formatter().parse(data[field]) if name is not None}
        except ValueError as exc:
            raise RewardsRisksSpecError(f"Rewards/risks spec template '{field}' is invalid") from exc
        if not expected.issubset(names):
            raise RewardsRisksSpecError(
                f"Rewards/risks spec template '{field}' must expose {sorted(expected)}"
            )

    # The reward/risk rule deliberately quotes the academic models' labels, but
    # the model specs remain authoritative. Fail at load time if a future model
    # revision relabels a band instead of silently disabling a headline.
    for model in SUPPORTED_MODELS:
        model_spec = load_formula_spec(f"{model}_v1")
        classes = model_spec.raw.get("bands", {}).get("classes", [])
        labels = {band.get("label") for band in classes if isinstance(band, dict)}
        for field in ("reward_bands", "risk_bands"):
            configured = data[field].get(model)
            if configured not in labels:
                raise RewardsRisksSpecError(
                    f"{field}.{model}={configured!r} is not a published band in {model}_v1"
                )
    return data


def _attribution() -> str:
    spec = load_rewards_risks_spec()
    return f"{spec['rationale'].strip()} {spec['attribution'].strip()}"


def _spec_version() -> str:
    return load_rewards_risks_spec()["spec_version"]


def rewards_risks_for_overview(verdict, data_quality) -> list[RewardRiskItem]:
    """Rewards and risks over an already-built Verdict and data-quality list.

    `verdict` items need `.model`, `.category`, `.fiscal_year`,
    `.aggregate_value`, `.band_label`, `.applicability`. `data_quality` items
    need `.issue_type`, `.status`. Duck-typed, like
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
        if (
            v.aggregate_value is None
            or not v.band_label
            or v.applicability not in {"computed", "computed_with_caveat"}
        ):
            # No value to plot is not a headline positive or negative — the
            # glyph and the Verdict grid already say "Insufficient data" or
            # "Unavailable" everywhere this belongs; repeating it here would
            # pad the list or promote an unsupported score.
            continue
        label = model_label.get(v.model, v.model)
        section = SECTION_FOR_CATEGORY.get(v.category)
        if section is None:
            # A new/corrupt category must not send the reader to a substantive
            # section that does not contain this model's evidence.
            continue
        caveat_suffix = " (with a caveat)" if v.applicability == "computed_with_caveat" else ""
        if v.band_label == reward_bands.get(v.model):
            items.append(
                RewardRiskItem(
                    kind=RewardRiskKind.reward,
                    text=spec["band_reward_template"].format(
                        model_label=label,
                        band_label=v.band_label,
                        fiscal_year=v.fiscal_year,
                        caveat_suffix=caveat_suffix,
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
                        model_label=label,
                        band_label=v.band_label,
                        fiscal_year=v.fiscal_year,
                        caveat_suffix=caveat_suffix,
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
        if dq.status != OPEN_DATA_QUALITY_STATUS:
            continue
        counts[dq.issue_type] = counts.get(dq.issue_type, 0) + 1
    for issue_type in sorted(counts):
        count = counts[issue_type]
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
