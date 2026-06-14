// Unit tests for ui/lib/overlay.js — multi-universe snapshot
// merge. Non-trivial cases only: silent fault tolerance (universe whose
// fetch failed isn't in the input), per-row `_universe` annotation,
// preserved insertion order across universes.
import { describe, it, expect } from "vitest";
import { mergeUniverseSnapshots } from "../../ui/lib/overlay.js";

describe("mergeUniverseSnapshots", () => {
  it("returns an empty array when no universes are provided", () => {
    expect(mergeUniverseSnapshots({})).toEqual([]);
  });

  it("returns an empty array when every universe failed (all null/undefined values)", () => {
    expect(mergeUniverseSnapshots({ sp500: null, eurostoxx: undefined })).toEqual([]);
  });

  it("annotates each row with its source universe id under the `_universe` key", () => {
    const merged = mergeUniverseSnapshots({
      sp500: [{ symbol: "AAPL" }, { symbol: "MSFT" }],
    });
    expect(merged).toEqual([
      { symbol: "AAPL", _universe: "sp500" },
      { symbol: "MSFT", _universe: "sp500" },
    ]);
  });

  it("concatenates rows from multiple universes preserving each universe's order", () => {
    const merged = mergeUniverseSnapshots({
      sp500: [{ symbol: "AAPL" }],
      eurostoxx: [{ symbol: "ASML.AS" }, { symbol: "SAP.DE" }],
    });
    // sp500 rows first because the input-object property order is sp500, eurostoxx
    expect(merged.map((r) => r.symbol)).toEqual(["AAPL", "ASML.AS", "SAP.DE"]);
    expect(merged.every((r) => typeof r._universe === "string")).toBe(true);
  });

  it("skips universes whose value is not an array (failed fetch path)", () => {
    const merged = mergeUniverseSnapshots({
      sp500: [{ symbol: "AAPL" }],
      eurostoxx: null,
      japan: undefined,
      "south-korea": [{ symbol: "005930.KS" }],
    });
    expect(merged.map((r) => r._universe)).toEqual(["sp500", "south-korea"]);
  });

  it("does not mutate the input row objects (returns shallow copies)", () => {
    const original = { symbol: "AAPL" };
    const merged = mergeUniverseSnapshots({ sp500: [original] });
    expect(original).not.toHaveProperty("_universe");
    expect(merged[0]._universe).toBe("sp500");
  });
});
