// Unit tests for ui/lib/state.js — URL state parse/serialize +
// view-mode resolution. Non-trivial cases only: validation contracts,
// multi-universe parsing, precedence rules, round-trip stability.
import { describe, it, expect } from "vitest";
import { parseState, serializeState, resolveViewMode } from "../lib/state.js";

const KNOWN = ["qte77-watchlist", "sp500", "eurostoxx", "federal-contractors"];

describe("parseState", () => {
  it("returns defaults for an empty query string", () => {
    const s = parseState("?", KNOWN);
    expect(s.view).toBe("simple");
    expect(s.universes).toEqual([]);
    expect(s.sortKey).toBeNull();
    expect(s.sortDir).toBe(-1);
    expect(s.filter).toBe("");
    expect(s.date).toBeNull();
    expect(s.sector).toBeNull();
    expect(s.ltFgWindow).toBe("all");
    expect(s.ycWindow).toBe("all");
  });

  it("parses chart time-window keys, defaulting unknown values to 'all'", () => {
    expect(parseState("?ltFgWindow=1y&ycWindow=5y", KNOWN).ltFgWindow).toBe("1y");
    expect(parseState("?ltFgWindow=1y&ycWindow=5y", KNOWN).ycWindow).toBe("5y");
    expect(parseState("?ltFgWindow=BOGUS", KNOWN).ltFgWindow).toBe("all");
    expect(parseState("?ycWindow=", KNOWN).ycWindow).toBe("all");
  });

  it("parses ?sector=Technology and treats an empty value as null", () => {
    expect(parseState("?sector=Technology", KNOWN).sector).toBe("Technology");
    expect(parseState("?sector=", KNOWN).sector).toBeNull();
  });

  it("falls through to default when view= is not 'simple' or 'detailed'", () => {
    expect(parseState("?view=BOGUS", KNOWN).view).toBe("simple");
    expect(parseState("?view=", KNOWN).view).toBe("simple");
  });

  it("parses multi-universe comma list filtered against the known whitelist", () => {
    const s = parseState("?universe=sp500,UNKNOWN,federal-contractors,,", KNOWN);
    expect(s.universes).toEqual(["sp500", "federal-contractors"]);
  });

  it("returns an empty universes list when none of the values are known", () => {
    expect(parseState("?universe=foo,bar", KNOWN).universes).toEqual([]);
  });

  it("preserves sortKey verbatim and validates sortDir to {-1, 1}", () => {
    const s = parseState("?sort=composite_scores.screener_score&sortDir=1", KNOWN);
    expect(s.sortKey).toBe("composite_scores.screener_score");
    expect(s.sortDir).toBe(1);
    expect(parseState("?sort=foo&sortDir=2", KNOWN).sortDir).toBe(-1);
    expect(parseState("?sort=foo&sortDir=abc", KNOWN).sortDir).toBe(-1);
  });

  it("rejects malformed dates and accepts ISO yyyy-mm-dd only", () => {
    expect(parseState("?date=2024-05-15", KNOWN).date).toBe("2024-05-15");
    expect(parseState("?date=2024/05/15", KNOWN).date).toBeNull();
    expect(parseState("?date=not-a-date", KNOWN).date).toBeNull();
    expect(parseState("?date=2024-13-99", KNOWN).date).toBeNull();
  });
});

describe("serializeState ↔ parseState round-trip", () => {
  it("survives a round-trip with non-default values", () => {
    const original = {
      view: /** @type {"simple" | "detailed"} */ ("detailed"),
      universes: ["sp500", "federal-contractors"],
      sortKey: "forward_pe",
      sortDir: /** @type {1 | -1} */ (1),
      filter: "tech",
      date: "2024-05-15",
      sector: "Technology",
      ltFgWindow: /** @type {import("../lib/state.js").WindowKey} */ ("5y"),
      ycWindow: /** @type {import("../lib/state.js").WindowKey} */ ("1y"),
    };
    const url = serializeState(original, "https://example.com/demo/");
    const reparsed = parseState(new URL(url).search, KNOWN);
    expect(reparsed).toEqual(original);
  });

  it("omits default-valued keys from the serialized query", () => {
    const minimal = {
      view: /** @type {"simple" | "detailed"} */ ("simple"),
      universes: [],
      sortKey: null,
      sortDir: /** @type {1 | -1} */ (-1),
      filter: "",
      date: null,
      sector: null,
      ltFgWindow: /** @type {import("../lib/state.js").WindowKey} */ ("all"),
      ycWindow: /** @type {import("../lib/state.js").WindowKey} */ ("all"),
    };
    const url = serializeState(minimal, "https://example.com/demo/");
    expect(new URL(url).search).toBe("");
  });
});

describe("resolveViewMode", () => {
  it("returns 'simple' when neither URL nor localStorage carry a value", () => {
    expect(resolveViewMode(null, null)).toBe("simple");
  });

  it("falls back to localStorage when URL is absent", () => {
    expect(resolveViewMode(null, "detailed")).toBe("detailed");
  });

  it("treats URL as authoritative over localStorage when both are valid", () => {
    expect(resolveViewMode("simple", "detailed")).toBe("simple");
  });

  it("falls through to localStorage when URL value is invalid", () => {
    expect(resolveViewMode("BOGUS", "detailed")).toBe("detailed");
    expect(resolveViewMode("BOGUS", null)).toBe("simple");
  });
});
