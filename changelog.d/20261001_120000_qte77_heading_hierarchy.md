### Changed

- Dashboard: "Today's picks" is now "Latest picks · updated `<date>`" (and "Latest picks"
  wherever the text names it), so a stale snapshot never reads as today's.
- Dashboard: every top-level section is a collapsible with an `h2` title. "Genuine decisions"
  (series A) is collapsible and open on load; "Reconstructed backfill" (series B) moved out of
  "How it's tested" into its own top-level section, closed on load; Methodology is collapsible,
  closed on load, and in-page links into it (e.g. `#backtest-rules`) open it first.
- Dashboard: one heading level and font size per tier: `h2` for the six top sections, `h3`
  inside them, `h4` one level deeper (previously four different sizes at the second level).
