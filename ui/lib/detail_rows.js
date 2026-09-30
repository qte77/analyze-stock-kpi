// @ts-check
// Pure detail-panel data for the demo dashboard: the KPI glossary text and
// the row-tuple builders for the federal-contracts audit block + external
// links. DOM-free; side-effect-free. The showDetail() DOM rendering that
// consumes these tuples lives in ui/app.js (it stays there — it is
// knotted with the shared chart infra). Tested by tests/demo/detail_rows.test.mjs.

import { formatObligated } from "./audit.js";
import { fmtNum, fmtPct } from "./format.js";

export const KPI_GLOSSARY = {
  forward_pe: "Forward P/E = price / next-12mo EPS estimate. Lower = cheaper.",
  trailing_pe: "Trailing P/E = price / past-12mo EPS. Lower = cheaper.",
  trail_fwd_pe:
    "Trailing P/E divided by Forward P/E. >1 = EPS growth expected; <1 = EPS contraction expected.",
  trailing_peg_ratio:
    "Trailing PEG = P/E adjusted for historical earnings growth. Lower better; <1 is the classic Peter Lynch threshold.",
  beta: "5y market sensitivity. <1 = less volatile than market.",
  rd_to_revenue: "R&D expense / total revenue (latest annual income statement). EQUITY-only.",
  operating_margins:
    "Operating income / revenue. Pre-tax, pre-interest — comparable across countries.",
  gross_margins: "(Revenue - COGS) / revenue. Pricing power / cost discipline.",
  profit_margins: "Net margin = net income / revenue. Bottom-line efficiency after tax + interest.",
  return_on_equity:
    "ROE = net income / equity. Profitability per equity dollar; sensitive to leverage.",
  return_on_assets:
    "ROA = net income / total assets. Leverage-neutral profitability per asset dollar.",
  roi: "Simplified ROIC = NetIncome / (BookEquity + TotalDebt - TotalCash). Screener-style; not company-filed ROIC.",
  current_ratio:
    "Current assets / current liabilities. Short-term liquidity (>1 = assets cover liabilities).",
  quick_ratio:
    "(Current assets - inventory) / current liabilities. Stricter liquidity than Current.",
  debt_to_equity: "Total debt / equity. Leverage (higher = more leveraged).",
  sortino_ratio: "Annualized Sortino over 1y (rf=0). Higher = better upside vs downside skew.",
  sortino_3y:
    "Annualized Sortino over the trailing 3y (rf=0), informational only — not a composite input. Blank unless price history reaches back far enough.",
  sortino_5y:
    "Annualized Sortino over the trailing 5y (rf=0), informational only — not a composite input. Blank unless price history reaches back far enough.",
  sortino_10y:
    "Annualized Sortino over the trailing 10y (rf=0), informational only — not a composite input. Blank unless price history reaches back far enough.",
  sortino_20y:
    "Annualized Sortino over the trailing 20y (rf=0), informational only — not a composite input. Blank unless price history reaches back far enough.",
  sortino_30y:
    "Annualized Sortino over the trailing 30y (rf=0), informational only — not a composite input. Blank unless price history reaches back far enough.",
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

/** Composite-score labels, shared by the panel's list and its radar (#426). */
export const COMPOSITE_LABELS = /** @type {const} */ ({
  quality: "Quality",
  dividend: "Dividend",
  growth: "Growth",
  big_call: "Big Call",
  aaqs: "AAQS",
  hgi: "HGI",
  screener_score: "qte77 Score",
});

/**
 * Plan 010 D7: the panel's KPI rows in the qte77 Score's four factors, in the
 * Score tooltip's order. Each factor's Score inputs come first (see
 * `screener_score` in src/analyze_stock_kpi/domain/composite_scores.py), then
 * the related KPIs the Score doesn't use.
 *
 * @param {Row} row
 * @returns {Array<{title: string, rows: Array<[string, string, boolean?, string?]>}>}
 */
export function kpiGroups(row) {
  const trail = row.trailing_pe;
  const fwd = row.forward_pe;
  const trailFwd = trail != null && fwd != null && fwd !== 0 ? (trail / fwd).toFixed(2) : "—";
  return [
    {
      title: "Profitability",
      rows: [
        [
          "ROE / ROA",
          `${fmtPct(row.return_on_equity)} % / ${fmtPct(row.return_on_assets)} %`,
          false,
          KPI_GLOSSARY.return_on_equity,
        ],
        ["Op margin %", fmtPct(row.operating_margins), false, KPI_GLOSSARY.operating_margins],
        ["R&D / Revenue %", fmtPct(row.rd_to_revenue), false, KPI_GLOSSARY.rd_to_revenue],
        ["Gross margin %", fmtPct(row.gross_margins), false, KPI_GLOSSARY.gross_margins],
        ["Net margin %", fmtPct(row.profit_margins), false, KPI_GLOSSARY.profit_margins],
        ["ROI", fmtPct(row.roi), false, KPI_GLOSSARY.roi],
      ],
    },
    {
      title: "Valuation",
      rows: [
        [
          "Trail / Fwd P/E",
          `${fmtNum(row.trailing_pe, 2)} / ${fmtNum(row.forward_pe, 2)}`,
          false,
          KPI_GLOSSARY.trailing_pe,
        ],
        [
          "PEG (trailing)",
          fmtNum(row.trailing_peg_ratio, 2),
          false,
          KPI_GLOSSARY.trailing_peg_ratio,
        ],
        ["Trail/Fwd P/E ratio", trailFwd, false, KPI_GLOSSARY.trail_fwd_pe],
        ["P/B / P/S TTM", `${fmtNum(row.price_to_book, 2)} / ${fmtNum(row.price_to_sales_ttm, 2)}`],
        ["Div yield / Payout", `${fmtPct(row.dividend_yield)} % / ${fmtPct(row.payout_ratio)} %`],
      ],
    },
    {
      title: "Risk",
      rows: [
        ["Beta", fmtNum(row.beta, 2), false, KPI_GLOSSARY.beta],
        ["Current ratio", fmtNum(row.current_ratio, 2), false, KPI_GLOSSARY.current_ratio],
        ["Quick ratio", fmtNum(row.quick_ratio, 2), false, KPI_GLOSSARY.quick_ratio],
        ["D/E", fmtNum(row.debt_to_equity, 2), false, KPI_GLOSSARY.debt_to_equity],
      ],
    },
    {
      title: "Momentum",
      rows: [
        ["Sortino 1y (rf=0)", fmtNum(row.sortino_ratio, 2), false, KPI_GLOSSARY.sortino_ratio],
        ["Sortino 3y", fmtNum(row.sortino_3y, 2), false, KPI_GLOSSARY.sortino_3y],
        ["Sortino 5y", fmtNum(row.sortino_5y, 2), false, KPI_GLOSSARY.sortino_5y],
        ["Sortino 10y", fmtNum(row.sortino_10y, 2), false, KPI_GLOSSARY.sortino_10y],
        ["Sortino 20y", fmtNum(row.sortino_20y, 2), false, KPI_GLOSSARY.sortino_20y],
        ["Sortino 30y", fmtNum(row.sortino_30y, 2), false, KPI_GLOSSARY.sortino_30y],
        ["Revenue growth", `${fmtPct(row.revenue_growth)} %`],
        ["Earnings growth", `${fmtPct(row.earnings_growth)} %`],
        [
          "52w high / low",
          `$${fmtNum(row.fifty_two_week_high, 2)} / $${fmtNum(row.fifty_two_week_low, 2)}`,
        ],
      ],
    },
  ];
}

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
