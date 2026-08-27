import { describe, expect, it } from "vitest";
import { factChangeKey, type FactChange } from "./WhatChanged";

/** Story 10.7. A real duplicate-React-key defect found live on CP and SHOP:
 *  `signal_key`+`canonical_concept` alone is not unique — a signal reading
 *  the same concept across two comparison years produces two genuinely
 *  distinct fact changes sharing that pair. Pins the fix using the exact
 *  live SHOP payload that reproduced it.
 */

function factChange(overrides: Partial<FactChange>): FactChange {
  return {
    kind: "fact_change",
    signal_key: "leverage_decreasing",
    canonical_concept: "long_term_debt",
    prior_value: null,
    current_value: 0,
    prior_provenance: null,
    current_provenance: null,
    ...overrides,
  };
}

describe("factChangeKey", () => {
  it("disambiguates two real fact changes sharing signal_key and canonical_concept (SHOP, live)", () => {
    const a = factChange({
      current_value: 916000000,
      current_provenance: {
        accession_number: "0001594805-25-000012",
        canonical_concept: "long_term_debt",
        fiscal_year: 2023,
      },
    });
    const b = factChange({
      current_value: 0,
      current_provenance: {
        accession_number: "0001594805-25-000012",
        canonical_concept: "long_term_debt",
        fiscal_year: 2024,
      },
    });
    expect(factChangeKey(a, 0)).not.toBe(factChangeKey(b, 1));
  });

  it("falls back to prior_provenance's fiscal year when current_provenance is absent", () => {
    const change = factChange({
      current_provenance: null,
      prior_provenance: {
        accession_number: "0001",
        canonical_concept: "long_term_debt",
        fiscal_year: 2021,
      },
    });
    expect(factChangeKey(change, 0)).toBe("leverage_decreasing-long_term_debt-2021");
  });

  it("falls back to the array index when neither endpoint carries a fiscal year", () => {
    const change = factChange({ current_provenance: null, prior_provenance: null });
    expect(factChangeKey(change, 3)).toBe("leverage_decreasing-long_term_debt-3");
  });
});
