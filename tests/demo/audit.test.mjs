// Unit tests for ui/lib/audit.js — pure audit-Map builder + the
// universe-aware fetch wrapper + obligated-USD formatter. Non-trivial
// cases only: silent-404 contract, null/last-wins keying, boundary
// formatting.
import { describe, it, expect } from "vitest";
import {
  buildAuditMap,
  loadAudit,
  formatObligated,
} from "../../ui/lib/audit.js";

describe("buildAuditMap", () => {
  it("returns null when the input is not an array (404 fallback path)", () => {
    expect(buildAuditMap(null)).toBeNull();
    expect(buildAuditMap(undefined)).toBeNull();
    expect(buildAuditMap("not-an-array")).toBeNull();
  });

  it("skips rows whose final_ticker is null (unresolved audit entries)", () => {
    const map = buildAuditMap([
      { rank: 1, recipient_name: "FOO LLC", final_ticker: null },
      { rank: 2, recipient_name: "LOCKHEED", final_ticker: "LMT" },
    ]);
    expect(map?.size).toBe(1);
    expect(map?.get("LMT")?.recipient_name).toBe("LOCKHEED");
    expect(map?.has(/** @type {string} */ (/** @type {unknown} */ (null)))).toBe(false);
  });

  it("uses last-wins semantics when two rows share the same final_ticker", () => {
    const map = buildAuditMap([
      { rank: 1, recipient_name: "LMT PARENT", final_ticker: "LMT", obligated_usd: 1e9 },
      { rank: 2, recipient_name: "LMT SUB", final_ticker: "LMT", obligated_usd: 2e9 },
    ]);
    expect(map?.get("LMT")?.recipient_name).toBe("LMT SUB");
  });
});

describe("loadAudit", () => {
  const BASE = "https://example.com/data";

  it("returns null for any non-federal-contractors universe without calling fetcher", async () => {
    let fetched = false;
    const fetcher = async () => {
      fetched = true;
      return [];
    };
    const result = await loadAudit("qte77-watchlist", "2024-05-15", BASE, fetcher);
    expect(result).toBeNull();
    expect(fetched).toBe(false);
  });

  it("returns null when the fetcher throws (silent-404 contract)", async () => {
    const fetcher = async () => {
      throw new Error("404 Not Found");
    };
    const result = await loadAudit(
      "federal-contractors",
      "2024-05-15",
      BASE,
      fetcher,
    );
    expect(result).toBeNull();
  });

  it("returns a Map keyed by final_ticker on the happy path", async () => {
    const fetcher = async (/** @type {string} */ url) => {
      expect(url).toBe(`${BASE}/results/federal_contractors/audit/2024-05-15.json`);
      return [
        { rank: 1, recipient_name: "LOCKHEED MARTIN CORPORATION", final_ticker: "LMT" },
      ];
    };
    const map = await loadAudit(
      "federal-contractors",
      "2024-05-15",
      BASE,
      fetcher,
    );
    expect(map?.get("LMT")?.recipient_name).toBe("LOCKHEED MARTIN CORPORATION");
  });
});

describe("formatObligated", () => {
  it("returns the em-dash when the value is null, undefined, or non-numeric", () => {
    expect(formatObligated(null)).toBe("—");
    expect(formatObligated(undefined)).toBe("—");
    expect(formatObligated(Number.NaN)).toBe("—");
  });

  it("formats values < $1M with no unit suffix", () => {
    expect(formatObligated(500)).toBe("$500");
  });

  it("formats values in [$1M, $1b) as MM with two decimals", () => {
    expect(formatObligated(1_500_000)).toBe("$1.50 M");
    expect(formatObligated(999_999_999)).toBe("$1000.00 M");
  });

  it("formats values >= $1b as b with two decimals", () => {
    expect(formatObligated(1_000_000_000)).toBe("$1.00 b");
    expect(formatObligated(1.7e10)).toBe("$17.00 b");
  });
});
