# Ops 5: SG&A includes selling and marketing

Status: review
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

- [x] `us-gaap_v20.yaml`: `sga` loses G&A; new `general_and_administrative`
      and `selling_and_marketing` concepts (AC 1)
- [x] `derivations_v6.yaml`: `sga_general_plus_selling` identity (AC 1)
- [x] `registry.yaml` → `concepts_v21` with a HISTORY entry (AC 3)
- [x] `test_sga_derivation.py`: AAPL's filed figures through real
      canonicalization: parts derive the total exactly; a filed total wins;
      G&A alone derives nothing (positive control) (AC 2)
- [x] Fixtures: `scripts/extend_fixture_concept.py` adds S&M facts from the same
      filings as each fixture's G&A; refuses unless the file round-trips byte
      for byte (+204 lines, additions only) (AC 4)
- [x] `scripts/verify_sga_golden.py` (imports nothing from scoring) reproduces
      the OLD golden SGAI and M exactly first, then: SHOP -2.011375, CPB
      -2.704602, OTEX -2.880276. Pipeline agrees to six places. QSR → null (AC 4)
- [x] Gross-margin guard tests moved from QSR to ZTS (a real subject still)
- [x] `CitationChip` labels all six derivation rules (five fell back to raw
      names); a test reads the live spec, mutation-checked (AC 5)
- [x] Re-canonicalized: only `sga` changed (CPB, MSFT, OTEX, SHOP), QSR
      FY2021-25 removed, operands added, no other concept moved (AC 3)
- [x] Re-scored (`scripts/rescore_beneish.py`): 36 years moved, max 0.031,
      no band flip either way
- [x] Stale `sga` issues (G&A conflicts) dismissed on dev by rule:
      `scripts/dismiss_stale_sga_issues.py` (MSFT FY2009, SHOP FY2022)
- [x] MSFT re-admitted: universe, golden, README, SPEC, D11 note; FY2026 SGAI
      0.895175, M -2.638076, as the Ops 4 review computed (AC 6)
- [x] `make test` (692), `make lint`, frontend 118 tests
- [x] Rendered QSR (FY2021-25 insufficient, verdict labelled FY2020) and SHOP,
      CPB, OTEX, MSFT (new M present, old absent); no console errors (AC 7)
- [x] Findings: this one resolved with evidence; QSR split, Beneish R&D scope
      and CCJ recorded open (AC 8)

### Codex review (MERGE AFTER FIXES), every finding re-verified before acting

The full review had six findings; 1-5 in commit `778f8b2`, 6 below.

- [x] **6. Corrected SGAI lived only in comments; M checked within 1e-3.** M is
      now exact at six places for every filer, and entries declare asserted
      `indices` (SHOP and CPB all eight, OTEX sgai). Codex's own mutation (CPB
      S&M 925M for 924M) passed before and fails now.
- [x] Judgement calls: the verifier's "as originally filed" reworded to what a
      trimmed fixture can show; SG&A's scope (functional lines such as R&D and
      OTEX's amortization are not operands) recorded with the open R&D question.
      Codex independently recomputed OTEX's eight indices and reproduced old and
      new M exactly.

- [x] **Dismissal rule could hit a genuine conflict.** Value matching within +/-1
      year is coincidence, not proof. Now proven: the issuer files NO SG&A total
      that fiscal year (sga had exactly two sources, so every candidate was G&A),
      and every value is an annual USD G&A fact ending in that exact year.
      `test_dismiss_stale_sga_issues.py`: the review's counterexample, a same-year
      coincidence, a neighbouring-year match, resolved and annotated issues, and a
      positive control; each of the three conditions mutation-checked. On real data
      the new rule still selects exactly MSFT FY2009 and SHOP FY2022.
- [x] **It also rewrote resolved issues.** Now `needs_review` only, and never
      overwrites an existing `resolution`.
- [x] **Verifier's "annual" admitted quarters** (calendar-year subtraction). Now a
      350-380 day duration; a same-filing conflict refuses to choose.
- [x] **The "gate" did not stop anything.** It printed MISMATCH and carried on.
      Now exits before computing new values; checked with a deliberately wrong
      golden SGAI (0.663883), which it refused.
- [x] **Backdated verdicts were unlabelled** on the overview cards and the compare
      table. Each now states its FY, and "FY2020 · later years insufficient" when
      it lags the company's newest verdict (`ui/verdictYear.ts`, tested). Rendered:
      QSR FY2020 and SHOP FY2024 labelled, AAPL not; compare page likewise.
      Pre-existing for SHOP; this story made it a five-year lag for QSR.

## After merge (production)

- The nightly pipeline re-canonicalizes and re-scores under concepts_v21 and
  ingests MSFT. No migration, no Render deploy (pipeline-only).
- **Needs Lawrence's OK:** run `scripts/dismiss_stale_sga_issues.py` against
  production. SHOP's FY2022 `sga` issue is live and would otherwise show beside
  its replacement.
- "What changed" will list these Beneish moves for CPB, OTEX and SHOP: a
  mapping fix, not a filing (`changes_since_pivot_include_backfill_rescoring`).

## Out of scope (split rule)

- QSR's G&A + advertising restoration: its own story, next.
- Whether Beneish's SG&A should include R&D (Compustat's definition question):
  needs a primary-source check, recorded as an open question.
