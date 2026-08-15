/** Shared money formatting for the debt cards.
 *
 *  Extracted because the two cards had diverged: the near-term share used one
 *  decimal for billions and the maturity profile used two, so CP FY2023 rendered
 *  "3.1B" in one and "3.13B" in the other for two genuinely different figures —
 *  making a real measurement difference look like a formatting inconsistency, and
 *  vice versa. One helper means the two cards can only ever differ when the
 *  numbers do.
 *
 *  Deliberately unit-less. These are absolute amounts in the filer's own
 *  reporting currency (CP files in CAD), and the currency is labelled once on the
 *  card rather than assumed per value.
 */

/** Amount scaled into a magnitude's display units, rounded half-up to the number
 *  of decimals that magnitude actually renders.
 *
 *  Returned as an integer count of the smallest rendered unit (hundredths of a
 *  billion, tenths of a million) so the gate and the display read the SAME
 *  quantity. Two separate defects came from them reading different ones:
 *
 *  1. The billions gate tested one decimal (`round(abs / 1e8) / 10 >= 1`) while
 *     its branch rendered two, so everything from 950,000,000 up was promoted to
 *     billions and then printed below 1 — BCE's FY2020 near-term debt showed
 *     "0.97B", CP's FY2025 maturity bucket "0.99B", each sitting in a column of
 *     "M" values it could no longer be compared against. Eleven live figures.
 *  2. `toFixed` breaks ties on the binary representation, not half-up: 0.95 is
 *     stored just below 0.95, so `(0.95).toFixed(1)` is "0.9". The millions gate
 *     admitted 950,000 as "at least 1.0M" and the branch then printed "0.9M".
 *
 *  `Math.round` is half-up and is applied to the magnitude, so negatives round
 *  away from zero symmetrically rather than toward +Infinity.
 */
function inRenderedUnits(abs: number, unitSize: number): number {
  return Math.round(abs / unitSize);
}

export function compactAmount(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? -1 : 1;

  // Rounded BEFORE the magnitude test, so 999,999,999 renders "1.00B" rather
  // than "1000M" sitting in a column beside "1.00B" — but rounded to the two
  // decimals this branch prints, so a value that only reaches 1.0B at ONE
  // decimal (975,000,000) stays in millions instead of printing as "0.97B".
  const hundredthsOfBillion = inRenderedUnits(abs, 1e7);
  if (hundredthsOfBillion >= 100) {
    return `${((sign * hundredthsOfBillion) / 100).toFixed(2)}B`;
  }

  const tenthsOfMillion = inRenderedUnits(abs, 1e5);
  if (tenthsOfMillion >= 10) {
    return `${((sign * tenthsOfMillion) / 10).toFixed(1)}M`;
  }

  return value.toLocaleString();
}
