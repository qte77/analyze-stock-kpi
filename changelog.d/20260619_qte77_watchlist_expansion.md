### Changed

- **qte77 watchlist expanded to 100 symbols (+27).** Added Allianz (`ALV.DE`),
  Deckers (`DECK`), Enel (`ENEL.MI`), Comfort Systems (`FIX`), Intl Container
  Terminal Services (`ICTEF`), InterDigital (`IDCC`), Louisiana-Pacific (`LPX`),
  Moody's (`MCO`), Meta (`META`), Monster Beverage (`MNST`), Monolithic Power
  (`MPWR`), NetEase (`NTES`), Qualcomm (`QCOM`), REA Group (`REA.AX`), Sezzle
  (`SEZL`), Sterling Infrastructure (`STRL`), TSMC (`TSM`), Clear Secure (`YOU`),
  SK hynix (`000660.KS`), Zhejiang NHU (`002001.SZ`), kakaku.com (`2371.T`),
  Realtek (`2379.TW`), MediaTek (`2454.TW`), Evergreen Marine (`2603.TW`), Yutong
  Bus (`600066.SS`), Organo (`6368.T`) and Advantest (`6857.T`). Each symbol was
  verified against the yfinance KPI surfaces the screener reads
  (`.info` / `.income_stmt` / `.cashflow`); inline `# Name` comments document the
  cryptic international codes. SK hynix is the lone partial — Yahoo omits a ROIC
  input so that one composite stays `None`; all other KPIs populate.
