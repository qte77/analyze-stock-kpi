// Unit tests for docs/demo/lib/csv.js — RFC 4180-shaped CSV exporter.
// Non-trivial cases only: the four escape edges (comma, double-quote,
// newline, null/undefined) + header alignment.
import { describe, it, expect } from "vitest";
import { exportCsv } from "../../docs/demo/lib/csv.js";

describe("exportCsv", () => {
  it("emits the header row before any data rows", () => {
    const out = exportCsv([{ a: 1, b: 2 }], ["a", "b"]);
    expect(out.split("\n")[0]).toBe("a,b");
  });

  it("quotes and doubles internal double-quotes per RFC 4180", () => {
    const out = exportCsv([{ name: 'BERKSHIRE "B" SHARES' }], ["name"]);
    expect(out).toBe('name\n"BERKSHIRE ""B"" SHARES"');
  });

  it("quotes any field containing a comma", () => {
    const out = exportCsv([{ name: "Apple, Inc." }], ["name"]);
    expect(out).toBe('name\n"Apple, Inc."');
  });

  it("quotes any field containing a newline (preserves embedded \\n inside the cell)", () => {
    const out = exportCsv([{ note: "line1\nline2" }], ["note"]);
    // Header + one quoted multi-line cell. The embedded newline stays as \n.
    expect(out).toBe('note\n"line1\nline2"');
  });

  it("renders null and undefined as the empty cell (no string 'null')", () => {
    const out = exportCsv(
      [{ a: null, b: undefined, c: 0 }],
      ["a", "b", "c"],
    );
    expect(out).toBe("a,b,c\n,,0");
  });

  it("honours the headers array's order, ignoring extra keys on the rows", () => {
    const out = exportCsv(
      [{ extra: "ignored", b: 2, a: 1 }],
      ["a", "b"],
    );
    expect(out).toBe("a,b\n1,2");
  });
});
