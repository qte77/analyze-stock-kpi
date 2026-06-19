// Unit tests for ui/lib/timeseries.js — per-ticker time-series
// builder for the detail-panel time-series tab (C3 of #137). Non-trivial
// cases only: empty input, missing-ticker holes, composite-scores nested
// access, exact (case-sensitive) symbol matching.
import { describe, it, expect } from "vitest";
import { buildTimeSeries } from "../lib/timeseries.js";

describe("buildTimeSeries", () => {
  it("returns empty series for an empty input list", () => {
    const series = buildTimeSeries([], "AAPL");
    expect(series.dates).toEqual([]);
    expect(series.score).toEqual([]);
    expect(series.quality).toEqual([]);
    expect(series.growth).toEqual([]);
    expect(series.sortino).toEqual([]);
  });

  it("emits one data point per input date even when the ticker is missing", () => {
    const series = buildTimeSeries(
      [
        { date: "2024-01-31", rows: [{ symbol: "MSFT" }] },
        {
          date: "2024-02-29",
          rows: [
            {
              symbol: "AAPL",
              sortino_ratio: 1.5,
              composite_scores: { screener_score: 72 },
            },
          ],
        },
      ],
      "AAPL",
    );
    expect(series.dates).toEqual(["2024-01-31", "2024-02-29"]);
    expect(series.score).toEqual([null, 72]);
    expect(series.sortino).toEqual([null, 1.5]);
  });

  it("reads composite-score fields via nested access (quality/growth/screener)", () => {
    const series = buildTimeSeries(
      [
        {
          date: "2024-05-31",
          rows: [
            {
              symbol: "AAPL",
              composite_scores: {
                quality: 80,
                growth: 65,
                screener_score: 78,
              },
            },
          ],
        },
      ],
      "AAPL",
    );
    expect(series.quality).toEqual([80]);
    expect(series.growth).toEqual([65]);
    expect(series.score).toEqual([78]);
  });

  it("matches symbol case-exact (case mismatch yields a null hole, not surprise data)", () => {
    const series = buildTimeSeries(
      [{ date: "2024-05-31", rows: [{ symbol: "AAPL", sortino_ratio: 1.5 }] }],
      "aapl",
    );
    expect(series.sortino).toEqual([null]);
  });

  it("treats rows[] being null/undefined as a missing-data point (silent fault tolerance)", () => {
    const series = buildTimeSeries(
      [
        { date: "2024-04-30", rows: null },
        { date: "2024-05-31", rows: [{ symbol: "AAPL", sortino_ratio: 1.5 }] },
      ],
      "AAPL",
    );
    expect(series.dates).toEqual(["2024-04-30", "2024-05-31"]);
    expect(series.sortino).toEqual([null, 1.5]);
  });

  it("ignores entries whose date is missing (degenerate snapshot)", () => {
    const series = buildTimeSeries(
      [
        { date: "", rows: [{ symbol: "AAPL", sortino_ratio: 2 }] },
        { date: "2024-05-31", rows: [{ symbol: "AAPL", sortino_ratio: 1.5 }] },
      ],
      "AAPL",
    );
    expect(series.dates).toEqual(["2024-05-31"]);
    expect(series.sortino).toEqual([1.5]);
  });
});
