import { describe, expect, it } from "vitest";
import { compactAmount } from "./format";

/** `compactAmount` exists because two debt cards diverged on the same figure, and
 *  its docstring records the exact fix: round BEFORE the magnitude test, so
 *  999,999,999 reads "1.00B" rather than "1000M" in a column beside real billions.
 *
 *  Nothing enforced that. PR #64's review then found a LOCAL re-implementation in
 *  the reverse-DCF card that had dropped the same fix, so the two cards on one page
 *  would have disagreed at that boundary again. A documented rule with no test is
 *  how the rule gets re-broken — this is the test.
 */
describe("compactAmount", () => {
  it("rounds before choosing the magnitude, so 999,999,999 is billions", () => {
    // THE BOUNDARY THE HELPER WAS EXTRACTED FOR. Naive code tests the raw value
    // against 1e9, fails, and renders "1000.0M".
    expect(compactAmount(999_999_999)).toBe("1.00B");
  });

  it("applies the same rounding at the millions boundary", () => {
    expect(compactAmount(999_999)).toBe("1.0M");
  });

  it("formats plain billions and millions", () => {
    expect(compactAmount(3_130_000_000)).toBe("3.13B");
    expect(compactAmount(547_000_000)).toBe("547.0M");
  });

  it("uses two decimals for billions and one for millions", () => {
    // Not cosmetic: the divergence that prompted the extraction was CP FY2023
    // rendering "3.1B" on one card and "3.13B" on the other for two genuinely
    // different figures, which made a real difference look like a formatting bug.
    expect(compactAmount(3_100_000_000)).toBe("3.10B");
    expect(compactAmount(3_100_000)).toBe("3.1M");
  });

  it("leaves sub-million amounts as locale-formatted integers", () => {
    expect(compactAmount(949_000)).toBe((949_000).toLocaleString());
    expect(compactAmount(949_999)).toBe((949_999).toLocaleString());
  });

  // ────────────────────────────────────────────────────────────────────────────
  // DELIBERATELY NOT ASSERTED: compactAmount(950_000).
  //
  // It returns "0.9M" today, and that is a gate/display disagreement rather than a
  // considered choice. The millions gate is `Math.round(abs / 1e5) / 10 >= 1`,
  // which for 950,000 rounds to exactly 1.0 and admits the value into the millions
  // branch — and the branch then renders `(0.95).toFixed(1)`, which is "0.9"
  // because 0.95 is not exactly representable in binary. So the gate says "this is
  // at least 1.0M" and the formatter prints less than that, in the one helper whose
  // entire reason for existing is that two cards disagreed about a boundary.
  //
  // It is NOT pinned here because the fix is a presentation decision with two
  // coherent answers and very different blast radii, measured 2026-08-13:
  //   (a) make the gate match its display  -> 950,000 renders "950,000".  1 input changes.
  //   (b) make the display match the gate  -> 950,000 renders "1.0M".   461 inputs change,
  //       because it also switches .x5 cases to round-half-up (900,050,000 -> "900.1M").
  // (b) is the more faithful reading of the docstring's stated intent — it PROMOTES
  // a value that rounds up, which is exactly what the 999,999,999 case describes.
  //
  // Asserting either would bless a disputed rendering. Left for a decision; no real
  // filer figure is exactly 950,000, so nothing is broken on the page today.
  // ────────────────────────────────────────────────────────────────────────────

  it("keeps the sign, choosing magnitude on the absolute value", () => {
    // Capex and some cash-flow operands arrive negative. Testing magnitude on the
    // signed value would send every negative amount down the smallest branch.
    expect(compactAmount(-3_130_000_000)).toBe("-3.13B");
    expect(compactAmount(-547_000_000)).toBe("-547.0M");
    expect(compactAmount(-999_999_999)).toBe("-1.00B");
  });

  it("handles zero without a magnitude suffix", () => {
    expect(compactAmount(0)).toBe("0");
  });
});
