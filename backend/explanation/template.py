"""Deterministic, cited explanation templates (FR-12, AD-7).

Explanation text is generated directly from already-computed scores/facts — no LLM
in the loop. Every sentence is grounded; provenance citations are attached from the
signals' provenance. An ungroundable statement is simply not produced (AD-19).
"""

from __future__ import annotations

from dataclasses import dataclass

from api.schemas import CompanyOverviewOut, LensScoreOut

MODEL_TITLE = {
    "piotroski": "Piotroski F-Score",
    "altman": "Altman Z-Score",
    "beneish": "Beneish M-Score",
    "sloan": "Sloan accruals ratio",
}


@dataclass
class LensExplanation:
    model: str
    #: One explanation per (model, fiscal_year) — a filer with N scored years
    #: produces N explanations per model, not one. Without this field the API
    #: response is ambiguous whenever more than one year is rendered for a
    #: model, which every report page does (FR-10's expandable card list is
    #: per fiscal year, not just the latest).
    fiscal_year: int
    text: str
    citations: list[str]  # accession numbers cited


def _lens_sentences(lens: LensScoreOut) -> tuple[str, list[str]]:
    title = MODEL_TITLE.get(lens.model, lens.model)
    citations: list[str] = []

    if lens.applicability == "excluded_out_of_scope":
        return (f"{title} is not applicable to this company (out of the model's valid sector scope).", citations)

    parts: list[str] = []
    if lens.aggregate_value is not None:
        band = f" — classified {lens.band_label}" if lens.band_label else ""
        parts.append(f"{title} for FY{lens.fiscal_year} is {lens.aggregate_value}{band}.")
    else:
        parts.append(f"{title} for FY{lens.fiscal_year} could not be fully computed (some inputs were insufficient).")

    passed = [s.signal_key for s in lens.signals if s.status == "pass"]
    failed = [s.signal_key for s in lens.signals if s.status == "fail"]
    insufficient = [s.signal_key for s in lens.signals if s.status == "insufficient_data"]
    if passed:
        parts.append(f"Signals met: {', '.join(passed)}.")
    if failed:
        parts.append(f"Signals not met: {', '.join(failed)}.")
    if insufficient:
        parts.append(f"Insufficient data for: {', '.join(insufficient)}.")

    for s in lens.signals:
        for p in s.provenance:
            if p.accession_number not in citations:
                citations.append(p.accession_number)

    if lens.applicability == "computed_with_caveat":
        # Use the reason recorded on the run. Falling back to the capital-intensity
        # wording only for runs written before caveat_reason existed — asserting it
        # unconditionally would attach Altman's reasoning to Beneish's
        # out-of-calibration caveat, which is a different thing entirely.
        reason = (lens.caveat_reason or "").strip() or (
            "this is a capital-intensive company, for which the model runs structurally low"
        )
        parts.append(f"Interpret with caveat: {reason.rstrip('.')}.")

    return (" ".join(parts), citations)


def build_explanations(overview: CompanyOverviewOut) -> list[LensExplanation]:
    out: list[LensExplanation] = []
    for lens in overview.scores:
        text, citations = _lens_sentences(lens)
        out.append(
            LensExplanation(model=lens.model, fiscal_year=lens.fiscal_year, text=text, citations=citations)
        )
    return out
