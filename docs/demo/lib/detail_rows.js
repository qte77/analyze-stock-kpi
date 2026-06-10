// @ts-check
// Pure detail-panel data for the demo dashboard: the KPI glossary text and
// the row-tuple builders for the federal-contracts audit block + external
// links. DOM-free; side-effect-free. The showDetail() DOM rendering that
// consumes these tuples lives in docs/demo/app.js (it stays there — it is
// knotted with the shared chart infra). Tested by tests/demo/detail_rows.test.mjs.

import { formatObligated } from "./audit.js";

export const KPI_GLOSSARY = {
  forward_pe: "Forward P/E = price / next-12mo EPS estimate. Lower = cheaper.",
  trailing_pe: "Trailing P/E = price / past-12mo EPS. Lower = cheaper.",
  trail_fwd_pe:
    "Trailing P/E divided by Forward P/E. >1 = EPS growth expected; <1 = EPS contraction expected.",
  trailing_peg_ratio:
    "Trailing PEG = P/E adjusted for historical earnings growth. Lower better; <1 is the classic Peter Lynch threshold.",
  beta: "5y market sensitivity. <1 = less volatile than market.",
  rd_to_revenue:
    "R&D expense / total revenue (latest annual income statement). EQUITY-only.",
  operating_margins:
    "Operating income / revenue. Pre-tax, pre-interest — comparable across countries.",
  gross_margins: "(Revenue - COGS) / revenue. Pricing power / cost discipline.",
  profit_margins:
    "Net margin = net income / revenue. Bottom-line efficiency after tax + interest.",
  return_on_equity:
    "ROE = net income / equity. Profitability per equity dollar; sensitive to leverage.",
  return_on_assets:
    "ROA = net income / total assets. Leverage-neutral profitability per asset dollar.",
  roi:
    "Simplified ROIC = NetIncome / (BookEquity + TotalDebt - TotalCash). Screener-style; not company-filed ROIC.",
  current_ratio:
    "Current assets / current liabilities. Short-term liquidity (>1 = assets cover liabilities).",
  quick_ratio:
    "(Current assets - inventory) / current liabilities. Stricter liquidity than Current.",
  debt_to_equity: "Total debt / equity. Leverage (higher = more leveraged).",
  sortino_ratio:
    "Annualized Sortino over 1y (rf=0). Higher = better upside vs downside skew.",
  screener_score:
    "qte77 Score — factor-weighted mean of 4 thematic groups: Profitability (>=2/4 inputs); Valuation (>=1/2); Risk (>=1/2); Momentum (1/1). Higher = better.",
  quality:
    "Mean of normalized ROE, ROA, operating margin, and inverted D/E. Higher = stronger fundamentals.",
  dividend:
    "Dividend yield + payout-ratio sweet spot (peaks near ~50% payout). Higher = healthier dividend profile.",
  growth:
    "Mean of normalized revenue + earnings growth. Higher = stronger top-line and bottom-line growth.",
  big_call:
    "Weighted Quality (40%) + Dividend (30%) + Growth (30%); reweights proportionally when a component is missing.",
  aaqs: "Quality combined with low-volatility (low beta is better).",
  hgi: "Growth-tilted score with a fixed bonus when operating margin clears ~10%.",
};

/**
 * @param {AuditRow | null} audit
 * @returns {Array<[string, string, boolean?, string?]>}
 */
export function auditDetailRows(audit) {
  if (!audit) return [];
  return [
    ["Federal Contracts", "", true],
    ["Obligated $", formatObligated(audit.obligated_usd)],
    ["UEI", audit.uei ?? "—"],
    [
      "EDGAR match",
      audit.edgar_match_score == null
        ? "—"
        : `${(Number(audit.edgar_match_score) * 100).toFixed(0)} %`,
      false,
      "SequenceMatcher score of the audit's recipient name against EDGAR's issuer title. Higher = more confident.",
    ],
    ["Recipient name", audit.recipient_name ?? "—"],
  ];
}

/**
 * @param {Row} row
 * @returns {Array<[string, string]>}
 */
export function externalLinkRows(row) {
  if (!row.symbol) return [];
  const sym = encodeURIComponent(row.symbol);
  return [
    ["Yahoo", `https://finance.yahoo.com/quote/${sym}`],
    ["SEC EDGAR", `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${sym}`],
    [
      "Wikipedia",
      `https://en.wikipedia.org/wiki/Special:Search?search=${encodeURIComponent(
        row.long_name ?? row.symbol,
      )}`,
    ],
  ];
}
