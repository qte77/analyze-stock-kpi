// Unit tests for docs/demo/lib/coloring.js — A1 conditional cell
// coloring thresholds per KPI. Non-trivial cases only: boundary
// inclusivity, lower-better vs higher-better direction, null/NaN/
// unknown-column null returns.
import { describe, it, expect } from "vitest";
import { cellClass } from "../../docs/demo/lib/coloring.js";

describe("cellClass", () => {
  it("returns null when the column is not in the threshold map", () => {
    expect(cellClass("unknown_kpi", 5)).toBeNull();
  });

  it("returns null for null / undefined / NaN values regardless of column", () => {
    expect(cellClass("forward_pe", null)).toBeNull();
    expect(cellClass("forward_pe", undefined)).toBeNull();
    expect(cellClass("forward_pe", Number.NaN)).toBeNull();
  });

  describe("lower-better KPIs (forward_pe: good < 20 < neutral < 30 < bad)", () => {
    it("classifies a value below the good threshold as kpi-good", () => {
      expect(cellClass("forward_pe", 15)).toBe("kpi-good");
    });

    it("treats the lower bound of the neutral band as inclusive (good→neutral at 20)", () => {
      expect(cellClass("forward_pe", 20)).toBe("kpi-neutral");
    });

    it("classifies a mid-range value as kpi-neutral", () => {
      expect(cellClass("forward_pe", 25)).toBe("kpi-neutral");
    });

    it("treats the lower bound of the bad band as inclusive (neutral→bad at 30)", () => {
      expect(cellClass("forward_pe", 30)).toBe("kpi-bad");
    });

    it("classifies a value far above the bad threshold as kpi-bad", () => {
      expect(cellClass("forward_pe", 50)).toBe("kpi-bad");
    });
  });

  describe("higher-better KPIs (return_on_equity: bad < 0.05 < neutral < 0.15 < good)", () => {
    it("classifies a value above the good threshold as kpi-good", () => {
      expect(cellClass("return_on_equity", 0.2)).toBe("kpi-good");
    });

    it("treats the good-band lower bound as inclusive (neutral→good at 0.15)", () => {
      expect(cellClass("return_on_equity", 0.15)).toBe("kpi-good");
    });

    it("classifies a mid-range value as kpi-neutral", () => {
      expect(cellClass("return_on_equity", 0.1)).toBe("kpi-neutral");
    });

    it("classifies a value below the bad threshold as kpi-bad", () => {
      expect(cellClass("return_on_equity", 0.02)).toBe("kpi-bad");
    });
  });

  it("handles the nested composite-screener key via dot-path lookup", () => {
    expect(cellClass("composite_scores.screener_score", 75)).toBe("kpi-good");
    expect(cellClass("composite_scores.screener_score", 50)).toBe("kpi-neutral");
    expect(cellClass("composite_scores.screener_score", 20)).toBe("kpi-bad");
  });
});
