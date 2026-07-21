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
    return BeneishResult(components, float(m), band, Applicability.computed)
