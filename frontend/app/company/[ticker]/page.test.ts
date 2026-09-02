import { describe, expect, it } from "vitest";
import { caveatReasonText } from "../../components/CaveatReason";
import { sectionFreshness, showsCaveatReason } from "./page";

/** Story 10.5. `sectionFreshness` computes each report section's own "latest
 *  score run and filing date it reflects" (the AC's freshness requirement)
 *  purely from data already on the wire — no new query. Pinning the two
 *  rules that make it correct: it takes the MAX across everything passed in
 *  (not the first or last item), and an absent period_end never wins over a
 *  present one.
 */

function lens(fiscalYear: number, periodEnds: (string | null)[] = []) {
  return {
    model: "piotroski",
    category: "quality_health",
    fiscal_year: fiscalYear,
    aggregate_value: 5,
    band_label: "Middle",
    applicability: "computed",
    caveat_reason: null,
    signals: [
      {
        signal_key: "x",
        status: "pass",
        value: 1,
        provenance: periodEnds.map((period_end) => ({
          accession_number: "0001",
          canonical_concept: "revenue",
          fiscal_year: fiscalYear,
          period_end,
        })),
      },
    ],
  };
}

describe("sectionFreshness", () => {
  it("returns nulls for an empty section", () => {
    expect(sectionFreshness([])).toEqual({ fiscalYear: null, periodEnd: null });
  });

  it("takes the MAX fiscal year across every lens, not the first or last", () => {
    const result = sectionFreshness([lens(2019), lens(2025), lens(2022)]);
    expect(result.fiscalYear).toBe(2025);
  });

  it("takes the latest period_end across every signal's provenance", () => {
    const result = sectionFreshness([
      lens(2024, ["2024-06-30"]),
      lens(2025, ["2025-03-31", "2025-12-31"]),
    ]);
    expect(result.periodEnd).toBe("2025-12-31");
  });

  it("never lets a missing period_end suppress a real one already found", () => {
    const result = sectionFreshness([lens(2025, [null]), lens(2024, ["2024-12-31"])]);
    expect(result.periodEnd).toBe("2024-12-31");
  });

  it("returns a null period_end when nothing in the section carries one", () => {
    const result = sectionFreshness([lens(2025, [null, null])]);
    expect(result.fiscalYear).toBe(2025);
    expect(result.periodEnd).toBeNull();
  });
});

describe("showsCaveatReason", () => {
  it("shows the box when computed_with_caveat carries a reason", () => {
    expect(showsCaveatReason({ applicability: "computed_with_caveat", caveat_reason: "reason" })).toBe(true);
  });

  it("keeps the caveat section visible when a legacy run has no stored reason", () => {
    expect(showsCaveatReason({ applicability: "computed_with_caveat", caveat_reason: null })).toBe(true);
  });

  it("keeps the caveat section visible when the stored reason is whitespace", () => {
    expect(showsCaveatReason({ applicability: "computed_with_caveat", caveat_reason: "   " })).toBe(true);
  });

  it("hides the box for a plain computed run even if caveat_reason were somehow set", () => {
    expect(showsCaveatReason({ applicability: "computed", caveat_reason: "reason" })).toBe(false);
  });

  it("hides the box for excluded_out_of_scope", () => {
    expect(showsCaveatReason({ applicability: "excluded_out_of_scope", caveat_reason: null })).toBe(false);
  });

  it("is independent of aggregate_value/missing_signals — a model can show both at once (SU FY2025 Beneish/Altman)", () => {
    expect(
      showsCaveatReason({ applicability: "computed_with_caveat", caveat_reason: "structural caveat" }),
    ).toBe(true);
  });
});

describe("caveatReasonText", () => {
  it("does not render an empty explanation for legacy or malformed values", () => {
    expect(caveatReasonText(null)).toBe("Reason unavailable for this stored run.");
    expect(caveatReasonText("   ")).toBe("Reason unavailable for this stored run.");
  });

  it("trims a real reason before displaying it", () => {
    expect(caveatReasonText("  structural caveat  ")).toBe("structural caveat");
  });
});
