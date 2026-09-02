/** @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { VerdictItem } from "../components/VerdictGlyph";
import { cellKey, VerdictCell } from "./page";

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

describe("cellKey", () => {
  it("treats applicability as part of a comparison state", () => {
    const computed = cellKey(verdict());
    const caveated = cellKey(verdict({ applicability: "computed_with_caveat" }));

    expect(computed).not.toBe(caveated);
  });

  it("distinguishes different missing-signal states", () => {
    const missingGrossMargin = cellKey(
      verdict({ aggregate_value: null, band_label: null, missing_signals: ["gmi"] }),
    );
    const missingSgai = cellKey(
      verdict({ aggregate_value: null, band_label: null, missing_signals: ["sgai"] }),
    );

    expect(missingGrossMargin).not.toBe(missingSgai);
  });
});

describe("VerdictCell", () => {
  it("keeps a valid caveated score visible and exposes its reason through an accessible disclosure", () => {
    const reason = "The gross margin is an approximation rather than a reported figure.";
    const { container } = render(
      <VerdictCell
        verdict={verdict({ applicability: "computed_with_caveat", caveat_reason: reason })}
      />,
    );

    expect(screen.getByText("No manipulation flag")).toBeTruthy();
    expect(screen.getByText("Caveat", { exact: true })).toBeTruthy();
    const details = container.querySelector("details");
    expect(details).not.toBeNull();
    expect(details?.open).toBe(false);

    fireEvent.click(details!.querySelector("summary")!);
    expect(details?.open).toBe(true);
    expect(screen.getByText(reason)).toBeTruthy();
  });

  it("preserves insufficient data and missing signals when a caveat also applies", () => {
    const { container } = render(
      <VerdictCell
        verdict={
          verdict({
            aggregate_value: null,
            band_label: null,
            applicability: "computed_with_caveat",
            missing_signals: ["gmi"],
            caveat_reason: "A structural caveat still applies.",
          })
        }
      />,
    );

    expect(screen.getByText("Insufficient data")).toBeTruthy();
    expect(screen.getByText("Missing: Gross Margin")).toBeTruthy();
    expect(container.querySelector("details")).not.toBeNull();
  });

  it("shows an honest fallback for legacy or malformed missing reasons", () => {
    render(<VerdictCell verdict={verdict({ applicability: "computed_with_caveat", caveat_reason: "   " })} />);

    expect(screen.getByText("Reason unavailable for this stored run.")).toBeTruthy();
  });
});
