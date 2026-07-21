"""Phase-1 Company Universe (foundational decision D6).

All four are US-GAAP 10-K filers on EDGAR. CIKs are needed for live ingestion;
SHOP is confirmed. The others are marked needs_cik until confirmed against EDGAR
during the first live run (gated — see the standing "ask before live fetch"
decision), so nothing fetches a guessed CIK.
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
    UniverseEntry("CP", "Canadian Pacific Kansas City Limited", None, capital_intensive=True),
    UniverseEntry("QSR", "Restaurant Brands International Inc.", None),
    UniverseEntry("OTEX", "Open Text Corporation", None),
)
