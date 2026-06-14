# ADR-0001 — Defer `financetoolkit` to v0.5.0 (#18)

**Status:** Accepted (2026-05-10)

**Amends:** [ADR-0000](0000-remove-traderfox.md) §Decision (fundamentals stack)

**Drives:** [#18](https://github.com/qte77/analyze-stock-kpi/issues/18)

**Amended by:** [ADR-0002](0002-simplified-composites.md) §Accepted risks (simplified composite formulas chosen; `financetoolkit` was not added)

## Context

ADR-0000 specified `yfinance + financetoolkit` for the new fundamentals layer. While planning PR 1D (#28), `context7` MCP research surfaced three findings:

- `yf.Ticker(t).info` already exposes ~30 ratios needed for the v0.4.0 `FundamentalsSnapshot` (P/E, P/B, ROE, ROA, margins, debt/equity, growth, dividend yield, etc.) — so FT adds zero v0.4.0 KPI surface
- `financetoolkit` requires a Financial Modeling Prep API key by default (free tier signup needed); a no-key mode exists via `enforce_source="YahooFinance"` but it double-fetches statements that yfinance has already returned
- Adding `financetoolkit` brings ~15 transitive deps (pandas, plotly, etc.), most of which are already in our tree via yfinance but a few (plotly) are pure additions

## Decision

Defer the `financetoolkit` dependency to v0.5.0 (the #18 composites PR). PR 1D (#28) shipped yfinance-only.

## Consequences

**Won:**

- v0.4.0 has one fewer direct dep + lighter transitive surface (no plotly)
- Single fetch path per ticker (no double-fetch via FT)
- Decision is reversible in one line of `pyproject.toml`

**Lost:**

- Pre-built Piotroski / ROIC formulas — must be re-implemented or pulled in via FT when v0.5.0 needs them

**Accepted risks:**

- If `yf.Ticker.info` ratios prove insufficient for the v0.5.0 composite formulas, the #18 PR will add `financetoolkit>=2.0` (1 line). This ADR will then be amended again or marked superseded.

## Alternatives considered

- **Add FT now in YF-only mode (`enforce_source="YahooFinance"`).** Rejected: YAGNI; transitive cost (plotly etc.) for unused capability; double-fetch overhead.
- **Vendor a few ratio formulas from FT into our codebase.** Rejected: maintenance burden; FT is the cleaner dependency if v0.5.0 actually needs the formulas.
- **Add FT later as part of #18 (this ADR).** Accepted.

## References

- [PR #28](https://github.com/qte77/analyze-stock-kpi/pull/28) — v0.4.0 fundamentals shipped yfinance-only
- [`/jerbouma/financetoolkit`](https://github.com/jerbouma/financetoolkit) (context7 ID)
- [ADR-0000](0000-remove-traderfox.md) — original library-stack decision being amended
