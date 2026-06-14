// @ts-check
// Side detail-panel (#row-detail) lifecycle for the demo dashboard: build,
// populate, tab-switch, dismiss. DOM-coupled glue split out of app.js to
// shrink the entry file (mirrors table.js). The row's audit record and the two
// chart renderers are passed in by the caller via a context object rather than
// read from app.js globals, so this file stays free of app.js mutable state and
// its chart slots. Pure data (KPI_GLOSSARY, audit/link row builders) + number
// formatting come from lib/. DOM glue — verified by hand via `make preview`.

import { KPI_GLOSSARY, auditDetailRows, externalLinkRows } from "./lib/detail_rows.js";
import { fmtNum, fmtPct } from "./lib/format.js";

/**
 * Build a `<dt>/<dd>` fragment from `[label, value, sectionHeader?, tooltip?]`
 * tuples. A truthy `sectionHeader` renders a lone `.section` `<dt>`; a `tooltip`
 * makes the `<dt>` focusable with a `title`.
 *
 * @param {Array<[string, string, boolean?, string?]>} pairs
 * @returns {DocumentFragment}
 */
function dl(pairs) {
  const frag = document.createDocumentFragment();
  for (const [label, value, sectionHeader, tooltip] of pairs) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    if (sectionHeader) {
      dt.className = "section";
      frag.append(dt);
      continue;
    }
    if (tooltip) {
      dt.title = tooltip;
      dt.tabIndex = 0;
    }
    const dd = document.createElement("dd");
    dd.textContent = value;
    frag.append(dt, dd);
  }
  return frag;
}

function closeDetail() {
  const aside = document.getElementById("row-detail");
  if (aside) aside.hidden = true;
}

/**
 * Wire global dismissal of the detail panel: an outside click (ignoring clicks
 * inside the panel or on a table row, which re-open it) and the Escape key.
 * Bound once at init; idempotent no-op if `#row-detail` is absent.
 */
export function bindDetailDismiss() {
  const aside = document.getElementById("row-detail");
  if (!aside) return;
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (aside.hidden || !(target instanceof Node)) return;
    if (aside.contains(target)) return;
    const targetElement = target instanceof Element ? target : target.parentElement;
    if (targetElement?.closest("#universe-table tbody tr")) return;
    aside.hidden = true;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !aside.hidden) aside.hidden = true;
  });
}

/**
 * Build + populate the `#row-detail` side panel for one row: header, the
 * Overview/Time-series tab pair, the radar chart, external links, and the KPI
 * definition list. The row's audit record and the two chart renderers are
 * injected via `ctx` so this module never reads app.js module state or its
 * chart slots directly. The time-series pane renders lazily on first tab click.
 *
 * @param {Row} row
 * @param {{
 *   auditByTicker: Map<string, AuditRow> | null,
 *   renderRadar: (canvas: HTMLCanvasElement, scores: CompositeScores) => void,
 *   renderTimeSeriesPane: (pane: HTMLElement, row: Row) => void | Promise<void>,
 * }} ctx
 */
export function showDetail(row, ctx) {
  const cs = row.composite_scores ?? {};
  const mcap = row.market_cap ? `$${(row.market_cap / 1e9).toFixed(2)} B` : "—";
  const audit = row.symbol ? (ctx.auditByTicker?.get(row.symbol) ?? null) : null;

  const aside = document.getElementById("row-detail");
  if (!aside) return;
  aside.replaceChildren();

  const closeBtn = document.createElement("button");
  closeBtn.id = "close-detail";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.textContent = "×";
  closeBtn.addEventListener("click", closeDetail);
  aside.append(closeBtn);

  const h3 = document.createElement("h3");
  h3.textContent = `${row.symbol ?? "—"} · ${row.long_name ?? ""}`;
  aside.append(h3);

  const tabs = document.createElement("div");
  tabs.className = "detail-tabs";
  const overviewTab = document.createElement("button");
  overviewTab.type = "button";
  overviewTab.textContent = "Overview";
  overviewTab.setAttribute("aria-selected", "true");
  const seriesTab = document.createElement("button");
  seriesTab.type = "button";
  seriesTab.textContent = "Time series";
  seriesTab.setAttribute("aria-selected", "false");
  tabs.append(overviewTab, seriesTab);
  aside.append(tabs);

  const overviewPane = document.createElement("div");
  const seriesPane = document.createElement("div");
  seriesPane.hidden = true;
  aside.append(overviewPane, seriesPane);

  overviewTab.addEventListener("click", () => {
    overviewTab.setAttribute("aria-selected", "true");
    seriesTab.setAttribute("aria-selected", "false");
    overviewPane.hidden = false;
    seriesPane.hidden = true;
  });
  seriesTab.addEventListener("click", () => {
    overviewTab.setAttribute("aria-selected", "false");
    seriesTab.setAttribute("aria-selected", "true");
    overviewPane.hidden = true;
    seriesPane.hidden = false;
    if (seriesPane.childElementCount === 0) {
      void ctx.renderTimeSeriesPane(seriesPane, row);
    }
  });

  const radarWrap = document.createElement("div");
  radarWrap.className = "radar-wrap";
  const radarCanvas = document.createElement("canvas");
  radarWrap.append(radarCanvas);
  overviewPane.append(radarWrap);

  const linkSection = document.createElement("nav");
  linkSection.className = "detail-links";
  for (const [label, href] of externalLinkRows(row)) {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = label;
    a.target = "_blank";
    a.rel = "noopener";
    linkSection.append(a);
  }
  overviewPane.append(linkSection);

  const trail = row.trailing_pe;
  const fwd = row.forward_pe;
  const trailFwd = trail != null && fwd != null && fwd !== 0 ? (trail / fwd).toFixed(2) : "—";

  const list = document.createElement("dl");
  list.append(
    dl([
      ["Sector", row.sector ?? "—"],
      ["Industry", row.industry ?? "—"],
      ["Exchange", `${row.exchange ?? "—"} (${row.currency ?? "—"})`],
      ["Market cap", mcap],
      [
        "Trail / Fwd P/E",
        `${fmtNum(row.trailing_pe, 2)} / ${fmtNum(row.forward_pe, 2)}`,
        false,
        KPI_GLOSSARY.trailing_pe,
      ],
      ["Trail/Fwd P/E ratio", trailFwd, false, KPI_GLOSSARY.trail_fwd_pe],
      ["P/B / P/S TTM", `${fmtNum(row.price_to_book, 2)} / ${fmtNum(row.price_to_sales_ttm, 2)}`],
      ["Gross margin %", fmtPct(row.gross_margins), false, KPI_GLOSSARY.gross_margins],
      ["Net margin %", fmtPct(row.profit_margins), false, KPI_GLOSSARY.profit_margins],
      [
        "ROE / ROA",
        `${fmtPct(row.return_on_equity)} % / ${fmtPct(row.return_on_assets)} %`,
        false,
        KPI_GLOSSARY.return_on_equity,
      ],
      ["ROI", fmtPct(row.roi), false, KPI_GLOSSARY.roi],
      ["R&D / Revenue %", fmtPct(row.rd_to_revenue), false, KPI_GLOSSARY.rd_to_revenue],
      ["Op margin %", fmtPct(row.operating_margins), false, KPI_GLOSSARY.operating_margins],
      ["D/E", fmtNum(row.debt_to_equity, 2), false, KPI_GLOSSARY.debt_to_equity],
      ["Current ratio", fmtNum(row.current_ratio, 2), false, KPI_GLOSSARY.current_ratio],
      ["Quick ratio", fmtNum(row.quick_ratio, 2), false, KPI_GLOSSARY.quick_ratio],
      ["Revenue growth", `${fmtPct(row.revenue_growth)} %`],
      ["Earnings growth", `${fmtPct(row.earnings_growth)} %`],
      ["Div yield / Payout", `${fmtPct(row.dividend_yield)} % / ${fmtPct(row.payout_ratio)} %`],
      [
        "52w high / low",
        `$${fmtNum(row.fifty_two_week_high, 2)} / $${fmtNum(row.fifty_two_week_low, 2)}`,
      ],
      ["Beta", fmtNum(row.beta, 2), false, KPI_GLOSSARY.beta],
      ["PEG (trailing)", fmtNum(row.trailing_peg_ratio, 2), false, KPI_GLOSSARY.trailing_peg_ratio],
      ["Sortino (1y, rf=0)", fmtNum(row.sortino_ratio, 2), false, KPI_GLOSSARY.sortino_ratio],
      ["Composite scores", "", true],
      ["Quality", fmtNum(cs.quality, 0), false, KPI_GLOSSARY.quality],
      ["Dividend", fmtNum(cs.dividend, 0), false, KPI_GLOSSARY.dividend],
      ["Growth", fmtNum(cs.growth, 0), false, KPI_GLOSSARY.growth],
      ["Big Call", fmtNum(cs.big_call, 0), false, KPI_GLOSSARY.big_call],
      ["AAQS", fmtNum(cs.aaqs, 0), false, KPI_GLOSSARY.aaqs],
      ["HGI", fmtNum(cs.hgi, 0), false, KPI_GLOSSARY.hgi],
      ["qte77 Score", fmtNum(cs.screener_score, 0), false, KPI_GLOSSARY.screener_score],
      ...auditDetailRows(audit),
    ]),
  );
  overviewPane.append(list);
  aside.hidden = false;
  ctx.renderRadar(radarCanvas, cs);
}
