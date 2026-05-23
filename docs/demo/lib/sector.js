// @ts-check
// Sector aggregation for the universe-header donut (B3). Pure: takes
// snapshot rows, returns a Map sorted desc-by-count with alphabetical
// tiebreak so the donut's largest slice is always first and renders
// stay deterministic across reloads. Tested by tests/demo/sector.test.mjs.

const NULL_BUCKET = "—";

/**
 * @param {Array<{sector?: string | null}>} rows
 * @returns {Map<string, number>}
 */
export function aggregateSectors(rows) {
  /** @type {Map<string, number>} */
  const counts = new Map();
  for (const row of rows) {
    const sector = row.sector ?? NULL_BUCKET;
    counts.set(sector, (counts.get(sector) ?? 0) + 1);
  }
  const entries = [...counts.entries()].sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
  );
  return new Map(entries);
}
