// Type declarations for the dashboard's snapshot shape.
//
// Mirrors `src/composite_scores.CompositeScores` and the subset of
// `src/fundamentals.FundamentalsSnapshot` fields the dashboard actually
// reads. Declaration-only — TypeScript auto-discovers these via the
// `include` list in `tsconfig.json`. Never shipped to the browser:
// GitHub Pages serves only `app.js`.

// Vendored library globals (Chart.js + Fuse.js are loaded via plain
// <script> tags in index.html, not module imports). `any` is the YAGNI
// choice: we use a tiny subset of each library's API. Upgrade to proper
// types if/when the surface grows.
declare const Chart: any;
declare const Fuse: any;

// Demo v2 (#134) view-mode toggle.
type ViewMode = "simple" | "detailed";

// Theme toggle: system follows `prefers-color-scheme`, light/dark force
// the palette regardless of OS preference.
type ThemeMode = "system" | "light" | "dark";

// A1 conditional cell coloring threshold per KPI.
interface KpiThreshold {
  lowerBetter: boolean;
  good: number;
  bad: number;
}

interface CompositeScores {
  quality?: number | null;
  dividend?: number | null;
  growth?: number | null;
  big_call?: number | null;
  aaqs?: number | null;
  hgi?: number | null;
  screener_score?: number | null;
}

// Mirrors `src/analyze_stock_kpi/orchestrators/federal_contractors.AuditRow`. All fields
// optional because the dashboard treats missing fields as a degraded
// reading rather than an error (the audit JSON may evolve faster than
// this declaration). `final_ticker` is the join key onto `Row.symbol`.
interface AuditRow {
  rank?: number | null;
  recipient_name?: string | null;
  uei?: string | null;
  obligated_usd?: number | null;
  candidate_ticker?: string | null;
  edgar_match_score?: number | null;
  yfinance_resolves?: boolean | null;
  final_ticker?: string | null;
  note?: string | null;
}

interface Row {
  symbol?: string;
  long_name?: string | null;
  sector?: string | null;
  industry?: string | null;
  exchange?: string | null;
  currency?: string | null;
  market_cap?: number | null;
  trailing_pe?: number | null;
  forward_pe?: number | null;
  price_to_book?: number | null;
  price_to_sales_ttm?: number | null;
  trailing_peg_ratio?: number | null;
  return_on_equity?: number | null;
  return_on_assets?: number | null;
  profit_margins?: number | null;
  gross_margins?: number | null;
  operating_margins?: number | null;
  debt_to_equity?: number | null;
  current_ratio?: number | null;
  quick_ratio?: number | null;
  revenue_growth?: number | null;
  earnings_growth?: number | null;
  dividend_yield?: number | null;
  payout_ratio?: number | null;
  fifty_two_week_high?: number | null;
  fifty_two_week_low?: number | null;
  beta?: number | null;
  roi?: number | null;
  rd_to_revenue?: number | null;
  sortino_ratio?: number | null;
  composite_scores?: CompositeScores | null;
}
