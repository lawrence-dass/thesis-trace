import { describe, expect, it } from "vitest";

import { isBackdated, newestVerdictYear, verdictYearLabel } from "./verdictYear";

describe("verdict year", () => {
  // QSR after Ops 5: Beneish's latest year with a value is FY2020; the rest FY2025.
  const qsr = [
    { model: "beneish", fiscal_year: 2020 },
    { model: "sloan", fiscal_year: 2025 },
    { model: "altman", fiscal_year: 2025 },
    { model: "piotroski", fiscal_year: 2025 },
  ];

  it("takes the newest year across the company's verdicts", () => {
    expect(newestVerdictYear(qsr)).toBe(2025);
    expect(newestVerdictYear([])).toBeNull();
  });

  it("says a lagging verdict is backdated, and why", () => {
    expect(verdictYearLabel(2020, 2025)).toBe("FY2020 · later years insufficient");
    expect(isBackdated(2020, 2025)).toBe(true);
  });

  it("states a current verdict's year plainly", () => {
    expect(verdictYearLabel(2025, 2025)).toBe("FY2025");
    expect(isBackdated(2025, 2025)).toBe(false);
    expect(verdictYearLabel(2025, null)).toBe("FY2025");
  });
});
