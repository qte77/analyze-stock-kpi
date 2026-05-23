// @ts-check
// Federal-contractors audit JSON helpers extracted from docs/demo/app.js
// so they can be unit-tested without a DOM. Tested by
// tests/demo/audit.test.mjs.

/** @typedef {import("../types.d.ts")} _Types */

/**
 * Build a Map keyed by `final_ticker` from a list of AuditRow objects.
 * Rows with `final_ticker` null/missing are skipped (they didn't resolve
 * to a tradeable ticker so they have no row in the universe snapshot
 * to attach to). Last-wins for duplicate keys.
 *
 * @param {unknown} rows  Parsed JSON; should be an `AuditRow[]`. Returns
 *                        `null` when not an array so the silent-404 +
 *                        bad-response paths converge on one sentinel.
 * @returns {Map<string, AuditRow> | null}
 */
export function buildAuditMap(rows) {
  if (!Array.isArray(rows)) return null;
  /** @type {Map<string, AuditRow>} */
  const map = new Map();
  for (const row of rows) {
    if (row && typeof row === "object" && typeof row.final_ticker === "string") {
      map.set(row.final_ticker, row);
    }
  }
  return map;
}

/**
 * Opportunistic audit-JSON fetch with silent-404 + universe-filter
 * contracts. Returns `null` for any non-federal-contractors universe
 * (no fetcher call) and for any fetcher rejection (silent-404).
 *
 * `fetcher` is dependency-injected so tests don't need a DOM/network.
 *
 * @param {string} universe
 * @param {string} date  ISO yyyy-mm-dd
 * @param {string} baseUrl  Origin + path of the `data` branch raw host
 * @param {(url: string) => Promise<unknown>} fetcher
 * @returns {Promise<Map<string, AuditRow> | null>}
 */
export async function loadAudit(universe, date, baseUrl, fetcher) {
  if (universe !== "federal-contractors") return null;
  try {
    const rows = await fetcher(
      `${baseUrl}/results/federal_contractors/audit/${date}.json`,
    );
    return buildAuditMap(rows);
  } catch {
    return null;
  }
}

/**
 * Format an obligated-USD amount with a unit suffix. `null`/`NaN`/missing
 * → em-dash. Boundaries: `>= 1e9` → "b" (billions, 2 decimals); `>= 1e6`
 * → "M" (millions, 2 decimals); else plain dollars (no decimals).
 *
 * @param {number | null | undefined} usd
 * @returns {string}
 */
export function formatObligated(usd) {
  if (usd == null) return "—";
  const n = Number(usd);
  if (Number.isNaN(n)) return "—";
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)} b`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)} M`;
  return `$${n.toFixed(0)}`;
}
