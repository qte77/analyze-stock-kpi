// Tests for the pure detail-panel row builders in ui/lib/detail_rows.js.
// (KPI_GLOSSARY is static data — no test; the DOM rendering that consumes
// these tuples lives in showDetail() in app.js.)

import { describe, it, expect } from "vitest";
import { auditDetailRows, externalLinkRows, kpiGroups } from "../lib/detail_rows.js";

// Plan 010 D7: the panel's KPI groups are the qte77 Score's four factors, and
// each of the Score's 9 inputs sits in the group of the factor it feeds
// (src/analyze_stock_kpi/domain/composite_scores.py, screener_score).
describe("kpiGroups", () => {
  // Distinct sentinel values, so each formatted value is findable in one group.
  const row = {
    return_on_equity: 0.111,
    return_on_assets: 0.222,
    operating_margins: 0.333,
    rd_to_revenue: 0.444,
    forward_pe: 55.55,
    trailing_peg_ratio: 66.66,
    beta: 7.77,
    current_ratio: 8.88,
    sortino_ratio: 9.99,
  };
  const FACTOR_INPUTS = {
    Profitability: ["11.10", "22.20", "33.30", "44.40"],
    Valuation: ["55.55", "66.66"],
    Risk: ["7.77", "8.88"],
    Momentum: ["9.99"],
  };

  it("returns the Score's four factors, in the Score tooltip's order", () => {
    expect(kpiGroups(row).map((g) => g.title)).toEqual(Object.keys(FACTOR_INPUTS));
  });

  it("puts every Score input in exactly its own factor's group", () => {
    const groups = kpiGroups(row);
    for (const [factor, values] of Object.entries(FACTOR_INPUTS)) {
      for (const value of values) {
        const holders = groups
          .filter((g) => g.rows.some(([, v]) => v.includes(value)))
          .map((g) => g.title);
        expect(holders, `${value} (${factor})`).toEqual([factor]);
      }
    }
  });
});

describe("auditDetailRows", () => {
  it("returns [] for a null audit", () => {
    expect(auditDetailRows(null)).toEqual([]);
  });

  it("builds the federal-contracts block with a section header + fields", () => {
    const rows = auditDetailRows({
      obligated_usd: 1234567,
      uei: "ABC123",
      edgar_match_score: 0.92,
      recipient_name: "Acme Corp",
    });
    expect(rows[0]).toEqual(["Federal Contracts", "", true]);
    expect(rows[1][0]).toBe("Obligated $");
    expect(typeof rows[1][1]).toBe("string"); // delegated to formatObligated
    expect(rows.find((r) => r[0] === "UEI")?.[1]).toBe("ABC123");
    expect(rows.find((r) => r[0] === "Recipient name")?.[1]).toBe("Acme Corp");
  });

  it("formats a populated EDGAR match score as a rounded percentage", () => {
    const rows = auditDetailRows({ edgar_match_score: 0.92 });
    expect(rows.find((r) => r[0] === "EDGAR match")?.[1]).toBe("92 %");
  });

  it("renders '—' for null EDGAR score and missing uei / recipient", () => {
    const rows = auditDetailRows({ edgar_match_score: null });
    expect(rows.find((r) => r[0] === "EDGAR match")?.[1]).toBe("—");
    expect(rows.find((r) => r[0] === "UEI")?.[1]).toBe("—");
    expect(rows.find((r) => r[0] === "Recipient name")?.[1]).toBe("—");
  });
});

describe("externalLinkRows", () => {
  it("returns [] when the row has no symbol", () => {
    expect(externalLinkRows({})).toEqual([]);
  });

  it("builds Yahoo / SEC EDGAR / Wikipedia links, URL-encoding the query", () => {
    const rows = externalLinkRows({
      symbol: "BRK.B",
      long_name: "Berkshire Hathaway",
    });
    expect(rows.map((r) => r[0])).toEqual(["Yahoo", "SEC EDGAR", "Wikipedia"]);
    expect(rows[0][1]).toBe("https://finance.yahoo.com/quote/BRK.B");
    expect(rows[2][1]).toContain("search=Berkshire%20Hathaway");
  });

  it("falls back to the symbol for the Wikipedia query when long_name is absent", () => {
    const rows = externalLinkRows({ symbol: "AAPL" });
    expect(rows[2][1]).toContain("search=AAPL");
  });
});
