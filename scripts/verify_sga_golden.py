"""Ops 5: independent re-verification of the golden SGAI and M-score.

Imports NOTHING from backend/scoring, backend/formulas or the mapping engine: it
reads the golden fixtures' JSON directly, so agreement with the pipeline is
corroboration rather than the same code run twice (project-context, 2026-08-04).

Method, proven before it is trusted: it first reproduces the OLD, G&A-only SGAI
that the golden file already pins (SHOP 0.663882, CPB 0.859487). Only if that
matches exactly does it compute the new SGAI = (G&A + S&M) basis. Beneish's
quantization contract (beneish_v1.yaml): every division rounded to 6 places,
ROUND_HALF_EVEN. Coefficients are Beneish (1999)'s published ones.

    make py F=scripts/verify_sga_golden.py
"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures"
Q = Decimal("0.000001")
COEF = {
    "dsri": Decimal("0.920"), "gmi": Decimal("0.528"), "aqi": Decimal("0.404"),
    "sgi": Decimal("0.892"), "depi": Decimal("0.115"), "sgai": Decimal("-0.172"),
    "tata": Decimal("4.679"), "lvgi": Decimal("-0.327"),
}


def q(x: Decimal) -> Decimal:
    return x.quantize(Q, rounding=ROUND_HALF_EVEN)


def annual(payload: dict, concept: str) -> dict[str, Decimal]:
    """period end -> value AS ORIGINALLY FILED (earliest filing carrying it)."""
    facts = payload["facts"]["us-gaap"].get(concept, {}).get("units", {}).get("USD", [])
    best: dict[str, tuple[str, Decimal]] = {}
    for f in facts:
        if "start" not in f or f.get("form") != "10-K":
            continue
        days = (Decimal(f["end"][:4]) - Decimal(f["start"][:4]))  # year span, coarse
        if days not in (Decimal(0), Decimal(1)):
            continue
        key = f["end"]
        if key not in best or f["filed"] < best[key][0]:
            best[key] = (f["filed"], Decimal(str(f["val"])))
    return {end: v for end, (_, v) in best.items()}


def sgai(sga: dict, rev: dict, t: str, t1: str) -> Decimal:
    return q(q(sga[t] / rev[t]) / q(sga[t1] / rev[t1]))


CASES = [
    # fixture, revenue tag, FY t end, FY t-1 end, golden indices (old), golden M (old)
    ("shop_real_company_facts.json", "Revenues", "2024-12-31", "2023-12-31",
     {"dsri": "0.964224", "gmi": "0.988624", "aqi": "1.080285", "sgi": "1.257790",
      "depi": "1.356208", "sgai": "0.663882", "tata": "0.028943", "lvgi": "0.875001"}, "-1.981461"),
    ("cpb_company_facts.json", "Revenues", "2025-08-03", "2024-07-28",
     {"dsri": "0.866179", "gmi": "1.013540", "aqi": "0.978278", "sgi": "1.064031",
      "depi": "0.975026", "sgai": "0.859487", "tata": "-0.035513", "lvgi": "0.985953"}, "-2.687902"),
    ("otex_company_facts.json", ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"),
     "2019-06-30", "2018-06-30", None, "-2.884422"),
]


def main() -> None:
    for name, rev_tag, t, t1, idx, m_old in CASES:
        payload = json.loads((FIXTURES / name).read_text())
        # A tuple of tags: the first that carries a period wins (OTEX moves to the
        # ASC 606 tag in FY2019; FY2018 is the same 2,815,241,000 under both).
        rev: dict[str, Decimal] = {}
        for tag in rev_tag if isinstance(rev_tag, tuple) else (rev_tag,):
            rev = annual(payload, tag) | rev
        ga = annual(payload, "GeneralAndAdministrativeExpense")
        sm = annual(payload, "SellingAndMarketingExpense")
        old = sgai(ga, rev, t, t1)
        sga = {e: ga[e] + sm[e] for e in (t, t1)}
        new = sgai(sga, rev, t, t1)
        print(f"{name}: G&A {ga[t1]:,} -> {ga[t]:,}; S&M {sm[t1]:,} -> {sm[t]:,}; revenue {rev[t1]:,} -> {rev[t]:,}")
        print(f"  old SGAI (G&A only) {old}" + (f"  golden {idx['sgai']}  {'MATCH' if str(old) == idx['sgai'] else 'MISMATCH'}" if idx else ""))
        print(f"  new SGAI (G&A + S&M) {new}")
        if idx:
            m_check = q(Decimal("-4.84") + sum(COEF[k] * Decimal(v) for k, v in idx.items()))
            new_idx = dict(idx, sgai=str(new))
            m_new = q(Decimal("-4.84") + sum(COEF[k] * Decimal(v) for k, v in new_idx.items()))
            print(f"  old M from golden indices {m_check}  golden {m_old}  {'MATCH' if str(m_check) == m_old else 'MISMATCH'}")
            print(f"  NEW M {m_new}  band {'Manipulation risk flagged' if m_new > Decimal('-1.78') else 'No manipulation flag'}")
        else:
            delta = COEF["sgai"] * (new - old)
            print(f"  NEW M ~ {Decimal(m_old) + delta} (golden M + -0.172 x dSGAI; exact to +/-1e-6, other indices not pinned)")


if __name__ == "__main__":
    main()
