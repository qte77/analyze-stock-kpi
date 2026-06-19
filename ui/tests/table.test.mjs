// Tests for the pure row helpers in ui/table.js. The DOM rendering
// (renderUniverseTable / renderRow) is glue verified by hand via `make
// preview`; here we cover the branchy pure logic only.

import { describe, it, expect } from "vitest";
import {
  buildRowTitle,
  coverageCount,
  meanComposite,
  totalCompositeScore,
  emptyTableMessage,
} from "../table.js";

describe("buildRowTitle", () => {
  it("shows weight + score + coverage when score and total are positive", () => {
    expect(buildRowTitle(50, 200, 9)).toBe("Weight 25.0 % · Score 50 · 9/9 inputs");
  });
  it("omits weight/score when score is null", () => {
    expect(buildRowTitle(null, 200, 4)).toBe("4/9 inputs");
  });
  it("omits weight/score when totalScore is 0", () => {
    expect(buildRowTitle(50, 0, 7)).toBe("7/9 inputs");
  });
});

describe("coverageCount", () => {
  const full = {
    forward_pe: 12,
    trailing_peg_ratio: 1,
    beta: 1,
    rd_to_revenue: 0.1,
    operating_margins: 0.2,
    return_on_equity: 0.3,
    return_on_assets: 0.1,
    current_ratio: 2,
    sortino_ratio: 1,
  };
  it("counts all 9 populated inputs", () => {
    expect(coverageCount(full)).toBe(9);
  });
  it("treats forward_pe <= 0 as the missing sentinel", () => {
    expect(coverageCount({ ...full, forward_pe: 0 })).toBe(8);
    expect(coverageCount({ ...full, forward_pe: -5 })).toBe(8);
  });
  it("returns 0 when no input is populated", () => {
    expect(coverageCount({})).toBe(0);
  });
  it("counts only the populated inputs in a mixed row", () => {
    expect(coverageCount({ beta: 1, current_ratio: 2 })).toBe(2);
  });
});

describe("meanComposite", () => {
  it("returns null when composite_scores is absent or null", () => {
    expect(meanComposite({})).toBeNull();
    expect(meanComposite({ composite_scores: null })).toBeNull();
  });
  it("returns null when no composite field is populated", () => {
    expect(meanComposite({ composite_scores: {} })).toBeNull();
  });
  it("averages only the populated composite fields", () => {
    expect(meanComposite({ composite_scores: { quality: 80, growth: 40 } })).toBe(60);
  });
  it("averages all 7 when fully populated", () => {
    const cs = {
      quality: 10,
      dividend: 10,
      growth: 10,
      big_call: 10,
      aaqs: 10,
      hgi: 10,
      screener_score: 10,
    };
    expect(meanComposite({ composite_scores: cs })).toBe(10);
  });
});

describe("totalCompositeScore", () => {
  it("sums each row's composite_scores.screener_score", () => {
    const rows = [
      { composite_scores: { screener_score: 60 } },
      { composite_scores: { screener_score: 40 } },
    ];
    expect(totalCompositeScore(rows)).toBe(100);
  });
  it("treats null / missing scores as 0", () => {
    const rows = [
      { composite_scores: { screener_score: 70 } },
      { composite_scores: { screener_score: null } },
      {},
    ];
    expect(totalCompositeScore(rows)).toBe(70);
  });
  it("returns 0 for an empty list", () => {
    expect(totalCompositeScore([])).toBe(0);
  });
});

describe("emptyTableMessage", () => {
  it("reports the active filter query first", () => {
    expect(emptyTableMessage("AAPL", "sp500")).toBe('no matches for "AAPL"');
  });
  it("explains the enhanced-kpi-screener conjunctive gate", () => {
    expect(emptyTableMessage("", "enhanced-kpi-screener-longs")).toContain(
      "conjunctive 14-criteria gate",
    );
  });
  it("explains the aggregator freshness gate", () => {
    expect(emptyTableMessage("", "aggregated-scores-best")).toContain("min-composites gate");
  });
  it("falls back to the pending-cron message for a static universe", () => {
    expect(emptyTableMessage("", "sp500")).toContain("first cron run pending");
  });
});
