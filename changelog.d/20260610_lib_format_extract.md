### Changed

- **`docs/demo/lib/format.js`: extract the pure value formatters + comparator (`nested`, `fmtNum`, `fmtPct`, `compareValues`) out of `app.js` into a unit-tested module.** Adds `tests/demo/format.test.mjs` covering dotted-key access (incl. missing segments / nullish root), `fmtNum` null/NaN/precision, `fmtPct` null plus its intentional no-NaN-guard behaviour, and `compareValues` nulls-last-regardless-of-direction + string/number ordering. `td()` stays in `app.js` (DOM glue). Behaviour-preserving; prerequisite for the upcoming `table.js` / `detail.js` concern splits.
