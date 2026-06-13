// @ts-check
// Multi-universe overlay (#137). Pure merge of per-universe snapshot
// arrays into a single row list with each row annotated with its source
// universe under `_universe`. The DOM-side multi-fetch + chip wiring
// lives in app.js. Tested by tests/demo/overlay.test.mjs.

/**
 * Merge a `{universe-id → rows}` mapping into a single annotated array.
 * Universes whose value isn't an array (typically because their fetch
 * rejected) are silently skipped so the overlay degrades gracefully if
 * one of the picked universes is unreachable.
 *
 * @param {Record<string, Row[] | null | undefined>} snapshotsByUniverse
 * @returns {Array<Row & {_universe: string}>}
 */
export function mergeUniverseSnapshots(snapshotsByUniverse) {
  /** @type {Array<Row & {_universe: string}>} */
  const merged = [];
  for (const [universe, rows] of Object.entries(snapshotsByUniverse)) {
    if (!Array.isArray(rows)) continue;
    for (const row of rows) {
      merged.push({ ...row, _universe: universe });
    }
  }
  return merged;
}
