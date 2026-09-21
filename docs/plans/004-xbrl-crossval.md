# Plan — XBRL cross-validation of yfinance financials

Issue [#101](https://github.com/qte77/analyze-stock-kpi/issues/101) · status: **shipped**
(PR [#373](https://github.com/qte77/analyze-stock-kpi/pull/373)) — implemented per the
source-verified design in
[006-agent-ready-backlog.md § 2](006-agent-ready-backlog.md) (supersedes this file's original
companyfacts/3–5-concept draft below). `src/analyze_stock_kpi/data_sources/sec/xbrl.py`
cross-validates yfinance revenue / net-income / EPS against SEC XBRL `companyconcept` data via
`enrich_snapshot_xbrl`, attaching `sec_revenue_delta_pct` / `sec_net_income_delta_pct` /
`sec_eps_delta_pct` to every `FundamentalsSnapshot`. `total_revenue` / `net_income_to_common`
promoted to permanent snapshot fields; no stored boolean mismatch flag (consumers threshold
the stored float themselves).

## Context

yfinance fundamentals can be stale or wrong. SEC **XBRL** company facts
(`data.sec.gov/api/xbrl/companyfacts/CIK{10}.json`) are authoritative for US filers.
Cross-validate a few headline fields and flag discrepancies on the snapshot, so the
dossier is auditable.

## Approach

Reuse the EDGAR plumbing already in place (`src/analyze_stock_kpi/data_sources/sec/` —
the CIK resolver + the conditional-GET / disk-cache `_fetch_json`). Add an XBRL
companyfacts fetch, map a handful of US-GAAP concepts to existing `FundamentalsSnapshot`
fields, compare within a tolerance, and attach a discrepancy flag. EQUITY US filers
only; others bypass (like the SEC last-filed enrichment).

## Steps

1. `src/analyze_stock_kpi/data_sources/sec/xbrl.py` — fetch + parse companyfacts (latest
   annual value per concept).
2. Map ~3–5 concepts (e.g. `Revenues`, `NetIncomeLoss`, `StockholdersEquity`) → snapshot fields.
3. Compare within a tolerance; attach an optional `xbrl_mismatch` detail post-fetch,
   like `enrich_snapshot_sec`.
4. Strict TDD (the SEC modules are unit-tested); live test tagged `@pytest.mark.network`.

## Open questions

- Which concepts/fields, and what tolerance? Units + scaling differ between yfinance + XBRL.
- Surface in the rich table / dashboard, or snapshot-only for now?

## References

- [#101](https://github.com/qte77/analyze-stock-kpi/issues/101); [ADR-0006](../decisions/0006-federal-contractors-universe.md) (EDGAR plumbing); roadmap "Deferred EDGAR product use cases".
- `src/analyze_stock_kpi/data_sources/sec/{cik_map,submissions}.py`.
