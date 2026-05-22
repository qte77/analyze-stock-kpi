// @ts-check
/* global Chart, Fuse */
// Demo dashboard logic (#59).
//
// Fetches data files cross-origin from the `data` branch via
// raw.githubusercontent.com. The branch is updated by the
// demo-snapshot.yml (weekly) and fear-greed.yaml (daily) workflows,
// which commit verified API commits to a branch outside the
// default-branch ruleset's scope.
//
// Type declarations for `Row` + `CompositeScores` live in `types.d.ts`
// (declaration-only; never shipped to the browser).

// Default points at the verified-commit `data` branch served via GitHub's
// raw host. Override at load via the `?base=<url>` query string so a local
// `make preview-local` (or any other static-file host) can feed the same
// dashboard fresh on-disk snapshots without editing this constant.
const DATA_BASE_URL = (
  new URLSearchParams(window.location.search).get("base") ??
  "https://raw.githubusercontent.com/qte77/analyze-stock-kpi/data"
).replace(/\/$/, "");

// Active universe id. Initialised from `?universe=<id>` query param at
// boot (see init()); the `<select id="universe-picker">` change handler
// mutates it + re-loads the dashboard. Falls back to the first entry of
// universes.json when the query is unset or unknown.
let activeUniverse = "qte77-watchlist";

// Audit JSON keyed by `final_ticker` for the active universe + snapshot
// date. Populated by loadAudit() opportunistically (silent 404). Used by
// showDetail() to append a "Federal Contracts" section when the row's
// symbol matches.
/** @type {Map<string, AuditRow> | null} */
let auditByTicker = null;

const RATING_CLASSES = {
  "extreme fear": "rating-extreme-fear",
  "fear": "rating-fear",
  "neutral": "rating-neutral",
  "greed": "rating-greed",
  "extreme greed": "rating-extreme-greed",
};

/** @type {{snapshot: Row[], sortKey: string, sortDir: 1 | -1}} */
const state = {
  snapshot: [],
  sortKey: "composite_scores.screener_score",
  sortDir: -1,
};

// Fuse.js index over the current snapshot. Rebuilt every time
// `state.snapshot` changes (init + snapshot-date change handler).
let fuseIndex = null;
let filterQuery = "";

function rebuildFuseIndex() {
  fuseIndex =
    typeof Fuse !== "undefined" && state.snapshot.length
      ? new Fuse(state.snapshot, {
          keys: ["symbol", "long_name", "sector"],
          threshold: 0.3,
        })
      : null;
}

function filteredSnapshot() {
  if (!filterQuery || fuseIndex == null) return state.snapshot;
  return fuseIndex.search(filterQuery).map((r) => r.item);
}

// English glossary for detail-panel tooltips (title= attributes on labels).
const KPI_GLOSSARY = {
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
    "Mean of 4 thematic factor scores: Profitability (ROE, ROA, Op M, R&D/Rev) needs >= 2 of 4 inputs; Valuation (P/E fwd, PEG) needs >= 1 of 2; Risk (Beta, Current) needs >= 1 of 2; Momentum (Sortino) needs 1 of 1. Factors below their input minimum drop from the composite; remaining factors re-share the weight equally. Returns — when total inputs < 5 of 9. Higher = better.",
  quality:
    "Mean of normalized ROE, ROA, operating margin, and inverted D/E. Higher = stronger fundamentals.",
  dividend:
    "Dividend yield + payout-ratio sweet spot (peaks near ~50% payout). Higher = healthier dividend profile.",
  growth:
    "Mean of normalized revenue + earnings growth. Higher = stronger top-line and bottom-line growth.",
  big_call:
    "Weighted Quality (40%) + Dividend (30%) + Growth (30%); reweights proportionally when a component is missing.",
  aaqs:
    "Quality combined with low-volatility (low beta is better). Higher = quality with stable beta.",
  hgi:
    "Growth-tilted score with a fixed bonus when operating margin clears ~10%.",
};

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error(`fetch ${url} failed: ${res.status}`);
  return res.json();
}

const loadManifest = () =>
  fetchJson(`${DATA_BASE_URL}/results/demo/${activeUniverse}/index.json`);

const loadSnapshot = (date) =>
  fetchJson(`${DATA_BASE_URL}/results/demo/${activeUniverse}/${date}.json`);

// Bundled manifest of universes — served same-origin alongside index.html
// (NOT under DATA_BASE_URL). Hand-maintained in lockstep with
// src/assets/universes/*.txt; one entry per bundled preset.
/** @returns {Promise<{universes: {id: string, label: string}[]}>} */
const loadUniverses = () => fetchJson("universes.json");

// Opportunistic audit-JSON join — only meaningful for federal-contractors
// today. Other universes have no audit path; we return null silently to
// keep the dashboard a pure no-op for them. 404s on the federal-contractors
// path itself (e.g., before the first refresh workflow run) also return
// null silently, mirroring loadFearGreedYears' Promise.allSettled pattern.
//
// On success the response is a JSON array of AuditRow objects; we index
// them by `final_ticker` (skipping rows where final_ticker is null — those
// rows didn't resolve to a tradeable ticker and have no row in the
// universe snapshot to attach to).
/**
 * @param {string} universe
 * @param {string} date
 * @returns {Promise<Map<string, AuditRow> | null>}
 */
async function loadAudit(universe, date) {
  if (universe !== "federal-contractors") return null;
  try {
    const rows = /** @type {AuditRow[]} */ (
      await fetchJson(
        `${DATA_BASE_URL}/results/federal_contractors/audit/${date}.json`,
      )
    );
    if (!Array.isArray(rows)) return null;
    const map = new Map();
    for (const row of rows) {
      if (row?.final_ticker) map.set(row.final_ticker, row);
    }
    return map;
  } catch {
    return null;
  }
}

async function loadFearGreedYears() {
  const thisYear = new Date().getUTCFullYear();
  const results = await Promise.allSettled([
    fetchJson(`${DATA_BASE_URL}/results/cnn_fg/${thisYear - 1}.json`),
    fetchJson(`${DATA_BASE_URL}/results/cnn_fg/${thisYear}.json`),
  ]);
  const merged = [];
  for (const r of results) {
    if (r.status === "fulfilled" && Array.isArray(r.value)) {
      merged.push(...r.value);
    }
  }
  return merged.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

function nested(obj, key) {
  return key.split(".").reduce((o, k) => (o == null ? null : o[k]), obj);
}

const fmtNum = (v, d = 1) =>
  v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d);

const fmtPct = (v) => (v == null ? "—" : (Number(v) * 100).toFixed(2));

function compareValues(a, b, dir) {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "string") return dir * a.localeCompare(b);
  return dir * (a - b);
}

function td(text, cls) {
  const el = document.createElement("td");
  el.textContent = text;
  if (cls) el.className = cls;
  return el;
}

/**
 * Render the visible (filtered + sorted) universe into the table body.
 * @returns {void}
 */
function renderTable() {
  const tbody = document.querySelector("#universe-table tbody");
  if (!tbody) return;
  tbody.replaceChildren();
  const visible = filteredSnapshot();
  const sorted = [...visible].sort((a, b) =>
    compareValues(nested(a, state.sortKey), nested(b, state.sortKey), state.sortDir),
  );
  // Per-row Weight % = score / sum(scores) over the *visible* set so
  // allocation hints stay relative to what the user is looking at.
  const totalScore = visible.reduce((acc, row) => {
    const s = nested(row, "composite_scores.screener_score");
    return acc + (s == null ? 0 : Number(s));
  }, 0);
  for (const row of sorted) {
    const tr = document.createElement("tr");
    const score = nested(row, "composite_scores.screener_score");
    // Count screener inputs (same 9 fields screener_score reads from
    // the snapshot; negative forward_pe is dropped to match the
    // backend's negative-PE guard).
    const coverage = [
      "forward_pe",
      "trailing_peg_ratio",
      "beta",
      "rd_to_revenue",
      "operating_margins",
      "return_on_equity",
      "return_on_assets",
      "current_ratio",
      "sortino_ratio",
    ].filter(
      (k) => row[k] != null && !(k === "forward_pe" && row[k] <= 0),
    ).length;
    const parts = [];
    if (score != null && totalScore > 0) {
      const weightPct = ((100 * Number(score)) / totalScore).toFixed(1);
      parts.push(`Weight ${weightPct} %`);
      parts.push(`Score ${Number(score).toFixed(0)}`);
    }
    parts.push(`${coverage}/9 inputs`);
    tr.title = parts.join(" · ");
    // Heatmap on the Score column only: 0 -> red (hue 0), 50 -> yellow (60),
    // 100 -> green (120). Lightness 75% keeps the dark text WCAG-readable.
    const scoreCell = td(fmtNum(score, 0), "num score-cell");
    if (score != null) {
      scoreCell.style.backgroundColor = `hsl(${Number(score) * 1.2}, 60%, 75%)`;
    }
    tr.append(
      td(row.symbol ?? "—"),
      td(row.long_name ?? "—"),
      td(row.sector ?? "—"),
      td(fmtNum(row.forward_pe, 2), "num"),
      td(fmtNum(row.trailing_peg_ratio, 2), "num"),
      td(fmtNum(row.beta, 2), "num"),
      td(fmtPct(row.rd_to_revenue), "num"),
      td(fmtPct(row.operating_margins), "num"),
      td(fmtPct(row.return_on_equity), "num"),
      td(fmtPct(row.return_on_assets), "num"),
      td(fmtNum(row.current_ratio, 2), "num"),
      td(fmtNum(row.sortino_ratio, 2), "num"),
      scoreCell,
    );
    tr.addEventListener("click", () => showDetail(row));
    tbody.appendChild(tr);
  }
}

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
 * Hide the row-detail aside without removing its children.
 * @returns {void}
 */
function closeDetail() {
  const aside = document.getElementById("row-detail");
  if (aside) aside.hidden = true;
}

/**
 * Wire document-level listeners that dismiss `#row-detail` on outside
 * click or Escape. Idempotent: safe to call once at init.
 * @returns {void}
 */
function bindDetailDismiss() {
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
    if (event.key === "Escape" && !aside.hidden) {
      aside.hidden = true;
    }
  });
}

/**
 * Populate and reveal the row-detail aside for one ticker row.
 * @param {Row} row
 * @returns {void}
 */
function showDetail(row) {
  const cs = row.composite_scores ?? {};
  const mcap = row.market_cap
    ? `$${(row.market_cap / 1e9).toFixed(2)} B`
    : "—";
  const audit = row.symbol ? auditByTicker?.get(row.symbol) ?? null : null;

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

  const trail = row.trailing_pe;
  const fwd = row.forward_pe;
  const trailFwd =
    trail != null && fwd != null && fwd !== 0
      ? (trail / fwd).toFixed(2)
      : "—";
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
      [
        "Gross margin %",
        fmtPct(row.gross_margins),
        false,
        KPI_GLOSSARY.gross_margins,
      ],
      [
        "Net margin %",
        fmtPct(row.profit_margins),
        false,
        KPI_GLOSSARY.profit_margins,
      ],
      [
        "ROE / ROA",
        `${fmtPct(row.return_on_equity)} % / ${fmtPct(row.return_on_assets)} %`,
        false,
        KPI_GLOSSARY.return_on_equity,
      ],
      ["ROI", fmtPct(row.roi), false, KPI_GLOSSARY.roi],
      [
        "R&D / Revenue %",
        fmtPct(row.rd_to_revenue),
        false,
        KPI_GLOSSARY.rd_to_revenue,
      ],
      [
        "Op margin %",
        fmtPct(row.operating_margins),
        false,
        KPI_GLOSSARY.operating_margins,
      ],
      ["D/E", fmtNum(row.debt_to_equity, 2), false, KPI_GLOSSARY.debt_to_equity],
      [
        "Current ratio",
        fmtNum(row.current_ratio, 2),
        false,
        KPI_GLOSSARY.current_ratio,
      ],
      ["Quick ratio", fmtNum(row.quick_ratio, 2), false, KPI_GLOSSARY.quick_ratio],
      ["Revenue growth", `${fmtPct(row.revenue_growth)} %`],
      ["Earnings growth", `${fmtPct(row.earnings_growth)} %`],
      ["Div yield / Payout", `${fmtPct(row.dividend_yield)} % / ${fmtPct(row.payout_ratio)} %`],
      ["52w high / low", `$${fmtNum(row.fifty_two_week_high, 2)} / $${fmtNum(row.fifty_two_week_low, 2)}`],
      ["Beta", fmtNum(row.beta, 2), false, KPI_GLOSSARY.beta],
      [
        "PEG (trailing)",
        fmtNum(row.trailing_peg_ratio, 2),
        false,
        KPI_GLOSSARY.trailing_peg_ratio,
      ],
      [
        "Sortino (1y, rf=0)",
        fmtNum(row.sortino_ratio, 2),
        false,
        KPI_GLOSSARY.sortino_ratio,
      ],
      ["Composite scores", "", true],
      ["Quality", fmtNum(cs.quality, 0), false, KPI_GLOSSARY.quality],
      ["Dividend", fmtNum(cs.dividend, 0), false, KPI_GLOSSARY.dividend],
      ["Growth", fmtNum(cs.growth, 0), false, KPI_GLOSSARY.growth],
      ["Big Call", fmtNum(cs.big_call, 0), false, KPI_GLOSSARY.big_call],
      ["AAQS", fmtNum(cs.aaqs, 0), false, KPI_GLOSSARY.aaqs],
      ["HGI", fmtNum(cs.hgi, 0), false, KPI_GLOSSARY.hgi],
      [
        "Screener",
        fmtNum(cs.screener_score, 0),
        false,
        KPI_GLOSSARY.screener_score,
      ],
      ...auditDetailRows(audit),
    ]),
  );
  aside.append(list);
  aside.hidden = false;
}

/**
 * Build the "Federal Contracts" detail rows for an audit entry, or an
 * empty array when there's no match (so the spread in showDetail is a
 * no-op for universes without an audit join).
 *
 * @param {AuditRow | null} audit
 * @returns {Array<[string, string, boolean?, string?]>}
 */
function auditDetailRows(audit) {
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
 * Format an obligated-USD amount with a unit suffix. `null`/missing → "—".
 * Big numbers compress to $X.Yb / $X.YM for readability in the side panel.
 * @param {number | null | undefined} usd
 * @returns {string}
 */
function formatObligated(usd) {
  if (usd == null) return "—";
  const n = Number(usd);
  if (Number.isNaN(n)) return "—";
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)} b`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)} M`;
  return `$${n.toFixed(0)}`;
}

function findClosestScore(entries, latestMs, daysAgo) {
  const target = latestMs - daysAgo * 86400000;
  let best = null;
  let bestDiff = Infinity;
  for (const e of entries) {
    const diff = Math.abs(new Date(e.timestamp).getTime() - target);
    if (diff < bestDiff) {
      bestDiff = diff;
      best = e;
    }
  }
  return best?.score;
}

function renderFearGreedHeader(entries) {
  if (!entries.length) {
    const chipEl = document.getElementById("fg-rating");
    chipEl.textContent = "no data";
    chipEl.className = "chip";
    document.getElementById("fg-deltas").textContent = "";
    return;
  }
  const last = entries[entries.length - 1];
  document.getElementById("fg-score").textContent = fmtNum(last.score, 0);
  const rating = (last.rating ?? "").toLowerCase();
  const chip = document.getElementById("fg-rating");
  chip.textContent = last.rating ?? "—";
  chip.className = `chip ${RATING_CLASSES[rating] ?? ""}`;

  const latestMs = new Date(last.timestamp).getTime();
  const deltas = [
    ["yesterday", 1],
    ["last week", 7],
    ["last month", 30],
    ["last year", 365],
  ]
    .map(([label, d]) => `${label} ${fmtNum(findClosestScore(entries, latestMs, d), 0)}`)
    .join(" · ");
  document.getElementById("fg-deltas").textContent = `(${deltas})`;
}

function renderFearGreedChart(entries) {
  if (!entries.length || typeof Chart === "undefined") return;
  const ctx = document.getElementById("fg-chart");
  // eslint-disable-next-line no-new
  new Chart(ctx, {
    type: "line",
    data: {
      labels: entries.map((e) => e.timestamp.slice(0, 10)),
      datasets: [
        {
          data: entries.map((e) => e.score),
          borderColor: "#1d1d1f",
          backgroundColor: "rgba(29, 29, 31, 0.08)",
          fill: true,
          pointRadius: 0,
          borderWidth: 1.5,
          tension: 0.15,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 100, ticks: { stepSize: 25 } },
        x: { ticks: { maxTicksLimit: 14 } },
      },
    },
  });
}

/**
 * Wire click-to-sort on every `<th>` of the universe table.
 * Toggling the same column flips direction; switching column resets to asc.
 * @returns {void}
 */
function bindTableSort() {
  document
    .querySelectorAll("#universe-table thead th")
    .forEach((/** @type {Element} */ th) => {
      if (!(th instanceof HTMLElement)) return;
      th.addEventListener("click", () => {
        const key = th.dataset.key;
        if (!key) return;
        if (state.sortKey === key) {
          state.sortDir = /** @type {1 | -1} */ (state.sortDir * -1);
        } else {
          state.sortKey = key;
          state.sortDir = 1;
        }
        document.querySelectorAll("#universe-table thead th").forEach((t) => {
          t.classList.remove("sort-asc", "sort-desc");
        });
        th.classList.add(state.sortDir > 0 ? "sort-asc" : "sort-desc");
        renderTable();
      });
    });
}

/**
 * Sync the URL bar to the active universe via `history.replaceState`,
 * so a refresh restores the picked universe and the URL can be shared.
 * Keeps `?base=` and any other unrelated query params intact.
 * @param {string} universe
 * @returns {void}
 */
function persistUniverseInUrl(universe) {
  const url = new URL(window.location.href);
  url.searchParams.set("universe", universe);
  window.history.replaceState({}, "", url);
}

/**
 * Load manifest + latest snapshot + audit JSON for `activeUniverse`,
 * populate the date selector, and render the table. Called once at
 * boot and again whenever the universe picker fires `change`.
 *
 * Returns early on manifest 404 (typical for a fresh universe before its
 * first cron run) — the dashboard collapses to an empty-state line in
 * the size span rather than crashing.
 * @returns {Promise<void>}
 */
async function loadActiveUniverse() {
  const dateSelector = /** @type {HTMLSelectElement | null} */ (
    document.getElementById("date-selector")
  );
  const sizeEl = document.getElementById("universe-size");
  if (!dateSelector || !sizeEl) return;

  let manifest;
  try {
    manifest = await loadManifest();
  } catch {
    state.snapshot = [];
    auditByTicker = null;
    rebuildFuseIndex();
    dateSelector.replaceChildren();
    sizeEl.textContent = `no data yet for ${activeUniverse}`;
    renderTable();
    return;
  }

  dateSelector.replaceChildren();
  for (const date of [...manifest.dates].reverse()) {
    const opt = document.createElement("option");
    opt.value = date;
    opt.textContent = date;
    dateSelector.appendChild(opt);
  }
  dateSelector.value = manifest.latest;

  state.snapshot = await loadSnapshot(manifest.latest);
  auditByTicker = await loadAudit(activeUniverse, manifest.latest);
  rebuildFuseIndex();
  sizeEl.textContent = `${state.snapshot.length} tickers`;
  renderTable();
  const updatedEl = document.getElementById("updated");
  if (updatedEl) {
    updatedEl.textContent = `updated ${manifest.updated_at}`;
  }
}

/**
 * Bootstrap: wire dismissal + sort + filter, populate the universe
 * picker, load the latest snapshot for `activeUniverse`, and render
 * the F&G banner + chart.
 * @returns {Promise<void>}
 */
async function init() {
  bindDetailDismiss();
  bindTableSort();
  const initialSortTh = document.querySelector(
    `#universe-table thead th[data-key="${state.sortKey}"]`,
  );
  if (initialSortTh) {
    initialSortTh.classList.add(state.sortDir > 0 ? "sort-asc" : "sort-desc");
  }

  // Wire universe picker first so manifest/snapshot loads use the
  // user-selected universe (from ?universe= or universes.json default).
  const picker = /** @type {HTMLSelectElement | null} */ (
    document.getElementById("universe-picker")
  );
  if (!picker) return;
  /** @type {{universes: {id: string, label: string}[]}} */
  let universesPayload;
  try {
    universesPayload = await loadUniverses();
  } catch {
    universesPayload = { universes: [{ id: "qte77-watchlist", label: "qte77 watchlist" }] };
  }
  const universes = universesPayload.universes ?? [];
  for (const u of universes) {
    const opt = document.createElement("option");
    opt.value = u.id;
    opt.textContent = u.label;
    picker.appendChild(opt);
  }
  const requested = new URLSearchParams(window.location.search).get("universe");
  const knownIds = new Set(universes.map((u) => u.id));
  activeUniverse = requested && knownIds.has(requested)
    ? requested
    : universes[0]?.id ?? "qte77-watchlist";
  picker.value = activeUniverse;
  picker.addEventListener("change", async () => {
    activeUniverse = picker.value;
    persistUniverseInUrl(activeUniverse);
    await loadActiveUniverse();
  });

  const dateSelector = /** @type {HTMLSelectElement | null} */ (
    document.getElementById("date-selector")
  );
  dateSelector?.addEventListener("change", async () => {
    state.snapshot = await loadSnapshot(dateSelector.value);
    auditByTicker = await loadAudit(activeUniverse, dateSelector.value);
    rebuildFuseIndex();
    renderTable();
  });

  const filterInput = document.getElementById("universe-filter");
  filterInput?.addEventListener("input", (e) => {
    const target = e.target;
    if (target instanceof HTMLInputElement) {
      filterQuery = target.value.trim();
      renderTable();
    }
  });

  await loadActiveUniverse();

  const fgEntries = await loadFearGreedYears();
  renderFearGreedHeader(fgEntries);
  renderFearGreedChart(fgEntries);
}

document.addEventListener("DOMContentLoaded", init);
