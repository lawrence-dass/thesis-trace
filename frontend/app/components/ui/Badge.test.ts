import { describe, expect, it } from "vitest";
import { bandTone } from "./Badge";

/** `bandTone` colors a backend-authored band label. It classifies nothing — the
 *  string is already fixed by `backend/formulas/specs/*.yaml` — so the only way
 *  it can be wrong is by failing to recognise a label, or by recognising the
 *  WRONG one via a substring collision.
 *
 *  A 2026-07-29 audit traced all ten labels through this function by hand and
 *  found them correct. Nothing recorded that, so the docstring above `bandTone`
 *  went on omitting Beneish for months while the code handled it — the same
 *  "documentation of a rule does not hold the rule" shape as the OTEX golden
 *  entry and `trajectory_v1.yaml`'s comment-not-field. This is the test.
 */
describe("bandTone", () => {
  // The ten labels the four models actually emit, quoted from their specs.
  it("maps every Piotroski band", () => {
    expect(bandTone("Strong")).toBe("pass");
    expect(bandTone("Middle")).toBe("caveat");
    expect(bandTone("Weak")).toBe("fail");
  });

  it("maps every Altman band", () => {
    expect(bandTone("Safe")).toBe("pass");
    expect(bandTone("Grey")).toBe("caveat");
    expect(bandTone("Distress")).toBe("fail");
  });

  it("maps every Beneish band", () => {
    // beneish_v1.yaml:65,67 — the pair this function's docstring omitted.
    expect(bandTone("No manipulation flag")).toBe("pass");
    expect(bandTone("Manipulation risk flagged")).toBe("fail");
  });

  it("maps every Sloan band", () => {
    // sloan_v1.yaml:36,38. Lower is better here: high accruals are the risk.
    expect(bandTone("Low accruals (higher quality)")).toBe("pass");
    expect(bandTone("High accruals (lower quality)")).toBe("fail");
  });

  // ── The two near-misses. Both hold on the SPECIFICITY of a single search
  // ── term, verified by mutation 2026-08-14 — each is one loosened string away
  // ── from inverting a result, and neither break fails any assertion above.

  it("keeps the two Beneish labels apart on 'no manipulation', not 'manipulation'", () => {
    // Both labels contain "manipulation", so the pass branch must match the
    // longer "no manipulation". Loosening it to bare "manipulation" makes
    // "Manipulation risk flagged" match pass FIRST and render a flagged
    // result green. (Reordering the two `if` blocks alone is harmless — it
    // only bites combined with a loosened fail term, so the term is the guard.)
    expect(bandTone("Manipulation risk flagged")).toBe("fail");
    expect(bandTone("Manipulation risk flagged")).not.toBe("pass");
    expect(bandTone("No manipulation flag")).toBe("pass");
  });

  it("keeps the two Sloan labels apart on 'low accrual', not 'low'", () => {
    // "High accruals (lower quality)" contains "low" inside "lower". Loosening
    // the pass term from "low accrual" to "low" turns the worst band green.
    expect(bandTone("High accruals (lower quality)")).toBe("fail");
    expect(bandTone("High accruals (lower quality)")).not.toBe("pass");
    expect(bandTone("Low accruals (higher quality)")).toBe("pass");
  });

  it("is case-insensitive, since the copy is authored upstream", () => {
    expect(bandTone("DISTRESS")).toBe("fail");
    expect(bandTone("safe")).toBe("pass");
  });

  it("falls back to neutral rather than guessing", () => {
    // A future model's band copy must not be forced into an existing tone.
    expect(bandTone(null)).toBe("neutral");
    expect(bandTone("")).toBe("neutral");
    expect(bandTone("Some future band")).toBe("neutral");
  });
});
