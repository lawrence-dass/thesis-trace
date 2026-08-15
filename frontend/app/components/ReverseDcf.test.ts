import { describe, expect, it } from "vitest";
import {
  OPERAND_LABEL_KEYS,
  bandGeometry,
  formatRate,
  inlineLabel,
  joinList,
  labelFor,
} from "./ReverseDcf";

/** Story 6.6 shipped these as pure, trivially testable, untested functions —
 *  there was no frontend test runner at all. Each block below pins a rule the
 *  source states in prose, because this repo's most repeated failure is a
 *  documented rule that nothing enforces.
 */

describe("formatRate", () => {
  it("renders a fraction as a percentage", () => {
    // Rates cross the wire as FRACTIONS (0.372), never as percentages. A reader of
    // the API who assumed percent would render 0.372% for CP's 37.2%.
    expect(formatRate(0.372)).toBe("37.2%");
    expect(formatRate(0.0264287144)).toBe("2.6%");
  });

  it("keeps the sign — decline is a real answer, not a missing one", () => {
    // OTEX's band runs from -6.5%, and the reader comparing an implied rate
    // against an actual decline needs the minus sign.
    expect(formatRate(-0.065)).toBe("-6.5%");
  });

  it("renders an absent rate as an em dash, never as zero", () => {
    // AD-16: a missing input is insufficient_data, never a defaulted 0. Rendering
    // "0.0%" would assert the market implies no growth.
    expect(formatRate(null)).toBe("—");
    expect(formatRate(undefined)).toBe("—");
  });

  it("refuses non-finite values rather than printing NaN%", () => {
    expect(formatRate(Number.NaN)).toBe("—");
    expect(formatRate(Number.POSITIVE_INFINITY)).toBe("—");
  });

  it("honours a requested precision", () => {
    expect(formatRate(0.372, 0)).toBe("37%");
    expect(formatRate(0.3721, 2)).toBe("37.21%");
  });
});

describe("joinList", () => {
  it("uses a serial comma for three or more terms", () => {
    // THE COMMA IS LOAD-BEARING, NOT STYLISTIC. One operand is itself named "cash
    // and equivalents", so without it the tail reads "total debt and cash and
    // equivalents" — three items or two, unknowable.
    expect(joinList(["market capitalisation", "total debt", "cash and equivalents"])).toBe(
      "market capitalisation, total debt, and cash and equivalents",
    );
  });

  it("joins two terms with a bare and", () => {
    expect(joinList(["cash from operations", "capital expenditure"])).toBe(
      "cash from operations and capital expenditure",
    );
  });

  it("returns a single term unchanged", () => {
    expect(joinList(["free cash flow"])).toBe("free cash flow");
  });

  it("returns an empty string for no terms rather than undefined", () => {
    // Rendered straight into prose; `undefined` would print literally.
    expect(joinList([])).toBe("");
  });
});

describe("labelFor", () => {
  it("labels the four DERIVATION LEAVES the API emits recursively", () => {
    // The gap /code-review found on PR #64. `_append_reverse_dcf_fact_operand`
    // walks each derived fact's own operands, so CCJ emits near_term_debt /
    // long_term_debt and BCE emits all four. Neither filer was in the browser
    // spot-check the first version of this map was written against, so they
    // rendered as raw snake_case beside properly cased labels.
    expect(labelFor("near_term_debt")).toBe("Near-term debt");
    expect(labelFor("long_term_debt")).toBe("Long-term debt");
    expect(labelFor("cash")).toBe("Cash");
    expect(labelFor("cash_equivalents")).toBe("Cash equivalents");
  });

  it("uses the solver's own operand name, not a guessed one", () => {
    // The first version guessed `market_capitalisation`; the solver emits
    // `market_cap`, so the label silently fell through to the raw name.
    expect(labelFor("market_cap")).toBe("Market capitalisation");
    expect(labelFor("cash_from_operations")).toBe("Cash from operations");
    expect(labelFor("capex")).toBe("Capital expenditure");
  });

  it("degrades an unmapped name to spaced words rather than snake_case", () => {
    expect(labelFor("some_future_operand")).toBe("some future operand");
  });

  it("covers every operand the reverse-DCF API can emit", () => {
    // The map's own comment claims to be exhaustive. This is what makes that claim
    // enforceable: adding an operand backend-side without a label fails here
    // instead of rendering lowercase on the page.
    const emitted = [
      "free_cash_flow",
      "cash_from_operations",
      "capex",
      "market_cap",
      "market_price",
      "shares_outstanding",
      "total_debt",
      "cash_and_equivalents",
      "enterprise_value",
      "near_term_debt",
      "long_term_debt",
      "cash",
      "cash_equivalents",
    ];
    expect(new Set(OPERAND_LABEL_KEYS)).toEqual(new Set(emitted));
  });
});

describe("inlineLabel", () => {
  it("lowers the first character so a label reads as prose mid-sentence", () => {
    expect(inlineLabel("cash_from_operations")).toBe("cash from operations");
    expect(inlineLabel("market_cap")).toBe("market capitalisation");
  });

  it("does not lower anything but the first character", () => {
    expect(inlineLabel("near_term_debt")).toBe("near-term debt");
  });
});

describe("bandGeometry", () => {
  it("always keeps zero inside the domain", () => {
    // THE RULE THE PLOT EXISTS FOR. Whether the price implies contraction or
    // growth is the single most important read on the card, so a domain that
    // floated above zero would hide the sign change. CP's band is entirely
    // positive (16.4%..51.6%) and zero must still be on the track.
    const { pos } = bandGeometry(0.164, 0.516, 0.372, 0.078);
    expect(pos(0)).toBeGreaterThanOrEqual(0);
    expect(pos(0)).toBeLessThanOrEqual(100);
  });

  it("keeps zero on the track for an entirely NEGATIVE band too", () => {
    const { pos } = bandGeometry(-0.4, -0.1, -0.2, null);
    expect(pos(0)).toBeGreaterThanOrEqual(0);
    expect(pos(0)).toBeLessThanOrEqual(100);
  });

  it("places every mark within the track", () => {
    // OTEX: the band crosses zero AND the achieved rate exceeds the implied one.
    const low = -0.065;
    const high = 0.207;
    const implied = 0.097;
    const historical = 0.128;
    const { pos } = bandGeometry(low, high, implied, historical);
    for (const mark of [low, high, implied, historical, 0]) {
      expect(pos(mark)).toBeGreaterThanOrEqual(0);
      expect(pos(mark)).toBeLessThanOrEqual(100);
    }
  });

  it("includes the historical mark in the domain when it lies outside the band", () => {
    // OTEX's achieved 12.8% sits below its 20.7% high, but a filer whose achieved
    // growth exceeds the whole band must not have that mark fall off the track.
    const { pos } = bandGeometry(0.05, 0.1, 0.07, 0.9);
    expect(pos(0.9)).toBeLessThanOrEqual(100);
    expect(pos(0.9)).toBeGreaterThan(pos(0.1));
  });

  it("treats a null historical rate exactly like zero — because zero is always in the domain anyway", () => {
    // NOT a coincidence, and worth pinning: `marks` seeds 0 unconditionally, so a
    // filer reporting 0% achieved growth cannot be distinguished GEOMETRICALLY
    // from one reporting none. The difference is carried by whether the mark is
    // drawn, not by the domain. Anyone changing the zero rule will land here and
    // see that this equivalence was intended rather than accidental.
    const withNull = bandGeometry(0.164, 0.516, 0.372, null);
    const withZero = bandGeometry(0.164, 0.516, 0.372, 0);
    expect(withNull.bandLeft).toBeCloseTo(withZero.bandLeft, 10);
    expect(withNull.bandWidth).toBeCloseTo(withZero.bandWidth, 10);
  });

  it("does widen the domain for a historical rate outside the band", () => {
    // The other half of the above: the domain is not inert to `historical`, it is
    // only inert to the one value that was already guaranteed to be in it.
    const withNull = bandGeometry(0.164, 0.516, 0.372, null);
    const withOutlier = bandGeometry(0.164, 0.516, 0.372, 0.9);
    expect(withOutlier.bandWidth).toBeLessThan(withNull.bandWidth);
  });

  it("gives a degenerate band a visible width instead of none", () => {
    // A band whose ends coincide has zero span. Rendering nothing would read as
    // "no band" rather than "a very tight one".
    const { bandWidth } = bandGeometry(0.2, 0.2, 0.2, null);
    expect(bandWidth).toBeGreaterThanOrEqual(0.5);
    expect(Number.isFinite(bandWidth)).toBe(true);
  });

  it("produces finite positions when every mark coincides", () => {
    // The `|| 0.01` span fallback. Without it this divides by zero and every mark
    // becomes NaN, which React renders as `left: NaN%` — an invisible plot.
    const { pos, bandLeft, bandWidth } = bandGeometry(0, 0, 0, 0);
    expect(Number.isFinite(pos(0))).toBe(true);
    expect(Number.isFinite(bandLeft)).toBe(true);
    expect(Number.isFinite(bandWidth)).toBe(true);
  });

  it("orders the band left-to-right", () => {
    const { pos, bandLeft, bandWidth } = bandGeometry(0.164, 0.516, 0.372, 0.078);
    expect(pos(0.164)).toBeLessThan(pos(0.516));
    expect(bandLeft).toBeGreaterThanOrEqual(0);
    expect(bandLeft + bandWidth).toBeLessThanOrEqual(100);
  });
});
