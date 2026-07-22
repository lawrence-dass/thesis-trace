"""Phase-1 Company Universe (foundational decision D6).

All four are US-GAAP 10-K filers on EDGAR. All CIKs confirmed live against
data.sec.gov/submissions/ (2026-07-21) before being hardcoded here.
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
    UniverseEntry("SHOP", "Shopify Inc.", "0001594805"),
    UniverseEntry("CP", "Canadian Pacific Kansas City Limited", "0000016875", capital_intensive=True),
    UniverseEntry("QSR", "Restaurant Brands International Inc.", "0001618756"),
    UniverseEntry("OTEX", "Open Text Corporation", "0001002638"),
)
