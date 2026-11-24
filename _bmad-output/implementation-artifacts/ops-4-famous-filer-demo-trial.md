# Ops 4: Famous-filer demo trial (AAPL, MSFT, NVDA, KO, NKE)

Status: in-progress
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
   the reverse DCF resolves for that year, and no open data-quality issue on it
   is unexplained.
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
- [x] Add AAPL, MSFT, NVDA, KO to `backend/pipeline/universe.py` (AC 4)
- [x] `phase1_golden.yaml`: `pending_fixture` entries + `universe` list (AC 5)
- [x] `make test` (680 passed) and `make lint` pass
- [x] Render each shipped filer's page (AC 6): all render, no console errors
- [x] `engineering-findings.yaml#ops_4_famous_filer_trial`; D11 amendment; SPEC and
      README updated to match (AC 7)

## Verification

| Filer | Latest FY | Piotroski | Altman | Beneish | Sloan | Reverse DCF | Shipped |
|---|---|---|---|---|---|---|---|
| AAPL | 2026 | 9 Strong | 12.70 Safe | -2.52 | -0.034 | 27.6% | yes |
| MSFT | 2026 | 6 | 7.04 Safe | -2.64 | -0.071 | 31.1% | yes |
| NVDA | 2026 | 4 | 59.94 Safe | -1.15 flagged | 0.109 high | 34.7% | yes |
| KO | 2025 | 7 | 4.56 Safe | -2.35 | 0.056 | 43.3% | yes |
| NKE | 2026 | 5 | insufficient (X3) | -2.19 | 0.006 | 23.5% | **no** |

Found by rendering: market values of a trillion or more read "4956.52B" (AAPL),
"2770.42B" (MSFT), "4561.13B" (NVDA). `compactAmount` has no trillions unit; no
earlier filer reached one.
