// @ts-check
// RFC 4180-shaped CSV exporter for the demo dashboard's "download
// visible view" button (A3). Pure: takes rows + a header order, returns
// a string. The DOM-side Blob URL + click trigger live in app.js.
// Tested by tests/demo/csv.test.mjs.

const NEEDS_QUOTING_RE = /[",\n]/;

/**
 * Escape one field value for inclusion in a CSV row.
 * @param {unknown} value
 * @returns {string}
 */
function escapeField(value) {
  if (value == null) return "";
  const s = String(value);
  if (!NEEDS_QUOTING_RE.test(s)) return s;
  return `"${s.replaceAll('"', '""')}"`;
}

/**
 * Serialise `rows` into a CSV string with the given header order.
 * Extra keys present on rows but absent from `headers` are dropped;
 * keys present in `headers` but absent on a row render as empty cells.
 *
 * @param {Record<string, unknown>[]} rows
 * @param {string[]} headers
 * @returns {string}
 */
export function exportCsv(rows, headers) {
  const lines = [headers.join(",")];
  for (const row of rows) {
    lines.push(headers.map((h) => escapeField(row[h])).join(","));
  }
  return lines.join("\n");
}
