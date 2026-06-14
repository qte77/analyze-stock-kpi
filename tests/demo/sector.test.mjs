// Unit tests for ui/lib/sector.js — sector aggregation for the
// donut (B3). Non-trivial cases only: ordering contract (desc by count,
// alphabetical tiebreak), null-sector bucketing, empty input.
import { describe, it, expect } from "vitest";
import { aggregateSectors, sectorColor } from "../../ui/lib/sector.js";

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
    const map = aggregateSectors([{ sector: null }, { sector: undefined }, { sector: "Tech" }]);
    expect(map.get("—")).toBe(2);
    expect(map.get("Tech")).toBe(1);
  });
});

describe("sectorColor", () => {
  it("returns a 7-char hex string for a known GICS sector", () => {
    const c = sectorColor("Technology");
    expect(c).toMatch(/^#[0-9A-Fa-f]{6}$/);
  });

  it("is deterministic — same input always returns the same color", () => {
    expect(sectorColor("Healthcare")).toBe(sectorColor("Healthcare"));
  });

  it("returns different colors for two different known sectors so slices are distinguishable", () => {
    expect(sectorColor("Technology")).not.toBe(sectorColor("Healthcare"));
  });

  it("maps the '—' null bucket to a neutral grey so empty sectors stay visually subdued", () => {
    expect(sectorColor("—")).toBe("#98989D");
  });

  it("falls back to the neutral grey for unknown sectors instead of returning null", () => {
    expect(sectorColor("Definitely Not A GICS Sector")).toBe("#98989D");
  });
});
