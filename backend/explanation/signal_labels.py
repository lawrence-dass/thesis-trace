"""Plain-language names for every model's sub-signals (Ops 6b).

Used by the explanation template so a sentence reads "Signals met: Working
Capital, EBIT" rather than "x1_working_capital, x3_ebit". The frontend keeps an
identical copy as `SIGNAL_LABEL` in `frontend/app/company/[ticker]/page.tsx`
(Render deploys only `backend/`, so one file cannot serve both).
`test_signal_labels.py` fails if the two drift, or if any signal in a formula
spec has no label here.
"""

from __future__ import annotations

SIGNAL_LABEL: dict[str, str] = {
    # Piotroski: each is a condition the filer met or did not.
    "roa_positive": "Positive Return on Assets",
    "cfo_positive": "Positive Operating Cash Flow",
    "roa_increasing": "Rising Return on Assets",
    "accruals": "Cash Flow Above Earnings",
    "leverage_decreasing": "Falling Leverage",
    "current_ratio_increasing": "Rising Current Ratio",
    "shares_not_diluted": "No Share Dilution",
    "gross_margin_increasing": "Rising Gross Margin",
    "asset_turnover_increasing": "Rising Asset Turnover",
    # Beneish
    "dsri": "Days Sales in Receivables",
    "gmi": "Gross Margin",
    "aqi": "Asset Quality",
    "sgi": "Sales Growth",
    "depi": "Depreciation Rate",
    "sgai": "SG&A Ratio",
    "tata": "Total Accruals",
    "lvgi": "Leverage",
    # Altman
    "x1_working_capital": "Working Capital",
    "x2_retained_earnings": "Retained Earnings",
    "x3_ebit": "EBIT",
    "x4_market_value_equity": "Market Value of Equity",
    "x5_sales": "Sales Turnover",
    # Sloan
    "accruals_ratio": "Accruals",
}


def signal_label(key: str) -> str:
    return SIGNAL_LABEL.get(key, key)
