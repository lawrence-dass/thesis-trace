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


def _reverse_dcf_methodology() -> dict:
    """Publish the authored reverse-DCF rule through the same public route.

    The reverse DCF is intentionally not an academic formula spec, so it cannot be
    passed through ``formulas.engine.load_spec``. It still has to publish its
    assumptions and default origin; otherwise the API would expose a number whose
    most consequential input is invisible on ``/methodology``.
    """
    from valuation.reverse_dcf import load_spec

    raw = load_spec()

    # The reverse-DCF file deliberately keeps maintainer notes next to public
    # rationales. Do not pass the raw blocks through: notes contain Story/AD and
    # verification references that are useful to maintainers but not to readers.
    assumptions = {
        name: {key: value for key, value in block.items() if key != "note"}
        for name, block in raw.get("assumptions", {}).items()
    }
    enterprise_value = {
        key: value for key, value in raw.get("enterprise_value", {}).items() if key != "note"
    }
    free_cash_flow = {
        key: value
        for key, value in raw.get("free_cash_flow", {}).items()
        if key not in {"note", "known_limitation"}
    }
    solver = {
        key: value for key, value in raw.get("solver", {}).items() if key != "note"
    }
    output = {key: value for key, value in raw.get("output", {}).items() if key != "note"}
    caveats = [
        {key: value for key, value in caveat.items() if key != "note"}
        for caveat in raw.get("caveats", [])
    ]
    return {
        "model": raw["rule"],
        "formula_version": raw["spec_version"],
        "description": raw.get("description", "").strip(),
        "inputs": list(
            dict.fromkeys(
                raw.get("enterprise_value", {}).get("operands", [])
                + raw.get("free_cash_flow", {}).get("operands", [])
                + ["shares_outstanding", "market_price", "fx_rate"]
            )
        ),
        "signals": [],
        "rounding": {},
        "bands": {},
        "threshold": None,
        "source": None,
        "derivations": [],
        "assumptions": assumptions,
        "solver": solver,
        "enterprise_value": enterprise_value,
        "free_cash_flow": free_cash_flow,
        "caveats": caveats,
        "output": output,
        "authorship": raw.get("authorship", {}),
        "attribution": raw.get("attribution", "").strip(),
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
    if model == "reverse_dcf":
        return _reverse_dcf_methodology()
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
