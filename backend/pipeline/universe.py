"""Company Universe (foundational decisions D6, D8).

Every CIK confirmed live against data.sec.gov before being hardcoded here.

Two reporting regimes are represented (D8, Canada-first):
  * 10-K / us-gaap  — the original four (confirmed 2026-07-21)
  * 40-F / ifrs-full — Canadian MJDS filers reporting under IFRS
                       (confirmed 2026-07-29)

Regime is NOT stored on the entry: it's discovered from the filer's own payload,
so a filer that switches regimes is handled without an edit here. Supported
regimes are declared in canonicalization.taxonomies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniverseEntry:
    ticker: str
    name: str
    cik: str | None  # zero-padded; None until confirmed against EDGAR
    is_financial_sector: bool = False
    capital_intensive: bool = False  # carries an Altman caveat (D6), used in Epic 2


PHASE1_UNIVERSE: tuple[UniverseEntry, ...] = (
    # --- 10-K / us-gaap (D6) ---
    UniverseEntry("SHOP", "Shopify Inc.", "0001594805"),
    UniverseEntry("CP", "Canadian Pacific Kansas City Limited", "0000016875", capital_intensive=True),
    UniverseEntry("QSR", "Restaurant Brands International Inc.", "0001618756"),
    UniverseEntry("OTEX", "Open Text Corporation", "0001002638"),
    # --- 40-F / ifrs-full (D8) ---
    # Cameco: uranium mining. Verified live 2026-07-29 — resolves 17 of 18
    # canonical concepts from directly-filed ifrs-full tags across FY2017-2025,
    # including ProfitLossFromOperatingActivities, so its EBIT is read as filed
    # rather than derived. total_liabilities comes from the existing
    # assets-minus-equity identity derivation.
    # capital_intensive: mining carries heavy PP&E, so Altman runs structurally
    # low and the D6 caveat applies for the same reason it does to CP.
    UniverseEntry("CCJ", "Cameco Corporation", "0001009001", capital_intensive=True),
)
