### Fixed

- **`sp500` universe: `BRK.B` → `BRK-B`.** Yahoo / yfinance uses a hyphen for
  Berkshire Hathaway's Class B share-class symbol; the dotted `BRK.B` resolves to
  all-null KPI rows (verified `0/3` on retry-probe vs `BRK-B` `3/3`). The qte77
  watchlist already used `BRK-B`; this aligns `sp500.txt`. The other empty-data
  symbols from the same audit (`MMC`, latam `.SA` lines and their ADRs `ERJ` /
  `EBR`) are an upstream yfinance `quoteSummary` issue, not symbol errors —
  tracked in #312.
