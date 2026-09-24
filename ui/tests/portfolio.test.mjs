// Unit tests for ui/lib/portfolio.js — the backtested long/short 25/25
// dashboard section's pure helpers (ADR-0013, plan 008). `compound` turns a
// cadence's stored daily returns into a 100-based index line client-side (no
// stored NAV, D5/D8); `metricsTableRows` / `keyFacts` project
// `results/backtest/summary.json` into the metrics-table rows and key-facts
// line.
import { describe, it, expect } from "vitest";
import {
  compound,
  metricsTableRows,
  keyFacts,
  sinceLabel,
  tradeLogRows,
  rebalanceMarkers,
  REBALANCE_REASON_LABELS,
} from "../lib/portfolio.js";

describe("compound", () => {
  it("returns empty arrays for an empty input list", () => {
    const out = compound([]);
    expect(out.dates).toEqual([]);
    expect(out.index).toEqual([]);
  });

  it("compounds ret_ls_net into a 100-based index by default", () => {
    const out = compound([
      { date: "2026-01-09", ret_ls_net: 0.1 },
      { date: "2026-01-16", ret_ls_net: -0.05 },
    ]);
    expect(out.dates).toEqual(["2026-01-09", "2026-01-16"]);
    expect(out.index[0]).toBeCloseTo(110, 10);
    expect(out.index[1]).toBeCloseTo(104.5, 10);
  });

  it("supports selecting any of the four stored return fields", () => {
    const rows = [
      { date: "2026-01-09", ret_long: 0.2, ret_short: -0.1, ret_ls_gross: 0.31, ret_ls_net: 0.3 },
    ];
    expect(compound(rows, "ret_long").index[0]).toBeCloseTo(120, 10);
    expect(compound(rows, "ret_short").index[0]).toBeCloseTo(90, 10);
    expect(compound(rows, "ret_ls_gross").index[0]).toBeCloseTo(131, 10);
    expect(compound(rows, "ret_ls_net").index[0]).toBeCloseTo(130, 10);
  });

  it("carries the running level forward when a row's field is missing or non-numeric", () => {
    const out = compound([
      { date: "2026-01-09", ret_ls_net: 0.1 },
      { date: "2026-01-16" },
      { date: "2026-01-23", ret_ls_net: 0.1 },
    ]);
    expect(out.index[0]).toBeCloseTo(110, 10);
    expect(out.index[1]).toBeCloseTo(110, 10);
    expect(out.index[2]).toBeCloseTo(121, 10);
  });
});

/** @type {import("../lib/portfolio.js").CadenceMetrics} */
const sampleMetrics = {
  ann_return: 0.12,
  ann_vol: 0.18,
  max_drawdown: -0.22,
  ann_turnover: 3.4,
  long_ann_return: 0.15,
  short_ann_return: -0.03,
  beta: 0.4,
  hit_rate: 0.58,
  mean_monthly_return: 0.01,
  ci90: [0.002, 0.018],
  t_stat: 2.1,
};

/** @type {import("../lib/portfolio.js").BacktestSummary} */
const sampleSummary = {
  method_version: "v1",
  as_of: "2026-09-20",
  start: "2021-11-01",
  universes: ["sp500"],
  score_inputs: ["return_on_equity"],
  cost_bps: 10,
  primary: "monthly",
  cadences: {
    monthly: { gross: sampleMetrics, net: { ...sampleMetrics, ann_return: 0.1 }, rebalances: 58 },
    weekly: { gross: sampleMetrics, net: { ...sampleMetrics, ann_return: 0.08 }, rebalances: 251 },
  },
  null: { n: 1000, percentile: 88, median_net_ann: 0.02 },
  fidelity: { per_date: [{ date: "2026-05-22", rho: 0.7, n: 300 }], median_rho: 0.71 },
  caveats: ["Survivorship: today's universe membership is used for the whole backfill."],
};

describe("metricsTableRows", () => {
  it("returns an empty array for a null/undefined summary", () => {
    expect(metricsTableRows(null, "net")).toEqual([]);
    expect(metricsTableRows(undefined, "net")).toEqual([]);
  });

  it("orders rows by the fixed cadence display order, skipping absent cadences", () => {
    const rows = metricsTableRows(sampleSummary, "net");
    expect(rows.map((r) => r.key)).toEqual(["monthly", "weekly"]);
  });

  it("flags only the primary cadence (from summary.primary, not hardcoded)", () => {
    const rows = metricsTableRows(sampleSummary, "net");
    expect(rows.find((r) => r.key === "monthly")?.primary).toBe(true);
    expect(rows.find((r) => r.key === "weekly")?.primary).toBe(false);
  });

  it("selects the requested gross/net mode's metrics + carries rebalances", () => {
    const netRows = metricsTableRows(sampleSummary, "net");
    const grossRows = metricsTableRows(sampleSummary, "gross");
    expect(netRows.find((r) => r.key === "monthly")?.ann_return).toBeCloseTo(0.1, 10);
    expect(grossRows.find((r) => r.key === "monthly")?.ann_return).toBeCloseTo(0.12, 10);
    expect(netRows.find((r) => r.key === "monthly")?.rebalances).toBe(58);
  });

  it("skips a cadence missing the requested mode", () => {
    const partial = {
      ...sampleSummary,
      cadences: { monthly: { gross: sampleMetrics, rebalances: 1 } },
    };
    expect(metricsTableRows(partial, "net")).toEqual([]);
  });
});

describe("keyFacts", () => {
  it("extracts start, primary-cadence net beta, null percentile, and fidelity median rho", () => {
    expect(keyFacts(sampleSummary)).toEqual({
      start: "2021-11-01",
      beta: 0.4,
      nullPercentile: 88,
      fidelityRho: 0.71,
    });
  });

  it("resolves every field to null for a null/undefined summary", () => {
    expect(keyFacts(null)).toEqual({
      start: null,
      beta: null,
      nullPercentile: null,
      fidelityRho: null,
    });
    expect(keyFacts(undefined)).toEqual({
      start: null,
      beta: null,
      nullPercentile: null,
      fidelityRho: null,
    });
  });

  it("tolerates a summary whose primary cadence is absent from cadences", () => {
    const broken = { ...sampleSummary, primary: "buy_hold" };
    expect(keyFacts(broken).beta).toBeNull();
  });

  it("resolves null/fidelity to null (D16: Series A may not have either yet)", () => {
    const sparse = { ...sampleSummary, null: null, fidelity: null };
    expect(keyFacts(sparse)).toEqual({
      start: "2021-11-01",
      beta: 0.4,
      nullPercentile: null,
      fidelityRho: null,
    });
  });
});

describe("sinceLabel", () => {
  it("appends the start date once known", () => {
    expect(sinceLabel("Genuine decisions", "2026-05-31")).toBe(
      "Genuine decisions since 2026-05-31",
    );
  });

  it("falls back to the plain base text when start is null or undefined", () => {
    expect(sinceLabel("Genuine decisions", null)).toBe("Genuine decisions");
    expect(sinceLabel("Genuine decisions", undefined)).toBe("Genuine decisions");
  });

  it("falls back to the plain base text for an empty-string start", () => {
    expect(sinceLabel("Genuine decisions", "")).toBe("Genuine decisions");
  });
});

/** @type {import("../lib/portfolio.js").TradeLogEntry[]} */
const sampleTrades = [
  {
    rank_date: "2026-06-01",
    trade_date: "2026-06-02",
    reason: "scheduled_monthly",
    long: { entered: [{ ticker: "AAPL", rank: 1, score: 91.2 }], exited: [] },
    short: { entered: [], exited: [{ ticker: "XYZ", rank: null, score: null }] },
    turnover: 0.12,
  },
  {
    rank_date: "2026-05-31",
    trade_date: "2026-06-01",
    reason: "initial",
    long: { entered: [{ ticker: "MSFT", rank: 2, score: 88.4 }], exited: [] },
    short: { entered: [{ ticker: "XYZ", rank: 25, score: 4.1 }], exited: [] },
    turnover: 1,
  },
];

describe("tradeLogRows", () => {
  it("returns an empty array for null/undefined trades", () => {
    expect(tradeLogRows(null)).toEqual([]);
    expect(tradeLogRows(undefined)).toEqual([]);
  });

  it("sorts newest trade_date first without mutating the input", () => {
    const rows = tradeLogRows(sampleTrades);
    expect(rows.map((r) => r.trade_date)).toEqual(["2026-06-02", "2026-06-01"]);
    expect(sampleTrades[0].trade_date).toBe("2026-06-02"); // unchanged order
  });

  it("attaches each row's human reason label", () => {
    const rows = tradeLogRows(sampleTrades);
    expect(rows[0].reasonLabel).toBe(REBALANCE_REASON_LABELS.scheduled_monthly);
    expect(rows[1].reasonLabel).toBe(REBALANCE_REASON_LABELS.initial);
  });

  it("falls back to the raw reason string for an unrecognized value", () => {
    const rows = tradeLogRows([{ ...sampleTrades[0], reason: "future_reason" }]);
    expect(rows[0].reasonLabel).toBe("future_reason");
  });

  it("passes through nullable rank/score on exited legs unchanged (Series A limitation)", () => {
    const rows = tradeLogRows(sampleTrades);
    expect(rows[0].short.exited[0]).toEqual({ ticker: "XYZ", rank: null, score: null });
  });
});

describe("rebalanceMarkers", () => {
  it("places the index value only at rebalance trade dates, null elsewhere", () => {
    const dates = ["2026-06-01", "2026-06-02", "2026-06-03"];
    const indexValues = [100, 101.5, 99.8];
    const markers = rebalanceMarkers(dates, indexValues, ["2026-06-02"]);
    expect(markers).toEqual([null, 101.5, null]);
  });

  it("returns null for a trade date not present on the chart's date axis", () => {
    const markers = rebalanceMarkers(["2026-06-01"], [100], ["2026-06-09"]);
    expect(markers).toEqual([null]);
  });

  it("returns null when the aligned index value is missing/non-numeric", () => {
    const markers = rebalanceMarkers(["2026-06-01"], [null], ["2026-06-01"]);
    expect(markers).toEqual([null]);
  });

  it("returns an all-null array for no trade dates", () => {
    expect(rebalanceMarkers(["2026-06-01", "2026-06-02"], [100, 101], [])).toEqual([null, null]);
  });
});
