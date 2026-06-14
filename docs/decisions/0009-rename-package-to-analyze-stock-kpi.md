# ADR-0009 — Rename the import package `src` → `analyze_stock_kpi`

**Status:** Accepted (2026-06-14)

**Relates to:**
[ADR-0007](0007-package-vs-infrastructure-boundary.md) — implements the
"Rename `src/` → `analyze_stock_kpi/`" refactor candidate flagged in its
§Consequences; the Scope-1 wheel boundary is unchanged (still the package
directory + bundled presets), only its name + path move.
[ADR-0008](0008-ui-promotion-to-ui.md) — sequencing-independent (top-level
`ui/` is clean before and after); confirmed out-of-scope there.

## Context

The importable package has always been named `src` — a layout artifact, not an
identity. Downstream consumers must write `from src.X import Y`, which is
unidiomatic (every project's source directory is `src`) and at odds with the
src-layout convention. ADR-0007 flagged the rename as a deferred candidate
"blocked by ~30 import sites in production code + tests … warrants its own ADR +
PR." The actual blast radius is ~228 references (imports, monkeypatch string
targets, docstrings, tool config, workflow paths, doc links). The PyPI
distribution name is already `analyze-stock-kpi`; only the import namespace lags.

## Decision

Adopt a **src-layout**: the package lives at `src/analyze_stock_kpi/` and is
imported as `analyze_stock_kpi`.

1. Move every `src/*` module + subpackage + the `assets/` presets into
   `src/analyze_stock_kpi/`; `src/` remains the layout root (not a package).
2. Add `src/analyze_stock_kpi/__init__.py` (the package had none) and the
   previously-missing `src/analyze_stock_kpi/utils/__init__.py`.
3. Rewrite `from src.X` → `from analyze_stock_kpi.X` (relative imports unchanged);
   the CLI invocation `python -m src` → `python -m analyze_stock_kpi`.
4. `pyproject.toml` `[tool.hatch.build.targets.wheel].packages` →
   `["src/analyze_stock_kpi"]`; coverage source → `analyze_stock_kpi`.
5. The PyPI distribution name `analyze-stock-kpi` is unchanged;
   `__version__.py`'s `version("analyze-stock-kpi")` is unaffected (keyed to the
   distribution name, not the import path).

## Consequences

- **Breaking import change.** Any consumer importing `src.X` must switch to
  `analyze_stock_kpi.X`. The distribution name, CLI behaviour, and public API
  surface are otherwise unchanged.
- **Scope-1 boundary (ADR-0007) intact.** The wheel still ships exactly the
  package directory + bundled presets; only the name + path moved. Rules 1/2 hold.
- **Idiomatic src-layout.** `import analyze_stock_kpi` resolves after an editable
  install (`uv sync`); running from a checkout uses `python -m analyze_stock_kpi`
  against that install, not a CWD-relative `src` directory.
- **Assets stay package-relative.** `PRESET_DIR` resolves via
  `Path(__file__).parent.parent` → `src/analyze_stock_kpi/assets/universes/`; no
  code change.

## References

- pyproject.toml `[tool.hatch.build.targets.wheel].packages` — `["src"]` →
  `["src/analyze_stock_kpi"]` (the wheel-scope line).
- pyproject.toml `[project].name = "analyze-stock-kpi"` — distribution name
  unchanged; only the import namespace changes.
- `src/analyze_stock_kpi/__version__.py` — `version("analyze-stock-kpi")`
  unaffected (metadata key = distribution name).
- [ADR-0007](0007-package-vs-infrastructure-boundary.md) — the three-scope model
  and the refactor candidate this ADR resolves.
- [ADR-0008](0008-ui-promotion-to-ui.md) — confirms sequencing independence.
