// Unit tests for ui/lib/empty_reason.js — per-cell tooltip text
// when the value is missing. Pure rule-table lookup; renders `null`
// when no rule applies so the cell stays a bare "—".
//
// Non-trivial cases only: each rule (positive case), negative cases
// that prove the rule doesn't over-match, and unknown-column / non-bank
// fallthroughs.
import { describe, it, expect } from "vitest";
import { explainEmpty } from "../../ui/lib/empty_reason.js";

const bankRow = {
  symbol: "JPM",
  sector: "Financial Services",
  industry: "Banks - Diversified",
  currency: "USD",
};

const cadBankRow = {
  symbol: "RY.TO",
  sector: "Financial Services",
  industry: "Banks - Diversified",
  currency: "CAD",
};

const techRow = {
  symbol: "AAPL",
  sector: "Technology",
  industry: "Consumer Electronics",
  currency: "USD",
};

describe("explainEmpty", () => {
  it("returns null for a row with no sector/industry/currency", () => {
    expect(explainEmpty({}, "rd_to_revenue")).toBeNull();
  });

  it("returns null for an unmatched (sector, column) combo (no speculative copy)", () => {
    expect(explainEmpty(techRow, "current_ratio")).toBeNull();
    expect(explainEmpty(techRow, "return_on_equity")).toBeNull();
  });

  it("returns null for an unknown column", () => {
    expect(explainEmpty(bankRow, "some_unknown_kpi")).toBeNull();
  });

  describe("Financial Services sector — bank-specific gaps", () => {
    it("explains R&D as not reported by banks", () => {
      expect(explainEmpty(bankRow, "rd_to_revenue")).toBe("Banks don't report R&D");
    });

    it("explains current ratio absence as no current/long-term split", () => {
      expect(explainEmpty(bankRow, "current_ratio")).toBe("Banks have no current/long-term split");
    });

    it("does not over-match: returns null for forward_pe on a bank", () => {
      expect(explainEmpty(bankRow, "forward_pe")).toBeNull();
    });
  });

  describe("Canadian-bank ROE/ROA gap (narrow per #169 pending)", () => {
    it("explains missing ROE on a CAD bank", () => {
      expect(explainEmpty(cadBankRow, "return_on_equity")).toBe(
        "Yahoo doesn't ship this field for non-US banks",
      );
    });

    it("explains missing ROA on a CAD bank", () => {
      expect(explainEmpty(cadBankRow, "return_on_assets")).toBe(
        "Yahoo doesn't ship this field for non-US banks",
      );
    });

    it("does not over-match: returns null for ROE on a USD bank (Yahoo ships ROE for JPM)", () => {
      expect(explainEmpty(bankRow, "return_on_equity")).toBeNull();
    });

    it("does not over-match: returns null for ROE on a CAD non-bank", () => {
      const cadNonBank = { ...cadBankRow, industry: "Oil & Gas Integrated" };
      expect(explainEmpty(cadNonBank, "return_on_equity")).toBeNull();
    });
  });
});
