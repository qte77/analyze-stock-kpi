// @ts-check
// Side detail-panel (#row-detail) lifecycle for the demo dashboard: build,
// populate, tab-switch, dismiss. DOM-coupled glue split out of app.js to
// shrink the entry file (mirrors table.js). The row's audit record and the two
// chart renderers are passed in by the caller via a context object rather than
// read from app.js globals, so this file stays free of app.js mutable state and
// its chart slots. Pure data (KPI_GLOSSARY, audit/link row builders) + number
// formatting come from lib/. DOM glue — verified by hand via `make preview`.

import {
  COMPOSITE_LABELS,
  KPI_GLOSSARY,
  auditDetailRows,
  externalLinkRows,
  kpiGroups,
} from "./lib/detail_rows.js";
import { fmtNum } from "./lib/format.js";
import { effectiveScore } from "./table.js";

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

/**
 * Show or hide one tab's pane, with its `aria-selected` and roving tabindex.
 *
 * @param {HTMLButtonElement} tab
 * @param {HTMLElement} pane
 * @param {boolean} selected
 */
function selectTab(tab, pane, selected) {
  tab.setAttribute("aria-selected", selected ? "true" : "false");
  tab.tabIndex = selected ? 0 : -1;
  pane.hidden = !selected;
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
  // The same screener_score the table's Score column shows and ranks by
  // everywhere, including on the aggregator universes — see table.js's
  // effectiveScore().
  const qte77Score = effectiveScore(row);
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

  // Plan 010 slice 7: a real ARIA tablist, so the shared arrow-key handler
  // (app.js bindTabArrowKeys) serves it like the market-mood tabs.
  const tabs = document.createElement("div");
  tabs.className = "detail-tabs";
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "Detail view");
  const overviewTab = document.createElement("button");
  const seriesTab = document.createElement("button");
  const overviewPane = document.createElement("div");
  const seriesPane = document.createElement("div");
  for (const [tab, pane, name, selected] of /** @type {const} */ ([
    [overviewTab, overviewPane, "overview", true],
    [seriesTab, seriesPane, "series", false],
  ])) {
    tab.type = "button";
    tab.id = `detail-tab-${name}`;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", `detail-pane-${name}`);
    pane.id = `detail-pane-${name}`;
    pane.setAttribute("role", "tabpanel");
    pane.setAttribute("aria-labelledby", tab.id);
    selectTab(tab, pane, selected);
  }
  overviewTab.textContent = "Overview";
  seriesTab.textContent = "Time series";
  tabs.append(overviewTab, seriesTab);
  aside.append(tabs, overviewPane, seriesPane);

  overviewTab.addEventListener("click", () => {
    selectTab(overviewTab, overviewPane, true);
    selectTab(seriesTab, seriesPane, false);
  });
  seriesTab.addEventListener("click", () => {
    selectTab(overviewTab, overviewPane, false);
    selectTab(seriesTab, seriesPane, true);
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

  const list = document.createElement("dl");
  list.append(
    dl([
      ["Sector", row.sector ?? "—"],
      ["Industry", row.industry ?? "—"],
      ["Exchange", `${row.exchange ?? "—"} (${row.currency ?? "—"})`],
      ["Market cap", mcap],
      // Plan 010 D7: the KPIs in the qte77 Score's four factors.
      ...kpiGroups(row).flatMap(({ title, rows }) => [
        /** @type {[string, string, boolean]} */ ([title, "", true]),
        ...rows,
      ]),
      ["Composite scores", "", true],
      ...Object.entries(COMPOSITE_LABELS).map(
        ([key, label]) =>
          /** @type {[string, string, boolean, string]} */ ([
            label,
            fmtNum(
              key === "screener_score" ? qte77Score : cs[/** @type {keyof typeof cs} */ (key)],
              0,
            ),
            false,
            KPI_GLOSSARY[/** @type {keyof typeof KPI_GLOSSARY} */ (key)],
          ]),
      ),
      ...auditDetailRows(audit),
    ]),
  );
  overviewPane.append(list);
  aside.hidden = false;
  ctx.renderRadar(radarCanvas, cs);
}
