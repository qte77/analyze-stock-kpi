// Tests for the themed axis factories in ui/lib/chart_axes.js. The
// point of the module is dependency injection + deferred color closures, so the
// tests assert the static shape AND that the tick/grid colors are NOT resolved
// at call time but defer to the injected cssVarFn when Chart.js later invokes
// them.

import { describe, it, expect, vi } from "vitest";
import { scoreYAxis, themedXAxis } from "../../ui/lib/chart_axes.js";

describe("scoreYAxis", () => {
  it("returns a 0–100 axis with stepSize 25", () => {
    const axis = scoreYAxis(() => "x");
    expect(axis.min).toBe(0);
    expect(axis.max).toBe(100);
    expect(axis.ticks.stepSize).toBe(25);
  });

  it("defers tick + grid colors to the injected cssVarFn", () => {
    const cssVarFn = vi.fn((token, fallback) => `${token}:${fallback}`);
    const axis = scoreYAxis(cssVarFn);
    expect(cssVarFn).not.toHaveBeenCalled(); // closures are deferred, not eager
    expect(axis.ticks.color()).toBe("--text:#1d1d1f");
    expect(axis.grid.color()).toBe("--border:#d2d2d7");
    expect(cssVarFn).toHaveBeenCalledTimes(2);
  });
});

describe("themedXAxis", () => {
  it("caps ticks at 14 by default and respects an override", () => {
    expect(themedXAxis(() => "x").ticks.maxTicksLimit).toBe(14);
    expect(themedXAxis(() => "x", 6).ticks.maxTicksLimit).toBe(6);
  });

  it("defers tick + grid colors to the injected cssVarFn", () => {
    const cssVarFn = vi.fn((token, fallback) => `${token}:${fallback}`);
    const axis = themedXAxis(cssVarFn);
    expect(cssVarFn).not.toHaveBeenCalled();
    expect(axis.ticks.color()).toBe("--text:#1d1d1f");
    expect(axis.grid.color()).toBe("--border:#d2d2d7");
  });
});
