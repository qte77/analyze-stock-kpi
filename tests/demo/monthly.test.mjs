// Unit tests for ui/lib/monthly.js — monthly aggregation of CNN
// Fear & Greed daily entries for the long-term-context section. Pure
// function: input `{timestamp, score}[]`, output parallel arrays of
// month / median / avg / count, sorted ascending by month.
import { describe, it, expect } from "vitest";
import { aggregateMonthlyFG } from "../../ui/lib/monthly.js";

describe("aggregateMonthlyFG", () => {
  it("returns empty arrays for an empty input list", () => {
    const out = aggregateMonthlyFG([]);
    expect(out.months).toEqual([]);
    expect(out.median).toEqual([]);
    expect(out.avg).toEqual([]);
    expect(out.count).toEqual([]);
  });

  it("buckets multiple entries in the same month into one row with median + avg", () => {
    const out = aggregateMonthlyFG([
      { timestamp: "2025-06-02T00:00:00Z", score: 40 },
      { timestamp: "2025-06-15T00:00:00Z", score: 60 },
    ]);
    expect(out.months).toEqual(["2025-06"]);
    expect(out.avg).toEqual([50]);
    expect(out.median).toEqual([50]);
    expect(out.count).toEqual([2]);
  });

  it("computes median for odd counts as the middle value", () => {
    const out = aggregateMonthlyFG([
      { timestamp: "2025-06-01T00:00:00Z", score: 10 },
      { timestamp: "2025-06-02T00:00:00Z", score: 50 },
      { timestamp: "2025-06-03T00:00:00Z", score: 90 },
    ]);
    expect(out.median).toEqual([50]);
  });

  it("computes median for even counts as the mean of the two middle values", () => {
    const out = aggregateMonthlyFG([
      { timestamp: "2025-06-01T00:00:00Z", score: 10 },
      { timestamp: "2025-06-02T00:00:00Z", score: 40 },
      { timestamp: "2025-06-03T00:00:00Z", score: 60 },
      { timestamp: "2025-06-04T00:00:00Z", score: 90 },
    ]);
    expect(out.median).toEqual([50]);
  });

  it("sorts output months ascending regardless of input order", () => {
    const out = aggregateMonthlyFG([
      { timestamp: "2025-08-01T00:00:00Z", score: 70 },
      { timestamp: "2025-06-01T00:00:00Z", score: 30 },
      { timestamp: "2025-07-01T00:00:00Z", score: 50 },
    ]);
    expect(out.months).toEqual(["2025-06", "2025-07", "2025-08"]);
    expect(out.avg).toEqual([30, 50, 70]);
  });

  it("uses UTC date bucketing so a 23:59 UTC entry doesn't leak to the next month for non-UTC viewers", () => {
    const out = aggregateMonthlyFG([
      { timestamp: "2025-06-30T23:59:00Z", score: 40 },
      { timestamp: "2025-07-01T00:01:00Z", score: 60 },
    ]);
    expect(out.months).toEqual(["2025-06", "2025-07"]);
    expect(out.count).toEqual([1, 1]);
  });

  it("counts entries per month for downstream display", () => {
    const out = aggregateMonthlyFG([
      { timestamp: "2025-06-01T00:00:00Z", score: 10 },
      { timestamp: "2025-06-15T00:00:00Z", score: 20 },
      { timestamp: "2025-07-01T00:00:00Z", score: 30 },
    ]);
    expect(out.months).toEqual(["2025-06", "2025-07"]);
    expect(out.count).toEqual([2, 1]);
  });

  it("diverges median from avg when scores are skewed", () => {
    const out = aggregateMonthlyFG([
      { timestamp: "2025-06-01T00:00:00Z", score: 10 },
      { timestamp: "2025-06-02T00:00:00Z", score: 10 },
      { timestamp: "2025-06-03T00:00:00Z", score: 10 },
      { timestamp: "2025-06-04T00:00:00Z", score: 100 },
    ]);
    expect(out.median).toEqual([10]);
    expect(out.avg).toEqual([32.5]);
  });
});
