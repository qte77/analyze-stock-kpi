// Unit tests for ui/lib/theme.js — theme resolution + URL/storage
// precedence. Non-trivial cases only: invalid values fall through,
// URL beats localStorage, default is "system".
import { describe, it, expect } from "vitest";
import { resolveTheme, isThemeMode, nextTheme } from "../lib/theme.js";

describe("isThemeMode", () => {
  it("accepts only the three valid mode strings", () => {
    expect(isThemeMode("system")).toBe(true);
    expect(isThemeMode("light")).toBe(true);
    expect(isThemeMode("dark")).toBe(true);
  });

  it("rejects unknown / malformed / empty / null inputs", () => {
    expect(isThemeMode("auto")).toBe(false);
    expect(isThemeMode("")).toBe(false);
    expect(isThemeMode(null)).toBe(false);
    expect(isThemeMode(undefined)).toBe(false);
    expect(isThemeMode("DARK")).toBe(false); // case-sensitive
  });
});

describe("resolveTheme", () => {
  it("returns 'system' when neither URL nor localStorage carry a value", () => {
    expect(resolveTheme(null, null)).toBe("system");
  });

  it("treats URL as authoritative over localStorage when both are valid", () => {
    expect(resolveTheme("light", "dark")).toBe("light");
  });

  it("falls back to localStorage when URL is absent", () => {
    expect(resolveTheme(null, "dark")).toBe("dark");
  });

  it("falls through to localStorage when URL value is invalid", () => {
    expect(resolveTheme("BOGUS", "dark")).toBe("dark");
  });

  it("falls through to the system default when both URL and localStorage are invalid", () => {
    expect(resolveTheme("BOGUS", "ALSO_BOGUS")).toBe("system");
  });
});

describe("nextTheme", () => {
  it("advances system → light → dark", () => {
    expect(nextTheme("system")).toBe("light");
    expect(nextTheme("light")).toBe("dark");
  });

  it("wraps dark back to system", () => {
    expect(nextTheme("dark")).toBe("system");
  });
});
