### Fixed

- `south-america` universe (#312): three members had returned no data since their symbols were
  retired ("Quote not found for symbol"), not because of an upstream Yahoo outage as first
  diagnosed. Replaced with their successor lines, each probed 3/3 on yfinance 1.7.0:
  `EMBR3.SA` → `EMBJ3.SA` (Embraer), `ELET3.SA` → `AXIA3.SA` (Eletrobras, now AXIA Energia),
  `JBSS3.SA` → `JBS` (JBS N.V. on the NYSE; its B3 BDR `JBSS32.SA` quotes BRL against USD
  financials, which would distort P/E). `JBS` joins the backtest's known non-US issuers, so it
  always gets the 120-day filing lag.
