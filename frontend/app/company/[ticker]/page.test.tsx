/** @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CompactVerdictCard } from "./page";
import type { VerdictItem } from "../../components/VerdictGlyph";

afterEach(cleanup);

function verdict(overrides: Partial<VerdictItem> = {}): VerdictItem {
  return {
    model: "beneish",
    category: "integrity",
    fiscal_year: 2025,
    aggregate_value: -2.5,
    band_label: "No manipulation flag",
    applicability: "computed",
    missing_signals: [],
    caveat_reason: null,
    ...overrides,
  };
}

describe("CompactVerdictCard", () => {
  it("renders the actual caveat reason on a valid computed score", () => {
    render(
      <CompactVerdictCard
        verdict={verdict({
          applicability: "computed_with_caveat",
          caveat_reason: "The gross margin is an approximation rather than a reported figure.",
        })}
        bands={[]}
      />,
    );

    expect(screen.getByText("-2.5")).toBeTruthy();
    expect(screen.getByText(/Caveat:/)).toBeTruthy();
    expect(screen.getByText("The gross margin is an approximation rather than a reported figure.")).toBeTruthy();
  });

  it("renders missing data and an explicit fallback for a legacy caveated run", () => {
    render(
      <CompactVerdictCard
        verdict={
          verdict({
            aggregate_value: null,
            band_label: null,
            applicability: "computed_with_caveat",
            missing_signals: ["gmi"],
            caveat_reason: null,
          })
        }
        bands={[]}
      />,
    );

    expect(screen.getByText("Insufficient data")).toBeTruthy();
    expect(screen.getByText("Missing: Gross Margin")).toBeTruthy();
    expect(screen.getByText("Reason unavailable for this stored run.")).toBeTruthy();
  });
});
