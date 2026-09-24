"""Cross-universe qte77 Score aggregator.

Reads the latest snapshot per bundled universe from the ``data`` branch,
ranks tickers by their qte77 Score (``composite_scores.screener_score`` --
the same composite the dashboard displays and sorts by on every other
universe), and emits a 50-ticker preset combining the top 25 + bottom 25.

Ranking previously used the mean of the 7 composite scores
(``quality / dividend / growth / big_call / aaqs / hgi / screener_score``),
which could disagree with the dashboard's displayed "qte77 Score"
(``screener_score``) for the same ticker. Ranking by ``screener_score``
directly keeps the aggregator's best/worst placement consistent with what
the dashboard shows everywhere else.

Mirrors :mod:`analyze_stock_kpi.orchestrators.federal_contractors` for orchestrator
shape: returns ``(list[ticker], list[AuditRow])``; per-ticker decisions
captured in the audit JSON committed to the ``data`` branch.

See ADR-0005 for tier classification (Tier-0; pure aggregation of
already-Tier-0 snapshots; no new external boundary).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from analyze_stock_kpi.domain.composite_scores import CompositeScores

from ._shared import AuditRowBase, dedup_by_ticker, is_stale

if TYPE_CHECKING:
    from collections.abc import Iterable

    from analyze_stock_kpi.data_sources.fundamentals import FundamentalsSnapshot

    from ._shared import DedupedSnapshot


# Derived from the model so adding a CompositeScores field flows through
# to the audit breakdown without a separate edit here.
_COMPOSITE_FIELDS = tuple(CompositeScores.model_fields)


class AuditRow(AuditRowBase):
    """Per-ticker decision trail for the aggregator.

    Inherits ``ticker``, ``source_universes``, ``snapshot_dates``,
    ``eligible``, ``excluded_reason`` from :class:`AuditRowBase`.
    ``composite_breakdown`` stays informational (all 7 composites, for
    context); ``screener_score`` is the value actually used to rank.
    """

    populated_composites: int
    composite_breakdown: dict[str, float | None]
    screener_score: float | None = None
    rank: int | None = None


def _extract_composites(snap: FundamentalsSnapshot) -> dict[str, float | None]:
    """Pull the 7 composite scores into a name->value dict."""
    cs = snap.composite_scores
    if cs is None:
        return dict.fromkeys(_COMPOSITE_FIELDS)
    return {f: getattr(cs, f) for f in _COMPOSITE_FIELDS}


def _classify(
    ticker: str,
    info: DedupedSnapshot,
    as_of: date,
    max_stale_days: int,
) -> tuple[AuditRow, float | None]:
    """Build the AuditRow and return ``(row, screener_score_for_ranking)``.

    ``screener_score_for_ranking`` is ``None`` for excluded tickers (won't
    be ranked).
    """
    snap = info.snapshot
    source_universes = info.source_universes
    snapshot_dates = info.snapshot_dates
    composites = _extract_composites(snap)
    populated = sum(1 for v in composites.values() if v is not None)
    first_date = snapshot_dates[source_universes[0]]
    base = {
        "ticker": ticker,
        "source_universes": source_universes,
        "snapshot_dates": snapshot_dates,
        "populated_composites": populated,
        "composite_breakdown": composites,
    }
    if is_stale(first_date, as_of, max_stale_days):
        return AuditRow(**base, eligible=False, excluded_reason="stale"), None
    score = composites["screener_score"]
    if score is None:
        return (
            AuditRow(**base, eligible=False, excluded_reason="no_screener_score"),
            None,
        )
    return AuditRow(**base, screener_score=score, eligible=True), score


def build_universe(
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]],
    snapshot_dates_by_universe: dict[str, str],
    *,
    top_n: int = 25,
    max_stale_days: int = 14,
    as_of: date | None = None,
) -> tuple[list[str], list[str], list[AuditRow]]:
    """Build the aggregated-scores best + worst preset pair + per-ticker audit.

    Args:
        snapshots_by_universe: Mapping of universe id to its latest
            snapshot list. First-seen universe wins on per-ticker dedup.
        snapshot_dates_by_universe: Per-universe ISO ``YYYY-MM-DD``
            snapshot date used for freshness gating.
        top_n: Each side of the ranking (default 25). Output is two
            lists, each up to ``top_n``.
        max_stale_days: Snapshots older than this are excluded.
        as_of: Reference date for the freshness gate. Defaults to today
            UTC; injected for deterministic tests.

    Returns:
        ``(best_tickers, worst_tickers, audit_rows)``. ``best_tickers``
        is the top-``top_n`` by ``screener_score``; ``worst_tickers`` is
        the bottom-``top_n``. Both sorted ASCII ascending. Disjoint sets.
        ``audit_rows`` has one entry per ticker encountered (including
        excluded ones); rank is ``+1..+top_n`` for best, ``-top_n..-1``
        for worst, ``None`` for excluded. A ticker is eligible iff its
        snapshot isn't stale and it has a non-``None`` ``screener_score``.
    """
    if as_of is None:
        as_of = datetime.now(UTC).date()
    if not snapshots_by_universe:
        return [], [], []

    per_ticker = dedup_by_ticker(snapshots_by_universe, snapshot_dates_by_universe)

    rows_by_ticker: dict[str, AuditRow] = {}
    eligible_with_score: list[tuple[str, float]] = []
    for ticker, info in per_ticker.items():
        row, score = _classify(ticker, info, as_of, max_stale_days)
        rows_by_ticker[ticker] = row
        if score is not None:
            eligible_with_score.append((ticker, score))

    eligible_with_score.sort(key=lambda x: (-x[1], x[0]))

    n = len(eligible_with_score)
    top_count = min(top_n, n)
    bottom_count = min(top_n, n - top_count)
    best_tickers: list[str] = []
    worst_tickers: list[str] = []
    for i in range(top_count):
        ticker, _ = eligible_with_score[i]
        rows_by_ticker[ticker] = rows_by_ticker[ticker].model_copy(
            update={"rank": i + 1},
        )
        best_tickers.append(ticker)
    for j in range(bottom_count):
        ticker, _ = eligible_with_score[n - 1 - j]
        rows_by_ticker[ticker] = rows_by_ticker[ticker].model_copy(
            update={"rank": -(j + 1)},
        )
        worst_tickers.append(ticker)

    return sorted(best_tickers), sorted(worst_tickers), list(rows_by_ticker.values())


def ranked_snapshots(
    snapshots_by_universe: dict[str, list[FundamentalsSnapshot]],
    snapshot_dates_by_universe: dict[str, str],
    tickers: Iterable[str],
) -> list[FundamentalsSnapshot]:
    """Return the exact per-ticker snapshot objects :func:`build_universe` ranked.

    Same dedup as :func:`build_universe` (first-seen universe wins). The
    build script uses this to emit the demo-display JSON for ``tickers``
    (``best_tickers + worst_tickers``) from the SAME records that were
    ranked -- never a second, independent fetch -- so a ticker shows the
    identical qte77 Score in the aggregated list and its source list for
    the same snapshot. Tickers absent from the dedup (shouldn't happen for
    a ``tickers`` list returned by ``build_universe`` on the same inputs)
    are silently skipped.
    """
    per_ticker = dedup_by_ticker(snapshots_by_universe, snapshot_dates_by_universe)
    return [per_ticker[t].snapshot for t in tickers if t in per_ticker]
