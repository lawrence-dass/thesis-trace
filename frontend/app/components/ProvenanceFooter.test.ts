import { describe, expect, it } from "vitest";
import { formatDateTime } from "./ProvenanceFooter";

describe("formatDateTime", () => {
  it("formats a real ISO timestamp", () => {
    const formatted = formatDateTime("2026-08-27T06:00:00Z");
    // Exact wording is locale/timezone-dependent; assert it actually parsed
    // rather than falling through to the raw-string guard.
    expect(formatted).toContain("2026");
    expect(formatted).not.toBe("2026-08-27T06:00:00Z");
  });

  it("falls back to the raw string rather than printing 'Invalid Date'", () => {
    expect(formatDateTime("not-a-date")).toBe("not-a-date");
  });
});
