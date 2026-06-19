// Unit tests for ui/lib/combined.js — the pure data layer behind the merged
// long-term-context chart (#288): F&G + normalized 5s10s on a 0-100 axis and
// SPY indexed on a log axis, reconciled onto one monthly grid. Pure functions;
// the Chart.js render lives in ui/charts.js.
import { describe, it, expect } from "vitest";
import { normalizeSlope, aggregateMonthly, buildCombinedSeries } from "../lib/combined.js";

describe("normalizeSlope", () => {
  it("maps the band midpoint to 50", () => {
    expect(normalizeSlope(0.5, -2, 3)).toBeCloseTo(50, 9);
  });

  it("maps the band endpoints to 0 and 100", () => {
    expect(normalizeSlope(-2, -2, 3)).toBe(0);
    expect(normalizeSlope(3, -2, 3)).toBe(100);
  });

  it("clamps values outside the band", () => {
    expect(normalizeSlope(-5, -2, 3)).toBe(0);
    expect(normalizeSlope(10, -2, 3)).toBe(100);
  });
});

describe("aggregateMonthly", () => {
  const rows = [
    { date: "2011-01-05", v: 1 },
    { date: "2011-01-20", v: 3 },
    { date: "2011-02-10", v: 10 },
  ];

  it("means values per UTC month", () => {
    const out = aggregateMonthly(rows, { dateKey: "date", valueKey: "v", reduce: "mean" });
    expect(out.months).toEqual(["2011-01", "2011-02"]);
    expect(out.values).toEqual([2, 10]);
  });

  it("takes the latest value in the month for reduce=last", () => {
    const out = aggregateMonthly(rows, { dateKey: "date", valueKey: "v", reduce: "last" });
    expect(out.months).toEqual(["2011-01", "2011-02"]);
    expect(out.values).toEqual([3, 10]); // Jan -> 2011-01-20 value
  });

  it("sorts months ascending regardless of input order", () => {
    const unsorted = [
      { date: "2011-03-01", v: 5 },
      { date: "2011-01-01", v: 1 },
      { date: "2011-02-01", v: 3 },
    ];
    const out = aggregateMonthly(unsorted, { dateKey: "date", valueKey: "v", reduce: "mean" });
    expect(out.months).toEqual(["2011-01", "2011-02", "2011-03"]);
    expect(out.values).toEqual([1, 3, 5]);
  });

  it("skips null/non-numeric values and unparseable dates", () => {
    const dirty = [
      { date: "2011-01-05", v: 4 },
      { date: "2011-01-06", v: null },
      { date: "not-a-date", v: 9 },
    ];
    const out = aggregateMonthly(dirty, { dateKey: "date", valueKey: "v", reduce: "mean" });
    expect(out.months).toEqual(["2011-01"]);
    expect(out.values).toEqual([4]);
  });
});

describe("buildCombinedSeries", () => {
  it("reconciles the three series onto the union of months with null gaps", () => {
    const fg = [
      { timestamp: "2011-01-15T00:00:00Z", score: 40 },
      { timestamp: "2011-02-15T00:00:00Z", score: 60 },
    ];
    const yc = [
      { date: "2011-02-10", slope_5s10s: 0.5 }, // only Feb
    ];
    const spy = [
      { date: "2011-01-31", ret_indexed: 100 },
      { date: "2011-03-31", ret_indexed: 130 }, // only Jan + Mar
    ];

    const out = buildCombinedSeries(fg, yc, spy, { slopeLo: -2, slopeHi: 3 });

    expect(out.labels).toEqual(["2011-01", "2011-02", "2011-03"]);
    // F&G median present Jan+Feb, null Mar
    expect(out.fgMedian).toEqual([40, 60, null]);
    // 5s10s only Feb; normalized: (0.5+2)/5*100 = 50
    expect(out.slopeNorm[0]).toBeNull();
    expect(out.slopeNorm[1]).toBeCloseTo(50, 9);
    expect(out.slopeNorm[2]).toBeNull();
    // SPY Jan + Mar, null Feb
    expect(out.spyIndexed).toEqual([100, null, 130]);
  });

  it("returns empty arrays when all series are empty", () => {
    const out = buildCombinedSeries([], [], [], { slopeLo: -2, slopeHi: 3 });
    expect(out.labels).toEqual([]);
    expect(out.fgMedian).toEqual([]);
    expect(out.slopeNorm).toEqual([]);
    expect(out.spyIndexed).toEqual([]);
  });
});
