import { describe, expect, it } from "vitest";
import { formatScore } from "./scoreFormat";
import type { BandClass } from "./Gauge";
import vectors from "./scoreFormat.vectors.json";

// The cases live in scoreFormat.vectors.json, which the backend's
// test_score_format.py runs against its Python twin (Ops 6b). A case added
// here is therefore a case both formatters must pass.
const bands = vectors.bands as Record<string, BandClass[]>;

describe("formatScore", () => {
  it("has cases to run", () => {
    expect(vectors.cases.length).toBeGreaterThan(15);
  });

  it.each(vectors.cases)("$model $value -> $expected ($why)", ({ model, value, bands: key, expected }) => {
    expect(formatScore(model, value, bands[key])).toBe(expected);
  });
});
