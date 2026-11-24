# Ops 4: Famous-filer demo trial (AAPL, MSFT, NVDA, KO, NKE)

Status: review
Date: 2026-11-24
Scope: SEC EDGAR + Tiingo ingestion and figures rendered to a user, so the
live-data definition of done applies

## Why

The live demo's nine filers are not the names an interviewer will try first.
Lawrence chose (2026-11-24) to trial five widely known US filers and ship only
the ones that come out clean. This amends D11 ("the universe follows the
researcher"): these five are added for demonstration, not because they are
being researched. The amendment is recorded in `foundational-decisions.md`.

## Acceptance criteria

1. Each candidate's CIK is confirmed live against EDGAR before it is hardcoded.
2. Each candidate is run through the full pipeline on the DEV store only, never prod.
3. A candidate is **clean** when, for its latest scoreable fiscal year, all four
   models (Piotroski, Altman, Beneish, Sloan) compute (none `insufficient_data`),
   the reverse DCF resolves for that year, and review finds no defect in its
   inputs. Data-quality issues touching the latest year are explained;
   historical ones are inventoried exactly (filing, both values), with the
   cause where verified and "cause not established" otherwise. *(Amended
   2026-11-24 after review, by Lawrence's decision. It first read "no open
   issue unexplained", which the first write-up claimed without meeting.)*
4. Only clean candidates are added to `PHASE1_UNIVERSE`. Each rejected one is
   recorded with the reason.
5. Each shipped filer gets a `pending_fixture` golden entry, listed in `universe`,
   so the SM-1 coverage gap is explicit (D11 point 4 is amended to allow this
   for demo filers).
6. Each shipped filer's company page renders correctly in a browser against the
   dev store.
7. The verification is recorded in `engineering-findings.yaml`.

## Tasks

- [x] Confirm the five CIKs against `www.sec.gov/files/company_tickers.json` (AC 1):
      all five MATCH; the trial script refuses to fetch on any mismatch
- [x] Trial runner `scripts/trial_filers.py` + optional `entries` on `pipeline.run.main`
      (default unchanged, so the nightly run is untouched) (AC 2)
- [x] Run it on the dev store; tabulate the four models plus reverse DCF per filer (AC 3)
- [x] Triage: NKE rejected (Altman X3 insufficient every year; needs a mapping
      version, so a follow-up story). Every open issue on the other four explained (AC 3-4)
- [x] Add AAPL, NVDA, KO to `backend/pipeline/universe.py` (AC 4); MSFT was
      added, then withheld after review (see below)
- [x] `phase1_golden.yaml`: `pending_fixture` entries + `universe` list (AC 5)
- [x] `make test` (680 passed) and `make lint` pass
- [x] Render each shipped filer's page (AC 6): all render, no console errors
- [x] `engineering-findings.yaml#ops_4_famous_filer_trial`; D11 amendment; SPEC and
      README updated to match (AC 7)

## Verification

| Filer | Latest FY | Piotroski | Altman | Beneish | Sloan | Reverse DCF | Shipped |
|---|---|---|---|---|---|---|---|
| AAPL | 2026 | 9 Strong | 12.70 Safe | -2.52 | -0.034 | 27.6% | yes |
| MSFT | 2026 | 6 | 7.04 Safe | -2.64 | -0.071 | 31.1% | **withheld** (SG&A) |
| NVDA | 2026 | 4 | 59.94 Safe | -1.15 flagged | 0.109 high | 34.7% | yes |
| KO | 2025 | 7 | 4.56 Safe | -2.35 | 0.056 | 43.3% | yes |
| NKE | 2026 | 5 | insufficient (X3) | -2.19 | 0.006 | 23.5% | **no** |

Found by rendering: market values of a trillion or more read "4956.52B" (AAPL),
"2770.42B" (MSFT), "4561.13B" (NVDA). `compactAmount` had no trillions unit; no
earlier filer reached one. Lawrence chose (2026-11-24) to fix it in this story:

- [x] `compactAmount` T branch, gated on hundredths of a trillion (the PR #74
      gate-equals-display rule); tests pin the real AAPL figures, both sides of
      the 1.00T boundary, a negative, and SHOP's 209B unchanged
- [x] Frontend: 100 tests pass; tsc and eslint clean
- [x] Re-rendered: AAPL 4.96T, MSFT 2.77T, NVDA 4.56T; no four-digit "B" left
      on any of the four pages; KO and SHOP unchanged

### Codex review (MERGE AFTER FIXES), every finding re-verified before acting

- [x] MSFT withheld: SGAI built on G&A alone. The same mapping gap is LIVE for
      CPB, OTEX and SHOP, and the golden file pins their G&A-only SGAI. That is
      `sga_fallback_omits_selling_and_marketing`, the next story. No headline
      band can flip (bounded in the finding)
- [x] AC 3 amended (Lawrence); exact issue inventory in the findings entry.
      NVDA is 11 precision pairs plus 1 real recast; KO's 3 causes are not
      established
- [x] KO: FY2024 is the $6.0B IRS deposit, FY2025 the fairlife payment
      (verified from KO's stored facts)
- [x] NVDA flag: not growth alone (M -1.736 with SGI at 1), re-derived
- [x] SPEC SM-1 / open-questions and the golden header no longer claim full
      hand-verification
- [x] Golden universe bound to `PHASE1_UNIVERSE`; mutation (KO out of both
      YAML lists) fails
- [x] `tests/test_trial_filers.py`: 5 tests incl. a positive control; mutation
      (fetch before confirm) fails 3 of them
- [x] Formatter: Codex's commit `e133bcb` (trillion ties, negatives, existing
      B/M outputs; 116 frontend tests) kept as-is after reading it
- Deferred: `data_quality_warnings_hide_year_and_concept` (pre-existing UI gap)

Deferred, not this story: display names come from EDGAR `entityName`, so casing
is inconsistent ("NVIDIA CORP" beside "Apple Inc."). Already true of existing
filers ("CANADIAN PACIFIC KANSAS CITY  LTD/CN"). NKE stays out by Lawrence's
choice; no follow-up story is scheduled. NKE's trial rows remain in the dev store only.
