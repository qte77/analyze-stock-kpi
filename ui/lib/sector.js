// @ts-check
// Sector aggregation for the universe-header donut (B3). Pure: takes
// snapshot rows, returns a Map sorted desc-by-count with alphabetical
// tiebreak so the donut's largest slice is always first and renders
// stay deterministic across reloads. Tested by tests/demo/sector.test.mjs.

const NULL_BUCKET = "—";

/** Neutral grey for the null bucket and unknown sectors. Matches the
 *  dark-theme --muted token so the slice blends gracefully in both
 *  themes without looking like a real GICS sector. */
const NEUTRAL = "#98989D";

/**
 * GICS sector palette tuned for both light (#ffffff) and dark (#2c2c2e)
 * panels. Tableau-10-Muted-derived: ~55% saturation, ~55% lightness so
 * the slices stay readable without feeling neon. Technology +
 * Communication Services use EyeRest brand tokens (amber / data-alt)
 * in place of their former blues so the donut stays zero-blue.
 * yfinance returns the long-form GICS names below verbatim — keys
 * match those strings.
 *
 * @type {Readonly<Record<string, string>>}
 */
export const SECTOR_COLORS = Object.freeze({
  Technology: "#c06010",
  Healthcare: "#6ACC64",
  "Financial Services": "#D5BB67",
  "Consumer Cyclical": "#EE854A",
  "Consumer Defensive": "#956CB4",
  "Communication Services": "#587818",
  Industrials: "#8C613C",
  Energy: "#D65F5F",
  Utilities: "#DC7EC0",
  "Basic Materials": "#B47CC7",
  "Real Estate": "#5FAB87",
  [NULL_BUCKET]: NEUTRAL,
});

/**
 * Look up the donut slice color for one sector label. Unknown sectors
 * (anything outside the GICS 11 + null bucket) fall back to the neutral
 * grey rather than throwing — the donut should never render a blank
 * slice on an unexpected input.
 *
 * @param {string} name
 * @returns {string}
 */
export function sectorColor(name) {
  return SECTOR_COLORS[name] ?? NEUTRAL;
}

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
  const entries = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  return new Map(entries);
}
