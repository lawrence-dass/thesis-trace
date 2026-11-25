// Enforces Story 11.5's closing bar: every sub-signal key already listed in
// page.tsx's real SIGNAL_LABEL map has a real, non-placeholder definition.
// Checked against the LIVE map (imported, not hand-copied) so a future key
// added to SIGNAL_LABEL without a matching definition fails loudly here
// rather than silently shipping an undefined Term lookup — same shape as
// the piotroski_v1.yaml declared-inputs-vs-actual-code-reads guard.
import { describe, expect, it } from "vitest";
import { SIGNAL_LABEL } from "../../company/[ticker]/page";
import { TERM_DEFINITIONS } from "./termDefinitions";
import signalLabels from "../../lib/signalLabels.json";

describe("TERM_DEFINITIONS", () => {
  it("has a real definition for every key SIGNAL_LABEL currently declares", () => {
    for (const key of Object.keys(SIGNAL_LABEL)) {
      const definition = (TERM_DEFINITIONS as Record<string, string | undefined>)[key];
      expect(definition, `missing TERM_DEFINITIONS entry for SIGNAL_LABEL key "${key}"`).toBeTruthy();
      expect(definition!.length, `definition for "${key}" reads as a placeholder`).toBeGreaterThan(20);
    }
  });

  it("every definition is non-empty prose, not a placeholder stub", () => {
    for (const [key, definition] of Object.entries(TERM_DEFINITIONS)) {
      expect(definition, key).not.toMatch(/^(tbd|todo|placeholder|xxx)$/i);
      expect(definition.trim().length, key).toBeGreaterThan(0);
    }
  });

  // Piotroski's nine keys used to need a hand-copied list here because no
  // frontend map held them. Since Ops 6b, SIGNAL_LABEL carries every signal in
  // the four specs (the backend's test_signal_labels.py enforces that), so the
  // first test above covers them. This pins that they are really in it.
  it("SIGNAL_LABEL carries Piotroski's signals, so the first test covers them", () => {
    expect(Object.keys(SIGNAL_LABEL)).toEqual(expect.arrayContaining(["roa_positive", "asset_turnover_increasing"]));
  });

  it("both pages read the one shared map", () => {
    expect(SIGNAL_LABEL).toBe(signalLabels);
  });
});
