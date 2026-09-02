import { describe, expect, it } from "vitest";
import { axisState, type VerdictItem } from "./VerdictGlyph";

/** `axisState` decides each spoke's length, dash pattern and tone. The one
 *  invariant every branch must hold: an absence (insufficient_data,
 *  excluded_out_of_scope) must render as a short, DASHED, never-zero spoke
 *  in a non-pass tone — never something that could be read as "measured and
 *  low" (AD-16). A `computed_with_caveat` model must keep its REAL position
 *  and REAL band tone, matching what the Gauge on the detail card below it
 *  already shows for that same model — the glyph must not invent a second,
 *  disagreeing convention for the same state.
 */

function verdict(overrides: Partial<VerdictItem>): VerdictItem {
  return {
    model: "piotroski",
    category: "quality_health",
    fiscal_year: 2025,
    aggregate_value: null,
    band_label: null,
    applicability: "computed",
    missing_signals: [],
    caveat_reason: null,
    ...overrides,
  };
}

describe("axisState", () => {
  it("gives a computed value with a band label its real position and real tone", () => {
    const s = axisState(verdict({ model: "piotroski", aggregate_value: 6, band_label: "Middle" }));
    expect(s.dashed).toBe(false);
    expect(s.tone).toBe("caveat");
    expect(s.label).toBe("Middle");
    // domainPct(piotroski=[0,9], 6) = 6/9*100 ≈ 66.7
    expect(s.pct).toBeCloseTo(66.67, 1);
  });

  it("insufficient_data is a short, dashed, non-zero, pending spoke", () => {
    const s = axisState(verdict({ model: "beneish", aggregate_value: null, applicability: "computed" }));
    expect(s.dashed).toBe(true);
    expect(s.tone).toBe("pending");
    expect(s.label).toBe("Insufficient data");
    expect(s.pct).toBeGreaterThan(0);
  });

  it("excluded_out_of_scope is a short, dashed, non-zero, excluded spoke", () => {
    const s = axisState(verdict({ model: "altman", applicability: "excluded_out_of_scope" }));
    expect(s.dashed).toBe(true);
    expect(s.tone).toBe("excluded");
    expect(s.pct).toBeGreaterThan(0);
  });

  it("computed_with_caveat keeps the REAL position and REAL band tone — only the label says Caveat", () => {
    // A real, non-trivial value and a real (failing) band, exactly like the
    // Gauge on the detail card would render for the same VerdictItem.
    const s = axisState(
      verdict({ model: "altman", aggregate_value: 1.2, band_label: "Distress", applicability: "computed_with_caveat" }),
    );
    expect(s.dashed).toBe(false);
    expect(s.label).toBe("Caveat");
    expect(s.tone).toBe("fail"); // bandTone("Distress"), NOT a caveat-specific tone
    // domainPct(altman=[0.5,4.5], 1.2) = (1.2-0.5)/4 * 100 = 17.5
    expect(s.pct).toBeCloseTo(17.5, 1);
  });

  it("never produces a zero-length spoke for any absence state", () => {
    const insufficient = axisState(verdict({ model: "sloan", aggregate_value: null }));
    const excluded = axisState(verdict({ model: "altman", applicability: "excluded_out_of_scope" }));
    expect(insufficient.pct).not.toBe(0);
    expect(excluded.pct).not.toBe(0);
  });

  it("lets no value take precedence over a caveat", () => {
    const s = axisState(
      verdict({ model: "altman", aggregate_value: null, applicability: "computed_with_caveat" }),
    );
    expect(s.label).toBe("Insufficient data");
    expect(s.tone).toBe("pending");
    expect(s.dashed).toBe(true);
  });

  it("uses the Gauge fallback domain for an unknown model key", () => {
    const s = axisState(verdict({ model: "future-model", aggregate_value: 3, band_label: null }));
    expect(s.pct).toBe(50);
    expect(s.tone).toBe("neutral");
  });

  it("treats a non-finite value as unavailable rather than drawing NaN geometry", () => {
    const s = axisState(verdict({ model: "piotroski", aggregate_value: Number.NaN }));
    expect(s.label).toBe("Insufficient data");
    expect(s.tone).toBe("pending");
    expect(s.dashed).toBe(true);
  });

  it("falls back to a neutral tone for a computed value with no band label at all", () => {
    const s = axisState(verdict({ model: "sloan", aggregate_value: 0.01, band_label: null }));
    expect(s.dashed).toBe(false);
    expect(s.tone).toBe("neutral");
    expect(s.label).toBe("0.01");
  });
});
