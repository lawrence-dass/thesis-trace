"""What the methodology page publishes (FR-11, AD-8, D8 consequence 3).

The page renders exactly what the read API returns, and the API reads only the
versioned specs — so a published rationale cannot drift from the rule actually
applied. These tests guard that chain.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from canonicalization.mappings import DERIVATION_RULES
from explanation.methodology import MODEL_TO_SPEC, get_methodology
from formulas.engine import load_spec

SCORING_DIR = Path(__file__).resolve().parents[1] / "scoring"


@pytest.mark.parametrize("model", sorted(MODEL_TO_SPEC))
def test_declared_inputs_match_what_the_model_actually_reads(model: str) -> None:
    """`inputs` is not documentation — it is load-bearing.

    scoring/runner.py checks it to decide whether a run consumed an input that is not
    comparable across filers, and the methodology page publishes it. An input the code
    reads but the spec omits is invisible to both: the comparability caveat can never
    fire on it, and the page under-reports what the score depends on.

    Found 2026-08-02 by building the page — piotroski_v1 declared 6 inputs while
    scoring/piotroski.py read 9 (gross_profit, long_term_debt, revenue were missing).

    Deliberately coarse: it greps the module source rather than executing it, so it
    can over-report if a concept name ever appears in a non-lookup context. Erring
    toward over-declaring is the safe direction — it widens the comparability check.
    """
    source = (SCORING_DIR / f"{model}.py").read_text()
    used = set(re.findall(r'facts\.get\("([a-z_]+)"', source)) | set(
        re.findall(r'g\("([a-z_]+)"', source)
    )
    declared = set(load_spec(MODEL_TO_SPEC[model]).raw.get("inputs", []))

    assert used - declared == set(), (
        f"{model} reads canonical concepts its spec does not declare: {sorted(used - declared)}"
    )


def test_altman_publishes_the_ifrs_ebit_decision() -> None:
    """D8 consequence 3: the ebit choice must be visible on the methodology page, not
    buried in a mapping row. Altman is where it belongs — X3 is EBIT / total assets."""
    derivations = {d["concept"]: d for d in get_methodology("altman")["derivations"]}

    ebit = derivations["ebit"]
    assert ebit["kind"] == "decision", "the ebit reconstruction is a judgment, not arithmetic"
    assert ebit["expression"] == "profit_before_tax + interest_expense"
    # The rationale must name the alternative that was rejected — a decision presented
    # without its alternatives reads as the only option, which is the opposite of
    # letting a user disagree with it.
    assert "alternative approach" in ebit["rationale"].lower()
    # ...and must be readable by someone who has never seen this repository. The
    # maintainer-facing note cites decision records and filers; publishing it verbatim
    # would leak internal shorthand onto a public page.
    for internal in ("D8", "consequence 3", "yaml", "Suncor", "Cameco", "DECISION,"):
        assert internal not in ebit["rationale"], f"internal shorthand published: {internal}"


def test_derivations_are_scoped_to_each_model_s_own_inputs() -> None:
    """Each page explains the judgments affecting the score being read, rather than a
    global list the reader has to filter mentally."""
    for model in MODEL_TO_SPEC:
        meta = get_methodology(model)
        concepts = {d["concept"] for d in meta["derivations"]}
        assert concepts <= set(meta["inputs"]), model

    # Sloan consumes only directly-filed concepts, so its page shows no derivations —
    # the negative case that keeps the section meaningful where it does appear.
    assert get_methodology("sloan")["derivations"] == []


def test_every_published_derivation_carries_a_rationale_and_a_kind() -> None:
    for model in MODEL_TO_SPEC:
        for derivation in get_methodology(model)["derivations"]:
            assert derivation["kind"] in {"identity", "decision"}, derivation
            assert derivation["rationale"], f"{derivation['rule']} would publish an empty rationale"
            assert "D8" not in derivation["rationale"], derivation["rule"]
            assert derivation["expression"], derivation


def test_source_constraints_are_published_in_plain_language() -> None:
    """A constrained derivation is only correct because of its constraint, so hiding it
    would publish a formula that looks more general than it is."""
    gross_profit = next(
        d
        for d in get_methodology("beneish")["derivations"]
        if d["concept"] == "gross_profit"
    )
    assert gross_profit["only_when"] == ["cogs comes from CostOfSales"]


def test_loader_rejects_a_derivation_with_no_rationale_or_kind() -> None:
    """Both are published, so a rule missing either cannot ship."""
    from canonicalization.mappings.engine import DerivationRule

    assert all(isinstance(d, DerivationRule) for d in DERIVATION_RULES)
    assert all(d.kind and d.note and d.rationale for d in DERIVATION_RULES)
