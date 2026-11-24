# Ops 5: SG&A includes selling and marketing

Status: in-progress
Date: 2026-11-24
Scope: concept mapping and a figure rendered to a user, so the live-data
definition of done applies
Finding: `engineering-findings.yaml#sga_fallback_omits_selling_and_marketing`

## Why

`us-gaap_v19.yaml` resolves `sga` from `SellingGeneralAndAdministrativeExpense`,
else `GeneralAndAdministrativeExpense` alone. A filer that reports selling and
marketing on its own line therefore gets G&A as its whole SG&A, and Beneish's
SGAI is computed on part of the concept. This is live for CPB, OTEX and SHOP
(18, 20 and 10 years), and is why MSFT was withheld in Ops 4. The golden file
pins SHOP's and CPB's G&A-only SGAI. No live headline band can flip (bounded in
the finding); the wrong figure is the SGAI component and the exact M.

## Verified before writing this (dev store, real EDGAR company facts)

- The four affected filers use ONE selling tag, `SellingAndMarketingExpense`,
  covering every year their G&A covers: CPB 18/18, OTEX 20/20, SHOP 11/11, MSFT 19/19.
- **G&A + S&M is an identity, exact to the million.** AAPL files the SG&A total
  and both parts for FY2023-26: 6,672 + 18,260 = 24,932; 7,458 + 18,639 = 26,097;
  8,077 + 19,524 = 27,601; 8,640 + 21,134 = 29,774.
- `AdvertisingExpense` must NOT be summed: for AAPL/MSFT it is a note disclosure
  inside S&M. For QSR it is an income-statement line, so the same tag means
  different things per filer.
- **No filer correctly uses "G&A alone = SG&A".** QSR FY2021-25 was the only
  other user, and for QSR it is a separate defect: from FY2021 it splits SG&A
  into G&A + advertising (2020: 407 + 870 vs the old 1,264 SG&A line), so its
  live FY2021 SGAI is 0.35. Recorded as its own finding.

## Decisions (Lawrence, 2026-11-24)

- QSR FY2021-25 resolves `insufficient_data` until a QSR-specific story restores
  it as G&A + its advertising line (AD-16: no partial figure).
- MSFT is re-admitted in this story (the D11 amendment pre-authorised it).

## Acceptance criteria

1. `sga` resolves from the filed SG&A total; otherwise, where both are filed for
   the year, as G&A + selling and marketing, carried as a derivation (`kind:
   identity`) with a published rationale. G&A alone never resolves `sga`.
2. The identity is pinned by a test using AAPL's four filed years, where the
   total and both parts are filed.
3. One mapping version: `concepts_v21` = `us-gaap_v20` + `derivations_v6`.
   Re-canonicalizing the dev store changes `sga` only for CPB, OTEX, SHOP and
   MSFT (now the sum), and QSR FY2021-25 (now absent). No other concept or
   filer changes.
4. Golden fixtures for SHOP, CPB and OTEX carry the real S&M facts their golden
   year needs. SGAI and M are re-verified by a computation that imports nothing
   from `backend/scoring` or `backend/formulas`. QSR's golden Beneish becomes
   `insufficient_data` with the reason.
5. Anything that labels a concept for display knows the two new operand
   concepts (the Story 6.6 label-map lesson).
6. MSFT re-enters `PHASE1_UNIVERSE` with a `pending_fixture` golden entry, and
   its FY2026 SGAI renders as 0.895175 (Codex's independent figure).
7. Rendered: SHOP, CPB, OTEX, QSR and MSFT pages show the corrected figures
   with no console errors; QSR's Beneish shows insufficient data, not 0.35.
8. Findings recorded: this one closed with evidence; QSR's split opened; the
   R&D-in-SG&A methodology question and CCJ's IFRS `AdministrativeExpense`
   recorded as open, not answered here.

## Tasks

- [ ] `us-gaap_v20.yaml`: `sga` loses G&A; new `general_and_administrative`
      and `selling_and_marketing` concepts (AC 1)
- [ ] `derivations_v6.yaml`: `sga_general_plus_selling` identity (AC 1)
- [ ] `registry.yaml` → `concepts_v21` with a HISTORY entry (AC 3)
- [ ] Identity test from AAPL's filed figures (AC 2)
- [ ] Fixtures: add S&M facts from the dev store's raw_facts (AC 4)
- [ ] Independent re-verification of SGAI/M; golden updated; QSR → insufficient (AC 4)
- [ ] Display label map for the new concepts (AC 5)
- [ ] Re-canonicalize the dev store; diff concepts_v20 vs v21 (AC 3)
- [ ] MSFT re-admitted: universe, golden, README, SPEC, D11 note (AC 6)
- [ ] `make test`, `make lint`, frontend checks
- [ ] Render the five pages (AC 7)
- [ ] Findings (AC 8)

## Out of scope (split rule)

- QSR's G&A + advertising restoration: its own story, next.
- Whether Beneish's SG&A should include R&D (Compustat's definition question):
  needs a primary-source check, recorded as an open question.
