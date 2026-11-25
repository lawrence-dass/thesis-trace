# Ops 8: The company page reads cleanly in a demo

Status: review
Date: 2026-11-25
Scope: text and figures rendered to a user, so the live-data definition of done applies
(render it in a browser). Frontend only; no spec, mapping or API change.

## Why

A demo-readiness pass over the live site (2026-11-25) found three rough edges a careful
viewer would notice on AAPL's page, the likeliest demo subject:

1. **Reverse DCF assumptions row.** "Discount rate 10%", "Terminal growth 2.5%" and
   "Horizon 5 years" each wrapped onto their own line, with the values pushed to
   different distances across the card. Cause: `Term`'s collapsed definition panel
   collapses its HEIGHT (`grid-rows-[0fr]`) but still contributes its full text WIDTH
   to the label's intrinsic size, so each label is as wide as its hidden definition.
   `Term` is used site-wide.
2. **"Today's price".** The card asks what growth "today's price" requires, but the
   price is the close on the fiscal-year-end date (AAPL: 2026-09-25), two months old.
3. **Data-quality warnings.** The Integrity section prints the identical line
   "Ambiguous source selection (needs_review, raised by canonicalization)" 17 times for
   AAPL. The API already serves the year, concept and both values in `detail`; the page
   drops them (`engineering-findings.yaml#data_quality_warnings_hide_year_and_concept`).

## Acceptance criteria

1. A collapsed `Term` contributes no width to its container; expanded, it behaves as
   before. On the reverse DCF card the three assumptions and the spec sit on one row at
   desktop width.
2. The reverse DCF card states the date and value of the market price it uses, taken
   from the stored `market_price` operand. Frontend copy no longer calls it "today's"
   price. (The spec-owned `attribution` text is stored per run and is NOT edited here:
   changing it needs `reverse_dcf_v2`. Recorded as a deferred finding.)
3. Each data-quality warning shows what it is about: the fiscal year (or the period for
   an ingestion conflict) and the concept.
4. Each warning shows the competing values EXACTLY, from the stored decimal strings,
   never compacted or float-rounded, so a 1M difference on a 14.5B figure and a
   0.000006 vs 0.00000625 par value both stay visible.
5. Warnings are ordered newest year first, so a current-year issue is never buried
   under history.
6. A warning whose `detail` has an unrecognised shape still renders its type, status
   and source as today (no crash, no blank row).

## Tasks

- [x] `Term.tsx`: collapsed panel `w-0 min-w-full`; `Term.test.tsx` pins it (AC 1)
- [x] `ReverseDcf.tsx`: `priceBasis` + price line beside the fiscal year; subtitle
      copy; `termDefinitions.ts` implied-growth wording; `priceBasis` tests (AC 2)
- [x] `ui/dataQuality.ts`: `describeIssue` + `exactValue`, pure functions (AC 3-6)
- [x] `dataQuality.test.ts`: both real shapes (AAPL ambiguous_selection, a dei
      source_conflict), the 1M-on-14.5B case, the par-value case, ordering, unknown shape
- [x] Company page renders the described warnings (AC 3-6)
- [x] `engineering-findings.yaml`: closed `data_quality_warnings_hide_year_and_concept`;
      added the deferred `reverse_dcf_attribution_says_todays_price` (curated)
- [x] Frontend: 148 tests pass; tsc and eslint clean. Backend `make test`: 717 pass
- [x] Rendered against the dev store: AAPL (reverse DCF + 17 warnings, dark), MSFT
      (7 source_conflict + 1 ambiguous_selection, light), Beneish methodology (inline
      `Term` expanded, light). No console errors

## Verification

| Page | Before | After |
|---|---|---|
| AAPL reverse DCF assumptions | three rows, values at three different x positions | one row: "Discount rate 10% · Terminal growth 2.5% · Horizon 5 years · Spec reverse_dcf_v1" |
| AAPL reverse DCF header | "FY2026" | "FY2026 · price 341.07 USD on 2026-09-25" |
| AAPL warnings | 17 × "Ambiguous source selection (needs_review, …)" | e.g. "FY2008 retained_earnings … 13,845,000,000 vs 15,129,000,000", newest first; all 17 are FY2007-FY2008 |
| MSFT warnings | 8 identical-shaped lines | "period ending 2026-06-30 dei:EntityListingParValuePerShare … Company Facts 0.000006 vs Inline XBRL 0.00000625" + resolution |

An EXPANDED `Term` in a flex row still widens its label (Terminal growth's value
moves right while its definition is open). That is the pre-existing open-state
behaviour and is out of this story's AC 1, which is about the collapsed state.

Seen while rendering, not caused or changed here: OTEX's Beneish resolves only
FY2011-FY2019, already recorded (depreciation tag covers FY2008-2019 only).
