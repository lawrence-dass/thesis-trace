"""Beneish M-Score computation (FR-6).

All 8 indices computed individually across years t and t-1; any index whose
inputs are missing or hit a zero denominator is insufficient_data (AD-16). If any
index is insufficient, the aggregate M is not computable. Financial-sector firms
are excluded (AD-20, D6). All arithmetic via the shared decimal engine (AD-15).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models import Applicability, SignalStatus
from formulas.engine import FormulaSpec, InsufficientData, divide, round_ratio, to_decimal
from scoring.facts import FactLookup
from scoring.piotroski import SignalOutcome


@dataclass
class BeneishResult:
    components: list[SignalOutcome]
    m_score: float | None
    band: str | None
    applicability: Applicability
    # Why the caveat applies, when it does. Stored so the explanation layer never
    # has to guess a model-specific reason (Altman's is capital intensity, not this).
    caveat_reason: str | None = None


def _ratio(numerator, denominator, spec: FormulaSpec) -> Decimal:
    return divide(numerator, denominator, spec)


def compute_beneish(
    facts: FactLookup, fiscal_year: int, spec: FormulaSpec, *, is_financial_sector: bool
) -> BeneishResult:
    y, p = fiscal_year, fiscal_year - 1

    if is_financial_sector:
        components = [SignalOutcome(s, SignalStatus.insufficient_data) for s in spec.signal_keys]
        return BeneishResult(components, None, None, Applicability.excluded_out_of_scope)

    g = facts.get
    indices: dict[str, Decimal | None] = {}

    def compute(key: str, fn) -> None:
        try:
            indices[key] = round_ratio(fn(), spec)
        except InsufficientData:
            indices[key] = None

    # DSRI = (AR_t/Sales_t) / (AR_{t-1}/Sales_{t-1})
    compute("dsri", lambda: _ratio(_ratio(g("receivables", y), g("revenue", y), spec),
                                   _ratio(g("receivables", p), g("revenue", p), spec), spec))
    # GMI = GM_{t-1} / GM_t, GM = (Sales - COGS)/Sales
    def gmi():
        gm_y = _ratio(to_decimal(g("revenue", y)) - to_decimal(g("cogs", y)), g("revenue", y), spec)
        gm_p = _ratio(to_decimal(g("revenue", p)) - to_decimal(g("cogs", p)), g("revenue", p), spec)
        return _ratio(gm_p, gm_y, spec)
    compute("gmi", gmi)
    # AQI = AQ_t / AQ_{t-1}, AQ = 1 - (CA + PPE)/TA
    def aq(year):
        return Decimal(1) - _ratio(to_decimal(g("current_assets", year)) + to_decimal(g("ppe_net", year)),
                                   g("total_assets", year), spec)
    compute("aqi", lambda: _ratio(aq(y), aq(p), spec))
    # SGI = Sales_t / Sales_{t-1}
    compute("sgi", lambda: _ratio(g("revenue", y), g("revenue", p), spec))
    # DEPI = DepRate_{t-1} / DepRate_t, DepRate = Dep/(Dep + PPE)
    def deprate(year):
        return _ratio(g("depreciation", year), to_decimal(g("depreciation", year)) + to_decimal(g("ppe_net", year)), spec)
    compute("depi", lambda: _ratio(deprate(p), deprate(y), spec))
    # SGAI = (SGA_t/Sales_t) / (SGA_{t-1}/Sales_{t-1})
    compute("sgai", lambda: _ratio(_ratio(g("sga", y), g("revenue", y), spec),
                                   _ratio(g("sga", p), g("revenue", p), spec), spec))
    # TATA = (NI_t - CFO_t) / TA_t
    compute("tata", lambda: _ratio(to_decimal(g("net_income", y)) - to_decimal(g("cash_from_operations", y)),
                                   g("total_assets", y), spec))
    # LVGI = Lev_t / Lev_{t-1}, Lev = (current liabilities + LTD)/TA
    def lev(year):
        return _ratio(to_decimal(g("current_liabilities", year)) + to_decimal(g("long_term_debt", year)),
                      g("total_assets", year), spec)
    compute("lvgi", lambda: _ratio(lev(y), lev(p), spec))

    components = [
        SignalOutcome(k, SignalStatus.insufficient_data if v is None else SignalStatus.pass_, value=(float(v) if v is not None else None))
        for k, v in ((k, indices[k]) for k in spec.signal_keys)
    ]

    if any(v is None for v in indices.values()):
        return BeneishResult(components, None, None, Applicability.computed)

    m = Decimal(str(spec.raw["constant"]))
    for key, coeff in spec.raw["coefficients"].items():
        m += Decimal(str(coeff)) * indices[key]
    m = round_ratio(m, spec)

    threshold = Decimal(str(spec.raw["threshold"]["manipulation_above"]))
    band = "Manipulation risk flagged" if m > threshold else "No manipulation flag"

    # ThesisTrace presentation guards (see the spec). Neither alters the score —
    # both only annotate, so nothing is invented. Reasons accumulate: a run can be
    # both out of calibration and built on an unvalidated margin, and one must not
    # silently replace the other.
    reasons: list[str] = []

    # Out-of-calibration disclosure (the `calibration` block).
    calib = spec.raw.get("calibration") or {}
    bound = calib.get("index_abs_max")
    if bound is not None and any(abs(v) > Decimal(str(bound)) for v in indices.values()):
        reasons.append(calib["caveat_reason"].strip())

    # Unvalidated gross margin (the `gross_margin_validation` block). GMI's
    # (Sales - COGS) / Sales is only a margin when COGS matches the revenue base.
    gross_margin = spec.raw.get("gross_margin_validation") or {}
    if gross_margin.get("require_gross_profit_concept") and not _gross_profit_validated(facts):
        reasons.append(gross_margin["caveat_reason"].strip())

    if reasons:
        return BeneishResult(
            components, float(m), band, Applicability.computed_with_caveat,
            caveat_reason=" ".join(reasons)[:512],
        )
    return BeneishResult(components, float(m), band, Applicability.computed)


def _gross_profit_validated(facts) -> bool:
    """True when this filer has a gross_profit canonical fact for ANY year — filed
    directly, or validly derived (which is itself source-constrained, see
    derivations_v2.yaml).

    Filer-level on purpose: a company that reports a gross profit line anywhere has
    demonstrated that revenue - cogs is meaningful for its income statement, so it
    stays validated in years the tag happens to be absent. One that never reports it
    is telling you the subtraction does not describe its business.
    """
    return any(facts.get("gross_profit", year) is not None for year in facts.fiscal_years())
