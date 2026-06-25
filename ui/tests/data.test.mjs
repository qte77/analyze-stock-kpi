// Unit tests for ui/lib/data.js — Pages-origin → data-branch base URL.
// Non-trivial cases only: fork self-host, the canonical no-op, and the three
// fallback shapes (root Pages, localhost, custom domain).
import { describe, it, expect } from "vitest";
import { defaultDataBase } from "../lib/data.js";

const CANONICAL = "https://raw.githubusercontent.com/qte77/analyze-stock-kpi/data";

describe("defaultDataBase", () => {
  it("derives the owner/repo data branch from a fork's project Pages origin", () => {
    expect(defaultDataBase("alice.github.io", "/analyze-stock-kpi/")).toBe(
      "https://raw.githubusercontent.com/alice/analyze-stock-kpi/data",
    );
  });

  it("resolves the qte77 deploy to exactly the canonical URL (no behaviour change)", () => {
    expect(defaultDataBase("qte77.github.io", "/analyze-stock-kpi/")).toBe(CANONICAL);
  });

  it("falls back to canonical for a user/org-root Pages site (no repo segment)", () => {
    expect(defaultDataBase("qte77.github.io", "/")).toBe(CANONICAL);
  });

  it("falls back to canonical for localhost", () => {
    expect(defaultDataBase("localhost", "/ui/")).toBe(CANONICAL);
  });

  it("falls back to canonical for a custom domain", () => {
    expect(defaultDataBase("stocks.example.com", "/analyze-stock-kpi/")).toBe(CANONICAL);
  });
});
