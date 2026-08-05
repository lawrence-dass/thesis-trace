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
export function compactAmount(value: number): string {
  const abs = Math.abs(value);
  // Rounded BEFORE the magnitude test, so 999,999,999 renders "1.00B" rather
  // than "1000M" sitting in a column beside "1.00B".
  if (Math.round(abs / 1e8) / 10 >= 1) return `${(value / 1e9).toFixed(2)}B`;
  if (Math.round(abs / 1e5) / 10 >= 1) return `${(value / 1e6).toFixed(1)}M`;
  return value.toLocaleString();
}
