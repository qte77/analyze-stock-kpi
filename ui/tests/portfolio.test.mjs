// Unit tests for ui/lib/portfolio.js — the hypothetical long/short model
// portfolio section's pure helpers (ADR-0012). `compound` turns stored
// weekly returns into a 100-based index line client-side (no stored NAV,
// D11); `holdingsRows` flattens a weekly state's target weights for the
// holdings table.
import { describe, it, expect } from "vitest";
import { compound, holdingsRows } from "../lib/portfolio.js";

describe("compound", () => {
  it("returns empty arrays for an empty input list", () => {
    const out = compound([]);
    expect(out.dates).toEqual([]);
    expect(out.index).toEqual([]);
  });

  it("compounds ret_ls into a 100-based index by default", () => {
    const out = compound([
      { date: "2026-01-09", ret_ls: 0.1 },
      { date: "2026-01-16", ret_ls: -0.05 },
    ]);
    expect(out.dates).toEqual(["2026-01-09", "2026-01-16"]);
    expect(out.index[0]).toBeCloseTo(110, 10);
    expect(out.index[1]).toBeCloseTo(104.5, 10);
  });

  it("supports selecting ret_long or ret_short instead of ret_ls", () => {
    const rows = [{ date: "2026-01-09", ret_long: 0.2, ret_short: -0.1, ret_ls: 0.3 }];
    expect(compound(rows, "ret_long").index[0]).toBeCloseTo(120, 10);
    expect(compound(rows, "ret_short").index[0]).toBeCloseTo(90, 10);
  });

  it("carries the running level forward when a row's field is missing or non-numeric", () => {
    const out = compound([
      { date: "2026-01-09", ret_ls: 0.1 },
      { date: "2026-01-16" },
      { date: "2026-01-23", ret_ls: 0.1 },
    ]);
    expect(out.index[0]).toBeCloseTo(110, 10);
    expect(out.index[1]).toBeCloseTo(110, 10);
    expect(out.index[2]).toBeCloseTo(121, 10);
  });
});

describe("holdingsRows", () => {
  it("returns an empty array for null/undefined state", () => {
    expect(holdingsRows(null)).toEqual([]);
    expect(holdingsRows(undefined)).toEqual([]);
  });

  it("flattens long then short, each sorted descending by weight", () => {
    const state = {
      long: [
        { ticker: "AAPL", weight: 0.1 },
        { ticker: "MSFT", weight: 0.3 },
      ],
      short: [
        { ticker: "XOM", weight: 0.2 },
        { ticker: "CVX", weight: 0.05 },
      ],
    };
    expect(holdingsRows(state)).toEqual([
      { ticker: "MSFT", side: "long", weight: 0.3 },
      { ticker: "AAPL", side: "long", weight: 0.1 },
      { ticker: "XOM", side: "short", weight: 0.2 },
      { ticker: "CVX", side: "short", weight: 0.05 },
    ]);
  });

  it("tolerates a state missing one leg", () => {
    const state = { long: [{ ticker: "AAPL", weight: 1 }], short: [] };
    expect(holdingsRows(state)).toEqual([{ ticker: "AAPL", side: "long", weight: 1 }]);
  });
});
