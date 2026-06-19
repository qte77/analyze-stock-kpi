// Unit tests for ui/lib/weekly.js — ISO-week aggregation of a daily numeric
// series (the 5s10s yield-curve slope) for the long-term-context section.
// Pure function: input rows with a date + numeric field, output parallel
// arrays of ISO week / mean / count, sorted ascending by week.
import { describe, it, expect } from "vitest";
import { aggregateWeekly } from "../lib/weekly.js";

describe("aggregateWeekly", () => {
  it("returns empty arrays for an empty input list", () => {
    const out = aggregateWeekly([]);
    expect(out.weeks).toEqual([]);
    expect(out.mean).toEqual([]);
    expect(out.count).toEqual([]);
  });

  it("buckets entries in the same ISO week into one row with the mean", () => {
    // 2025-06-02 (Mon) … 2025-06-08 (Sun) are ISO week 2025-W23.
    const out = aggregateWeekly([
      { date: "2025-06-02", slope_5s10s: 0.2 },
      { date: "2025-06-05", slope_5s10s: 0.4 },
    ]);
    expect(out.weeks).toEqual(["2025-W23"]);
    expect(out.mean[0]).toBeCloseTo(0.3, 10);
    expect(out.count).toEqual([2]);
  });

  it("separates entries that fall in adjacent ISO weeks (Sun vs Mon)", () => {
    // 2025-06-08 is Sunday (W23); 2025-06-09 is Monday (W24).
    const out = aggregateWeekly([
      { date: "2025-06-08", slope_5s10s: 1 },
      { date: "2025-06-09", slope_5s10s: 3 },
    ]);
    expect(out.weeks).toEqual(["2025-W23", "2025-W24"]);
    expect(out.count).toEqual([1, 1]);
  });

  it("sorts output weeks ascending regardless of input order", () => {
    const out = aggregateWeekly([
      { date: "2025-06-16", slope_5s10s: 5 }, // W25
      { date: "2025-06-02", slope_5s10s: 1 }, // W23
      { date: "2025-06-09", slope_5s10s: 3 }, // W24
    ]);
    expect(out.weeks).toEqual(["2025-W23", "2025-W24", "2025-W25"]);
    expect(out.mean).toEqual([1, 3, 5]);
  });

  it("uses the ISO week-year at the Jan boundary (2021-01-01 → 2020-W53)", () => {
    const out = aggregateWeekly([{ date: "2021-01-01", slope_5s10s: 0.5 }]);
    expect(out.weeks).toEqual(["2020-W53"]);
  });

  it("rolls a late-December date into the next year's W01 (2024-12-30 → 2025-W01)", () => {
    const out = aggregateWeekly([
      { date: "2024-12-30", slope_5s10s: 0.1 },
      { date: "2025-01-02", slope_5s10s: 0.3 },
    ]);
    expect(out.weeks).toEqual(["2025-W01"]);
    expect(out.count).toEqual([2]);
  });

  it("skips null / non-numeric values and unparseable dates", () => {
    const out = aggregateWeekly([
      { date: "2025-06-02", slope_5s10s: 0.2 },
      { date: "2025-06-03", slope_5s10s: null },
      { date: "not-a-date", slope_5s10s: 0.9 },
    ]);
    expect(out.weeks).toEqual(["2025-W23"]);
    expect(out.mean).toEqual([0.2]);
    expect(out.count).toEqual([1]);
  });

  it("supports configurable date/value fields via opts", () => {
    const out = aggregateWeekly(
      [
        { ts: "2025-06-02", v: 10 },
        { ts: "2025-06-05", v: 20 },
      ],
      { dateKey: "ts", valueKey: "v" },
    );
    expect(out.weeks).toEqual(["2025-W23"]);
    expect(out.mean).toEqual([15]);
  });
});
