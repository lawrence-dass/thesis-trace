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
  // THE GATE AND THE DISPLAY MUST READ THE SAME QUANTITY. Resolved 2026-08-14;
  // the three tests below are the boundary cases, and each is the deliverable
  // rather than an extra — a gate change is only correct if both sides are pinned.
  // ────────────────────────────────────────────────────────────────────────────

  it("does not promote to billions a value that only reaches 1.0B at one decimal", () => {
    // THE LIVE DEFECT, and the reason this was not merely the 950,000 curiosity.
    // The old billions gate tested ONE decimal (`round(abs / 1e8) / 10 >= 1`)
    // while the branch printed TWO, so everything from 950,000,000 up was
    // promoted and then rendered below 1: these three figures showed "0.97B",
    // "0.99B" and "0.98B" on real pages, in columns of "M" values they could no
    // longer be read against. All three are real dev-store facts.
    // The two that were VISIBLY WRONG on a rendered page, confirmed in the
    // browser 2026-08-14 — CP's Year 4 repayment bucket and the headline of
    // Suncor's near-term debt card, which read "0.97B of 9.99B".
    expect(compactAmount(990_000_000)).toBe("990.0M"); // CP debt_maturity_year_4 FY2025
    expect(compactAmount(973_000_000)).toBe("973.0M"); // SU near_term_debt FY2025
    // Served in an overview payload but not currently rendered as an amount
    // (earlier-year rows show only the percentage). Pinned anyway: whether a
    // figure reaches a card is a layout decision that can change, and the
    // formatter must be right regardless of who calls it.
    expect(compactAmount(975_000_000)).toBe("975.0M"); // BCE near_term_debt FY2020
  });

  it("still promotes a value that DOES reach 1.00B at two decimals", () => {
    // The other side of the same boundary. Narrowing the gate must not break the
    // case the helper was extracted for — 999,999,999 is asserted above, and
    // CCJ's FY2025 total debt is the real figure that crosses at two decimals.
    expect(compactAmount(996_348_000)).toBe("1.00B"); // CCJ total_debt FY2025
    expect(compactAmount(995_000_000)).toBe("1.00B"); // exact .995 tie, rounds up
    expect(compactAmount(994_999_999)).toBe("995.0M"); // just below it
  });

  it("breaks ties half-up rather than on the binary representation", () => {
    // `toFixed` rounds by what the double actually stores: 0.95 sits just below
    // 0.95, so `(0.95).toFixed(1)` is "0.9" — the millions gate admitted 950,000
    // as "at least 1.0M" and the branch then printed less than that. Rounding
    // half-up before the test makes the two agree by construction.
    expect(compactAmount(950_000)).toBe("1.0M");
    expect(compactAmount(900_050_000)).toBe("900.1M");
    expect(compactAmount(3_150_000)).toBe("3.2M");
  });

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
