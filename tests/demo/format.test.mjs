// Tests for ui/lib/format.js — pure value formatters + a null-aware
// comparator + dotted-key accessor shared by the dashboard's table/detail
// rendering. No DOM; plain values in/out.

import { describe, it, expect } from "vitest";
import {
  nested,
  fmtNum,
  fmtPct,
  compareValues,
} from "../../ui/lib/format.js";

describe("nested", () => {
  it("reads a flat key", () => {
    expect(nested({ a: 1 }, "a")).toBe(1);
  });
  it("reads a dotted nested key", () => {
    expect(nested({ a: { b: { c: 7 } } }, "a.b.c")).toBe(7);
  });
  it("returns null when an intermediate segment is missing", () => {
    expect(nested({ a: {} }, "a.b.c")).toBeNull();
  });
  it("returns null when the root is nullish", () => {
    expect(nested(null, "a.b")).toBeNull();
  });
});

describe("fmtNum", () => {
  it("returns the em-dash for null / undefined", () => {
    expect(fmtNum(null)).toBe("—");
    expect(fmtNum(undefined)).toBe("—");
  });
  it("returns the em-dash for non-numeric / NaN input", () => {
    expect(fmtNum("abc")).toBe("—");
    expect(fmtNum(NaN)).toBe("—");
  });
  it("formats to the requested precision (default 1)", () => {
    expect(fmtNum(2)).toBe("2.0");
    expect(fmtNum(1.234, 2)).toBe("1.23");
  });
});

describe("fmtPct", () => {
  it("returns the em-dash for null / undefined", () => {
    expect(fmtPct(null)).toBe("—");
    expect(fmtPct(undefined)).toBe("—");
  });
  it("scales a fraction to a 2-decimal percentage value", () => {
    expect(fmtPct(0.1523)).toBe("15.23");
  });
  it("does NOT guard NaN (historical behaviour) — yields 'NaN'", () => {
    expect(fmtPct(NaN)).toBe("NaN");
  });
});

describe("compareValues", () => {
  it("treats two nulls as equal", () => {
    expect(compareValues(null, null, 1)).toBe(0);
  });
  it("sorts nulls last regardless of direction", () => {
    expect(compareValues(null, 5, 1)).toBe(1);
    expect(compareValues(null, 5, -1)).toBe(1);
    expect(compareValues(5, null, 1)).toBe(-1);
    expect(compareValues(5, null, -1)).toBe(-1);
  });
  it("compares strings via localeCompare, scaled by dir", () => {
    expect(compareValues("a", "b", 1)).toBeLessThan(0);
    expect(compareValues("a", "b", -1)).toBeGreaterThan(0);
  });
  it("compares numbers numerically, scaled by dir", () => {
    expect(compareValues(1, 2, 1)).toBeLessThan(0);
    expect(compareValues(1, 2, -1)).toBeGreaterThan(0);
  });
});
