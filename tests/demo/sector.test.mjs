// Unit tests for docs/demo/lib/sector.js — sector aggregation for the
// donut (B3). Non-trivial cases only: ordering contract (desc by count,
// alphabetical tiebreak), null-sector bucketing, empty input.
import { describe, it, expect } from "vitest";
import { aggregateSectors } from "../../docs/demo/lib/sector.js";

describe("aggregateSectors", () => {
  it("returns an empty Map for an empty input list", () => {
    expect(aggregateSectors([]).size).toBe(0);
  });

  it("sorts segments descending by count so the donut's largest slice is first", () => {
    const map = aggregateSectors([
      { sector: "Health" },
      { sector: "Tech" },
      { sector: "Tech" },
      { sector: "Health" },
      { sector: "Tech" },
    ]);
    expect([...map.entries()]).toEqual([
      ["Tech", 3],
      ["Health", 2],
    ]);
  });

  it("breaks count ties alphabetically so renders stay deterministic across reloads", () => {
    const map = aggregateSectors([
      { sector: "Tech" },
      { sector: "Health" },
      { sector: "Tech" },
      { sector: "Health" },
    ]);
    expect([...map.keys()]).toEqual(["Health", "Tech"]);
  });

  it("buckets null and undefined sectors into the '—' segment (no silent drop)", () => {
    const map = aggregateSectors([
      { sector: null },
      { sector: undefined },
      { sector: "Tech" },
    ]);
    expect(map.get("—")).toBe(2);
    expect(map.get("Tech")).toBe(1);
  });
});
