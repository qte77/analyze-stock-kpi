// Tests for ui/lib/window.js — pure time-window helpers for the
// dashboard's long-term charts. No DOM; plain data in/out. The Chart.js
// render that consumes these lives in ui/app.js.

import { describe, it, expect } from "vitest";
import { WINDOW_DAYS, filterByWindow, findClosestScore } from "../../ui/lib/window.js";

describe("WINDOW_DAYS", () => {
  it("maps each window key to its trailing day count; 'all' is Infinity", () => {
    expect(WINDOW_DAYS["1y"]).toBe(365);
    expect(WINDOW_DAYS["5y"]).toBe(1826);
    expect(WINDOW_DAYS["10y"]).toBe(3653);
    expect(WINDOW_DAYS.all).toBe(Infinity);
  });
});

describe("filterByWindow", () => {
  const mk = (/** @type {string[]} */ days) => days.map((d) => ({ timestamp: d }));

  it("returns the same array reference for an empty list", () => {
    const empty = [];
    expect(filterByWindow(empty, "1y", "timestamp")).toBe(empty);
  });

  it("passes everything through unchanged for the 'all' window (Infinity)", () => {
    const entries = mk(["2020-01-01", "2026-06-01"]);
    expect(filterByWindow(entries, "all", "timestamp")).toBe(entries);
  });

  it("returns the input unchanged when the latest timestamp is unparseable", () => {
    const entries = mk(["2026-01-01", "not-a-date"]);
    expect(filterByWindow(entries, "1y", "timestamp")).toBe(entries);
  });

  it("keeps the entry exactly on the cutoff boundary (>= is inclusive)", () => {
    // latest = 2026-06-10 (UTC midnight); 1y cutoff = 2025-06-10 exactly.
    const entries = mk(["2025-06-09", "2025-06-10", "2026-06-10"]);
    const out = filterByWindow(entries, "1y", "timestamp");
    expect(out.map((e) => e.timestamp)).toEqual(["2025-06-10", "2026-06-10"]);
  });

  it("drops entries older than the trailing window", () => {
    const entries = mk(["2020-01-01", "2026-01-01", "2026-06-10"]);
    const out = filterByWindow(entries, "1y", "timestamp");
    expect(out.map((e) => e.timestamp)).toEqual(["2026-01-01", "2026-06-10"]);
  });

  it("honours an arbitrary iso field name", () => {
    const entries = [{ date: "2020-01-01" }, { date: "2026-06-10" }];
    const out = filterByWindow(entries, "1y", "date");
    expect(out.map((e) => e.date)).toEqual(["2026-06-10"]);
  });
});

describe("findClosestScore", () => {
  const latest = Date.parse("2026-06-10");

  it("returns undefined for an empty list", () => {
    expect(findClosestScore([], latest, 7)).toBeUndefined();
  });

  it("returns the only entry's score regardless of distance", () => {
    const entries = [{ timestamp: "2000-01-01", score: 42 }];
    expect(findClosestScore(entries, latest, 7)).toBe(42);
  });

  it("picks the entry nearest the target offset (daysAgo)", () => {
    const entries = [
      { timestamp: "2026-06-01", score: 10 },
      { timestamp: "2026-06-09", score: 20 },
      { timestamp: "2026-05-01", score: 30 },
    ];
    // daysAgo = 1 → target = 2026-06-09 → score 20
    expect(findClosestScore(entries, latest, 1)).toBe(20);
  });

  it("keeps the first of two equidistant entries (strict <)", () => {
    const entries = [
      { timestamp: "2026-06-09", score: 1 }, // 1 day before target
      { timestamp: "2026-06-11", score: 2 }, // 1 day after target
    ];
    // daysAgo = 0 → target = latest = 2026-06-10
    expect(findClosestScore(entries, latest, 0)).toBe(1);
  });
});
