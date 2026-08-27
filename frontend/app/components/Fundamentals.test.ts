import { describe, expect, it } from "vitest";
import { waterfallSegments, type WaterfallBar } from "./Fundamentals";

/** Story 10.4. `waterfallSegments` is the one piece of frontend logic in this
 *  card — everything else is presentation of API-supplied values (AD-8) — so
 *  it is the one thing worth pinning here. The API always sends all five
 *  bars in stage order; these fixtures mirror that.
 */

function figure(value: number | null, reason: string | null = null): WaterfallBar["figure"] {
  return { value, provenance: null, reason, as_of: null, source: null };
}

describe("waterfallSegments", () => {
  it("closes a full-coverage waterfall on the earnings figure", () => {
    const bars: WaterfallBar[] = [
      { stage: "revenue", bar_type: "total", figure: figure(1000) },
      { stage: "cost_of_revenue", bar_type: "decrease", figure: figure(400) },
      { stage: "gross_profit", bar_type: "total", figure: figure(600) },
      { stage: "other", bar_type: "decrease", figure: figure(450) },
      { stage: "earnings", bar_type: "total", figure: figure(150) },
    ];
    const segments = waterfallSegments(bars);
    expect(segments.map((s) => [s.top, s.bottom])).toEqual([
      [1000, 0], // revenue
      [1000, 600], // cost of revenue, floating
      [600, 0], // gross profit
      [600, 150], // other, floating
      [150, 0], // earnings
    ]);
    expect(segments.every((s) => s.present)).toBe(true);
  });

  it("skips an absent bar without moving the running total (never a zero bar)", () => {
    // CP's shape: no cost-of-revenue or gross-profit tag at all.
    const bars: WaterfallBar[] = [
      { stage: "revenue", bar_type: "total", figure: figure(15078) },
      { stage: "cost_of_revenue", bar_type: "decrease", figure: figure(null, "Not disclosed") },
      { stage: "gross_profit", bar_type: "total", figure: figure(null, "Not disclosed") },
      { stage: "other", bar_type: "decrease", figure: figure(15078 - 4141) },
      { stage: "earnings", bar_type: "total", figure: figure(4141) },
    ];
    const segments = waterfallSegments(bars);

    const cost = segments.find((s) => s.stage === "cost_of_revenue")!;
    expect(cost.present).toBe(false);
    expect(cost.reason).toBe("Not disclosed");

    const grossProfit = segments.find((s) => s.stage === "gross_profit")!;
    expect(grossProfit.present).toBe(false);

    // "Other" floats from revenue's own running total (15078), NOT from a
    // stale zero left by the two skipped bars, straight down to earnings.
    const other = segments.find((s) => s.stage === "other")!;
    expect(other.top).toBe(15078);
    expect(other.bottom).toBe(4141);

    const earnings = segments.find((s) => s.stage === "earnings")!;
    expect(earnings.top).toBe(4141);
  });
});
