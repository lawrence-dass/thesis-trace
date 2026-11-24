import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { DERIVATION_LABEL } from "./CitationChip";

// Read from the backend's CURRENT spec, not a list typed here: a hand-written
// list would only compare this map with another declaration, and the same omission
// made in both would pass (project-context, 2026-10-07). Vitest runs from
// frontend/, so the backend sits one level up.
const SPECS = resolve(process.cwd(), "../backend/canonicalization/mappings/specs");

function currentDerivationRules(): string[] {
  const registry = readFileSync(resolve(SPECS, "registry.yaml"), "utf8");
  const version = registry.match(/^derivations:\s*(\S+)/m)?.[1];
  if (!version) throw new Error("registry.yaml names no derivations spec");
  const spec = readFileSync(resolve(SPECS, `${version}.yaml`), "utf8");
  return [...spec.matchAll(/^\s*- rule:\s*(\S+)/gm)].map((m) => m[1]);
}

describe("DERIVATION_LABEL", () => {
  it("labels every rule in the current derivations spec", () => {
    const rules = currentDerivationRules();
    expect(rules.length).toBeGreaterThanOrEqual(6); // the read must find the rules
    const missing = rules.filter((r) => !(r in DERIVATION_LABEL));
    expect(missing).toEqual([]);
  });

  it("describes SG&A as both of its parts", () => {
    expect(DERIVATION_LABEL.sga_general_plus_selling).toBe(
      "general & administrative + selling & marketing",
    );
  });
});
