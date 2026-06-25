### Changed

- **Dashboard adopts the qte77 EyeRest brand theming, aligned with the sibling
  paperverse + agentic-job-offer-to-application-kit dashboards.** CSS tokens are
  renamed to the brand-canonical names (`--surface` / `--text-muted` / `--primary`,
  plus a new `--primary-on`) and the light/dark cascade moves to `html[data-theme]`,
  set by a new repo-local `ui/theme.js` that mirrors `qte77.github.io/assets/theme.js`:
  one cycling `◐/○/●` button, `localStorage["qte77-theme"]`, a `themechange` event that
  recolours the charts, a dynamic `aria-label` + `#theme-status` live region,
  `prefers-reduced-motion`, and a `<head>` anti-FOUC guard. The data arc re-tones per
  theme, so rating-chip text uses `--primary-on` to keep contrast in both modes. The old
  `lib/theme.js` + its test are removed (the toggle logic now lives in `ui/theme.js`).
- **Theme toggle no longer writes `?theme=` to the URL on click** — it reads `?theme=`
  on load (deep-links still work) and persists the choice to `localStorage`.
