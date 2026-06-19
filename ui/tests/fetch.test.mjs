// Tests for the fetch helpers in ui/lib/fetch.js. `globalThis.fetch`
// is stubbed per-test; loadYearsFromBranch's per-year URLs are distinguished
// by the year suffix so the full floor->now range, ascending sort, and the
// per-leg silent-fail can be asserted without a live network.

import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchJson, loadYearsFromBranch } from "../lib/fetch.js";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

/** Minimal Response-like stub. */
function res(ok, body) {
  return { ok, status: ok ? 200 : 404, json: async () => body };
}

describe("fetchJson", () => {
  it("returns parsed JSON on a 2xx response (cache disabled)", async () => {
    globalThis.fetch = vi.fn(async () => res(true, { hello: "world" }));
    await expect(fetchJson("https://x/y.json")).resolves.toEqual({ hello: "world" });
    expect(globalThis.fetch).toHaveBeenCalledWith("https://x/y.json", {
      cache: "no-cache",
    });
  });

  it("throws with the url + status on a non-2xx response", async () => {
    globalThis.fetch = vi.fn(async () => res(false));
    await expect(fetchJson("https://x/missing.json")).rejects.toThrow(
      "fetch https://x/missing.json failed: 404",
    );
  });
});

describe("loadYearsFromBranch", () => {
  const year = new Date().getUTCFullYear();

  it("concatenates both year legs and sorts ascending by the key", async () => {
    globalThis.fetch = vi.fn(async (url) => {
      const u = String(url);
      if (u.endsWith(`${year - 1}.json`)) return res(true, [{ t: "b" }, { t: "d" }]);
      if (u.endsWith(`${year}.json`)) return res(true, [{ t: "a" }, { t: "c" }]);
      return res(false);
    });
    const out = await loadYearsFromBranch("https://base", "results/x", "t");
    expect(out.map((e) => e.t)).toEqual(["a", "b", "c", "d"]);
  });

  it("keeps the fulfilled leg when the other one fails", async () => {
    globalThis.fetch = vi.fn(async (url) =>
      String(url).endsWith(`${year}.json`) ? res(true, [{ t: "x" }, { t: "y" }]) : res(false),
    );
    const out = await loadYearsFromBranch("https://base", "results/x", "t");
    expect(out.map((e) => e.t)).toEqual(["x", "y"]);
  });

  it("skips a fulfilled-but-non-array leg", async () => {
    globalThis.fetch = vi.fn(async (url) =>
      String(url).endsWith(`${year}.json`)
        ? res(true, [{ t: "z" }])
        : res(true, { not: "an array" }),
    );
    const out = await loadYearsFromBranch("https://base", "results/x", "t");
    expect(out.map((e) => e.t)).toEqual(["z"]);
  });

  it("fetches every year from the floor through this year, sorted ascending", async () => {
    const floor = 2011;
    const expected = Array.from({ length: year - floor + 1 }, (_, i) => floor + i);
    const seen = [];
    globalThis.fetch = vi.fn(async (url) => {
      const m = String(url).match(/(\d{4})\.json$/);
      const y = m ? Number(m[1]) : null;
      if (y) seen.push(y);
      return res(true, [{ t: String(y) }]);
    });
    const out = await loadYearsFromBranch("https://base", "results/x", "t");
    expect([...seen].sort((a, b) => a - b)).toEqual(expected);
    expect(out.map((e) => e.t)).toEqual(expected.map(String));
  });

  it("honours an explicit floorYear", async () => {
    const floor = year - 2;
    const seen = [];
    globalThis.fetch = vi.fn(async (url) => {
      const m = String(url).match(/(\d{4})\.json$/);
      if (m) seen.push(Number(m[1]));
      return res(true, []);
    });
    await loadYearsFromBranch("https://base", "results/x", "t", floor);
    expect([...seen].sort((a, b) => a - b)).toEqual([floor, year - 1, year]);
  });

  it("silently skips years whose file 404s and returns the rest sorted", async () => {
    globalThis.fetch = vi.fn(async (url) => {
      const u = String(url);
      if (u.endsWith(`${year - 1}.json`)) return res(true, [{ t: `${year - 1}` }]);
      if (u.endsWith(`${year}.json`)) return res(true, [{ t: `${year}` }]);
      return res(false);
    });
    const out = await loadYearsFromBranch("https://base", "results/x", "t");
    expect(out.map((e) => e.t)).toEqual([`${year - 1}`, `${year}`]);
  });
});
