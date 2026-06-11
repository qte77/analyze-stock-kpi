// Tests for the fetch helpers in docs/demo/lib/fetch.js. `globalThis.fetch`
// is stubbed per-test; loadYearsFromBranch's this-year/last-year URLs are
// distinguished by the year suffix so concat-order, ascending sort, and the
// per-leg silent-fail can be asserted without a live network.

import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchJson, loadYearsFromBranch } from "../../docs/demo/lib/fetch.js";

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
      String(url).endsWith(`${year}.json`)
        ? res(true, [{ t: "x" }, { t: "y" }])
        : res(false),
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
});
