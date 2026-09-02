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
    # IFRS cash-flow classification verified from the filer's explicit interest-paid
    # tag. This is source data about the issuer, not a reverse-DCF assumption.
    interest_outside_operating: bool = False


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
    UniverseEntry(
        "CCJ",
        "Cameco Corporation",
        "0001009001",
        capital_intensive=True,
        interest_outside_operating=True,
    ),
    # BCE: telecom. Verified live 2026-08-02 — 288 ifrs-full concepts, FY2017-2025.
    # Resolves 15 of 18 canonical concepts directly. Its gaps are presentation, not
    # tagging quality: no SG&A line (IAS 1 by-nature, so Beneish SGAI stays
    # insufficient_data), no gross profit line, and no operating-profit line, so
    # `ebit` awaits the D8 consequence-3 decision. Switched its PP&E tag to the
    # right-of-use-inclusive variant after FY2022 — covered by the ifrs-full_v2
    # fallback, without which BCE would silently lose 3 of its 9 years.
    # capital_intensive: telecom network build-out, same Altman caveat as CP.
    UniverseEntry("BCE", "BCE Inc.", "0000718940", capital_intensive=True),
    # Suncor: integrated oil and gas. Verified live 2026-08-02 — 234 ifrs-full
    # concepts, FY2017-2025, resolving 13 of 18 directly plus total_liabilities from
    # the assets-minus-equity derivation. The most degraded filer in the universe and
    # deliberately so: it tags NO retained earnings at all, so Altman's X2 genuinely
    # cannot resolve, and four of its concepts come from by-nature variant tags that
    # are not like-for-like with a by-function filer (see ifrs-full_v2.yaml's footer).
    # It earns its place by being the honest hard case, not the clean one.
    UniverseEntry("SU", "Suncor Energy Inc.", "0000311337", capital_intensive=True),
    # --- Epic 12 (D11): US universe expansion, driven by real decision packets ---
    # CPB: packaged foods, non-calendar FYE (early August). Story 12.1-12.4
    # hand-verified live: 20 of 22 canonical concepts resolve for FY2025 with no
    # new mapping work; its legacy pre-ASC-606 revenue tag was checked and
    # REJECTED (measures something ~35% different, not the same concept renamed
    # — see us-gaap_v9.yaml's revenue note). capital_intensive=False: its FY2025
    # Altman Grey band (1.850072) reflects the FY2024 Sovos Brands acquisition's
    # debt load, not a structurally PP&E-heavy business the way CP/CCJ/BCE/SU
    # are — confirmed by comparing against those filers' own Z-scores, all of
    # which run structurally low every year, not just after a debt-financed deal.
    UniverseEntry("CPB", "The Campbell's Company", "0000016732"),
    # ZTS: animal health pharma, calendar FYE. Never tags OperatingIncomeLoss —
    # the first us-gaap filer to need the ebit_pbt_plus_interest derivation
    # (Story 12.3, us-gaap_v9.yaml + derivations_v5.yaml), previously ifrs-full
    # only. Its restricted-cash-inclusive cash_and_equivalents fallback is the
    # first use of excludes_issuers: proven unsafe for ZTS specifically (its own
    # RestrictedCashCurrent tag) while remaining proven-safe for QSR under the
    # exact same source rule — see us-gaap_v9.yaml's cash_and_equivalents note.
    # capital_intensive=False: FY2025 Altman Z=5.615320, Safe.
    UniverseEntry("ZTS", "Zoetis Inc.", "0001555280"),
)
