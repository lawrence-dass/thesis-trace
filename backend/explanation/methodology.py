"""Methodology metadata per score, read from the versioned formula spec (FR-11, AD-5)."""

from __future__ import annotations

from formulas.engine import load_spec

MODEL_TO_SPEC = {
    "piotroski": "piotroski_v1",
    "altman": "altman_v1",
    "beneish": "beneish_v1",
    "sloan": "sloan_v1",
}


def get_methodology(model: str) -> dict | None:
    version = MODEL_TO_SPEC.get(model)
    if version is None:
        return None
    spec = load_spec(version)
    raw = spec.raw
    return {
        "model": spec.model,
        "formula_version": spec.formula_version,
        "description": raw.get("description", "").strip(),
        "inputs": raw.get("inputs", []),
        "signals": raw.get("signals", []),
        "rounding": raw.get("rounding", {}),
        "bands": raw.get("bands", {}),
        "threshold": raw.get("threshold"),
        "source": raw.get("bands", {}).get("citation"),
    }
