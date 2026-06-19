### Changed

- **Theme toggle is now a single cycler button instead of the 3-button
  segmented control.** One click advances system → light → dark → system;
  the button shows the active mode as an `<icon> <word>` label so it stays
  glanceable. "System" (follow OS) remains a reachable state, and the
  `?theme=` URL + `localStorage` persistence is unchanged. A visually
  hidden `aria-live="polite"` status region announces each change to
  screen readers, since focus stays on the button after a click.

### Fixed

- **No more flash-of-wrong-theme on load for an explicit light/dark
  override.** An inline guard in `<body>` resolves the theme (URL >
  `localStorage` > system) and sets the body class before first paint,
  instead of waiting for the deferred `app.js` module.
