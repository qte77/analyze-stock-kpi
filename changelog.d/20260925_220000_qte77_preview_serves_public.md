### Fixed

- `make preview` and `make preview_local` now use Vite's dev server, which serves `ui/public/`
  (vendored Chart.js, favicon), so charts render locally (#415). The dashboard URL is now
  `http://localhost:8000/analyze-stock-kpi/`; `preview_local` prints its own URL, which reads the
  local `results/` through Vite's `/@fs/` route (dev server only).
