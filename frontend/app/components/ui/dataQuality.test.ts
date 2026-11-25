import { describe, expect, it } from "vitest";
import { describeIssue, describeIssues, exactValue } from "./dataQuality";

// Detail shapes copied from real dev-store rows (2026-11-25), not invented.
const aaplEquity2007 = {
  issue_type: "ambiguous_selection",
  status: "needs_review",
  raised_by: "canonicalization",
  detail: { values: ["14531000000.000000", "14532000000.000000"], fiscal_year: 2007, canonical_concept: "stockholders_equity" },
};
const otexParValue = {
  issue_type: "source_conflict",
  status: "needs_review",
  raised_by: "ingestion",
  detail: {
    unit: "USD/shares",
    concept: "EntityListingParValuePerShare",
    taxonomy: "dei",
    period_end: "2023-06-30",
    resolution: "Company Facts wins (AD-4); the Inline XBRL value was not written.",
    period_start: "2022-07-01",
    inline_xbrl_value: 0.00000625,
    company_facts_value: 0.000006,
  },
};

describe("exactValue (AC 4)", () => {
  it("keeps a 1M difference on a 14.5B figure visible — compactAmount shows both as 14.53B", () => {
    expect(exactValue("14531000000.000000")).toBe("14,531,000,000");
    expect(exactValue("14532000000.000000")).toBe("14,532,000,000");
  });

  it("keeps a par value's digits — toLocaleString's default shows both as 0", () => {
    expect(exactValue(0.000006)).toBe("0.000006");
    expect(exactValue(0.00000625)).toBe("0.00000625");
  });

  it("formats decimal strings as text: no float rounding, sign kept, trailing zeros only trimmed", () => {
    expect(exactValue("-6895000.000000")).toBe("-6,895,000");
    expect(exactValue("12345678901234567.125000")).toBe("12,345,678,901,234,567.125");
    expect(exactValue("not a number")).toBe("not a number");
  });
});

describe("describeIssue (AC 3, 6)", () => {
  it("an ambiguous selection names its fiscal year, concept and both candidates", () => {
    const d = describeIssue(aaplEquity2007);
    expect(d.when).toBe("FY2007");
    expect(d.concept).toBe("stockholders_equity");
    expect(d.values).toEqual(["14,531,000,000", "14,532,000,000"]);
    expect(d.label).toBe("Ambiguous source selection");
    expect(d.meta).toBe("needs_review, raised by canonicalization");
  });

  it("a source conflict names its period, taxonomy-qualified concept, each source's value and the resolution", () => {
    const d = describeIssue(otexParValue);
    expect(d.when).toBe("period ending 2023-06-30");
    expect(d.concept).toBe("dei:EntityListingParValuePerShare");
    expect(d.values).toEqual(["Company Facts 0.000006", "Inline XBRL 0.00000625"]);
    expect(d.resolution).toMatch(/Company Facts wins/);
    expect(d.sortYear).toBe(2023);
  });

  it("an unmapped member names the concept and the member as filed", () => {
    const d = describeIssue({
      issue_type: "unmapped_member",
      status: "needs_review",
      raised_by: "canonicalization",
      detail: { taxonomy: "us-gaap", source_concept: "Revenues", member_as_filed: "cpb:SnacksMember", fiscal_year: 2025 },
    });
    expect(d.concept).toBe("us-gaap:Revenues");
    expect(d.member).toBe("cpb:SnacksMember");
    expect(d.when).toBe("FY2025");
  });

  it("an unrecognised or missing detail still renders the old line, never blank (AC 6)", () => {
    for (const detail of [null, undefined, {}, { something: "new" }]) {
      const d = describeIssue({ issue_type: "brand_new_type", status: "needs_review", raised_by: "x", detail });
      expect(d.label).toBe("brand_new_type");
      expect(d.meta).toBe("needs_review, raised by x");
      expect(d.when).toBeNull();
      expect(d.concept).toBeNull();
      expect(d.values).toEqual([]);
    }
  });
});

describe("describeIssues (AC 5)", () => {
  it("orders newest year first, keeps API order within a year, and puts year-less warnings last", () => {
    const mk = (fy: number | null, c: string) => ({
      issue_type: "ambiguous_selection",
      status: "needs_review",
      raised_by: "canonicalization",
      detail: fy == null ? { canonical_concept: c } : { fiscal_year: fy, canonical_concept: c },
    });
    const out = describeIssues([mk(2008, "a"), mk(null, "z"), mk(2024, "b"), mk(2008, "c"), otexParValue]);
    expect(out.map((d) => d.concept)).toEqual(["b", "dei:EntityListingParValuePerShare", "a", "c", "z"]);
  });
});
