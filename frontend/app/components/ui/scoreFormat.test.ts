import { describe, expect, it } from "vitest";
import { formatScore } from "./scoreFormat";

describe("formatScore", () => {
  it("shows two decimals for a ratio-based model (SHOP FY2025 Altman Z)", () => {
    expect(formatScore("altman", 74.998229)).toBe("75.00");
    expect(formatScore("beneish", -1.981461)).toBe("-1.98");
    expect(formatScore("sloan", -0.055096)).toBe("-0.06");
  });

  it("shows Piotroski, a 0-9 count, as a whole number", () => {
    expect(formatScore("piotroski", 5)).toBe("5");
  });

  it("rounds half-even on the decimal digits, not on the binary value", () => {
    // 0.125 and 0.135 are exact ties at two decimals: half-even keeps the even digit.
    expect(formatScore("sloan", 0.125)).toBe("0.12");
    expect(formatScore("sloan", 0.135)).toBe("0.14");
    // 1.005 is stored in binary just below 1.005; toFixed(2) gives "1.00" for
    // the wrong reason. As a six-decimal score it is a tie, and half-even gives 1.00.
    expect(formatScore("altman", 1.005)).toBe("1.00");
    expect(formatScore("altman", 1.015)).toBe("1.02");
  });

  it("never prints a negative zero", () => {
    expect(formatScore("sloan", -0.001)).toBe("0.00");
  });

  it("adds decimals rather than print a band boundary the value does not sit on", () => {
    const beneish = [
      { label: "No manipulation flag", below: -1.78 },
      { label: "Manipulation flag", min: -1.78 },
    ];
    // -1.7849 is below -1.78, but two decimals would print the boundary itself.
    expect(formatScore("beneish", -1.7849, beneish)).toBe("-1.785");
    // -1.7801 needs four decimals before it stops reading as -1.78.
    expect(formatScore("beneish", -1.7801, beneish)).toBe("-1.7801");
    // A value exactly on the boundary may print as the boundary.
    expect(formatScore("beneish", -1.78, beneish)).toBe("-1.78");
    // Far from any boundary, the bands change nothing.
    expect(formatScore("beneish", -2.5, beneish)).toBe("-2.50");
  });

  it("applies the boundary guard to Altman's 1.81 and 2.99 lines too", () => {
    const altman = [
      { label: "Distress", below: 1.81 },
      { label: "Grey", min: 1.81, max: 2.99 },
      { label: "Safe", above: 2.99 },
    ];
    expect(formatScore("altman", 2.994, altman)).toBe("2.994");
    expect(formatScore("altman", 1.8149, altman)).toBe("1.815");
    expect(formatScore("altman", 3.4, altman)).toBe("3.40");
  });
});
