"""Methodology metadata per score, read from the versioned formula spec (FR-11, AD-5).

Also publishes the derivations feeding this model's inputs. D8 consequence 3 requires
that a judgment ThesisTrace made — reconstructing IFRS `ebit`, where two defensible
formulas give different numbers — be visible on the methodology page rather than
buried. Everything here is read from the versioned specs, so the published rationale
cannot drift from the rule actually applied.
"""

from __future__ import annotations

from canonicalization.mappings import DERIVATION_RULES
from formulas.engine import load_spec

MODEL_TO_SPEC = {
    "piotroski": "piotroski_v1",
    "altman": "altman_v1",
    "beneish": "beneish_v1",
    "sloan": "sloan_v1",
}


def _derivations_for(inputs: list[str]) -> list[dict]:
    """The derivation rules that can produce this model's inputs.

    Scoped to the model's own inputs so each page explains the judgments that
    actually affect the score being read, rather than a global list a user has to
    filter mentally.
    """
    return [
        {
            "concept": rule.canonical_concept,
            "rule": rule.rule,
            "kind": rule.kind,
            "expression": rule.expression(),
            # The PUBLIC rationale, never the maintainer note — that one cites decision
            # records and file paths, which mean nothing to a reader of this page.
            "rationale": " ".join((rule.rationale or "").split()),
            # Named plainly: a source constraint is the difference between a figure
            # that means what it says and one that merely computes.
            "only_when": [
                f"{operand} comes from {' or '.join(sources)}"
                for operand, sources in rule.requires_source
            ],
        }
        for rule in DERIVATION_RULES
        if rule.canonical_concept in inputs
    ]


def get_methodology(model: str) -> dict | None:
    version = MODEL_TO_SPEC.get(model)
    if version is None:
        return None
    spec = load_spec(version)
    raw = spec.raw
    inputs = raw.get("inputs", [])
    return {
        "model": spec.model,
        "formula_version": spec.formula_version,
        "description": raw.get("description", "").strip(),
        "inputs": inputs,
        "signals": raw.get("signals", []),
        "rounding": raw.get("rounding", {}),
        "bands": raw.get("bands", {}),
        "threshold": raw.get("threshold"),
        "source": raw.get("bands", {}).get("citation"),
        "derivations": _derivations_for(inputs),
    }
