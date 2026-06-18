### Added

- Self-hosted brand typography for the demo dashboard — **Inter** (UI/prose)
  and **JetBrains Mono** (numeric table cells + `<code>`), per the qte77
  EyeRest design tokens (#295). Latin TTF subsets ship in `ui/fonts/` (SIL OFL 1.1,
  `ui/fonts/OFL.txt`) with `font-display: swap` and the prior system stack as
  fallback — no third-party font CDN request.
- Adopted the qte77 brand mark (`logo-mark.paths.dejavu.svg`) as the demo
  dashboard favicon, replacing the bespoke radar SVG (#295).
