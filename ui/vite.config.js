import { defineConfig } from "vite";

// GitHub Pages project site → https://qte77.github.io/analyze-stock-kpi/.
// `base` scopes the built asset + public URLs under that subpath (the old raw
// copy worked because every reference was relative; bundled asset URLs are
// root-absolute, so they need the base).
//
// Vite bundles only the app JS (entry: index.html → app.js) and the CSS
// (style.css, with its ui/fonts/*.ttf @font-face assets hashed in). Everything
// served verbatim lives in public/: the vendored Chart.js / Fuse.js UMD globals
// (loaded as classic <script> tags), favicon.svg, and universes.json (fetched
// at runtime). The dashboard's data still loads at runtime from the `data`
// branch (raw.githubusercontent.com, absolute URLs) — never bundled (ADR-0010).
export default defineConfig({
  base: "/analyze-stock-kpi/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
