# Ops 3: Scores display at a readable precision

Status: review
Date: 2026-11-24
Scope: a figure rendered to a user, so the live-data definition of done applies

## Why

Scores are stored at the specs' `ratio_places: 6` and were shown at full
precision: SHOP's FY2025 Altman Z read "74.998229". The value is correct. SHOP
does not tag Liabilities, so it is derived as assets minus equity
(15.189B - 13.473B = 1.716B, FY2025 10-K), and against a 209B market value,
X4 dominates. The precision read as noise. Lawrence chose (2026-11-24) two
decimals on headlines, with the exact value kept on hover and in breakdowns.

## Acceptance criteria

1. Headline scores show two decimals; Piotroski, a 0-9 count, shows a whole number.
2. Rounding is decimal ROUND_HALF_EVEN on the stored digits (AD-15), never `toFixed`.
3. A shortened number never lands on a band boundary the exact value does not
   sit on; decimals are added until it clears, up to the stored six.
4. The exact stored value is available as a hover tooltip wherever a score is shortened.
5. The methodology worked example keeps exact values (it is a calculation).

## Tasks

- [x] `frontend/app/components/ui/scoreFormat.ts`: `formatScore`, `exactScore` (AC 1-3)
- [x] Applied to: verdict headline cards, per-year lens cards, gauge label, compare
      fallback, verdict glyph fallback; `title` carries the exact value (AC 4)
- [x] Methodology page left exact (AC 5)
- [x] `scoreFormat.test.ts`: two-decimal, whole-number, half-even ties, no
      negative zero, Beneish and Altman boundary guards
- [x] Updated the CompactVerdictCard test to the new display (`-2.50`, title `-2.5`)
- [x] Frontend: 99 tests pass; tsc and eslint clean
- [x] Rendered all 9 filers against the dev store

## Verification

| Filer | Model | Stored | Shown |
|---|---|---|---|
| SHOP | Altman | 74.998229 | 75.00 |
| SHOP | Beneish | -1.981461 | -1.98 |
| ZTS | Altman | 5.61532 | 5.62 |
| OTEX FY2013 | Altman | 2.98734 | **2.987**: 2.99 would be the Safe line, beside a "Grey" badge |
| CCJ FY2018 | Beneish | -1.78136 | **-1.781**: -1.78 would be the flag line, beside "No manipulation flag" |

The boundary guard (AC 3) fires on two real filers' per-year cards, so it is not
hypothetical.
