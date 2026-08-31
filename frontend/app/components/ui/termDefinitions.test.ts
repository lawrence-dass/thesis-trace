// Enforces Story 11.5's closing bar: every sub-signal key already listed in
// page.tsx's real SIGNAL_LABEL map has a real, non-placeholder definition.
// Checked against the LIVE map (imported, not hand-copied) so a future key
// added to SIGNAL_LABEL without a matching definition fails loudly here
// rather than silently shipping an undefined Term lookup — same shape as
// the piotroski_v1.yaml declared-inputs-vs-actual-code-reads guard.
import { describe, expect, it } from "vitest";
import { SIGNAL_LABEL } from "../../company/[ticker]/page";
import { TERM_DEFINITIONS } from "./termDefinitions";

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
});
