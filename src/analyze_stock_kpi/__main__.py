"""analyze-stock-kpi entrypoint.

Resolves the active asset universe, prints a CNN Fear & Greed sentiment
banner, fetches fundamentals via yfinance, prints an equities/ETF summary
table, and persists every snapshot (including sparse ones for
FX/futures/crypto) to ``results/fundamentals/<UTC>.json``.
"""

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .config import settings
from .data_sources.fundamentals import (
    FundamentalsSnapshot,
    fetch_universe_fundamentals,
)
from .data_sources.sec.submissions import enrich_snapshot_sec
from .data_sources.sentiment import FearGreedSnapshot, fetch_fear_greed
from .domain.composite_scores import CompositeScores, compute_scores
from .domain.universe import resolve_universe
from .orchestrators.federal_contractors import build_universe
from .utils.parse_args import CliArgs

_TABLE_QUOTE_TYPES = {"EQUITY", "ETF"}

logger = logging.getLogger(__name__)


def _format_ratio(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "-"


def _format_percent(value: float | None) -> str:
    return f"{value * 100:.2f}%" if value is not None else "-"


def _format_score(value: float | None) -> str:
    return f"{value:.0f}" if value is not None else "-"


_STALE_10Q_DAYS = 150


def _format_days_since(filing_date: date | None, *, today: date | None = None) -> str:
    """Format an EDGAR last-filed date as "Nd"; "-" when missing.

    Wraps in Rich ``[red]…[/red]`` markup when N exceeds the >150d
    staleness threshold (US issuers normally file 10-Q quarterly; a
    gap longer than 150d signals delisting, restatement, or foreign-
    filer status).
    """
    if filing_date is None:
        return "-"
    today = today or datetime.now(UTC).date()
    n = (today - filing_date).days
    return f"[red]{n}d[/red]" if n > _STALE_10Q_DAYS else f"{n}d"


def _print_sentiment_banner(console: Console, snapshot: FearGreedSnapshot) -> None:
    stamp = snapshot.timestamp.strftime("%Y-%m-%d %H:%M %Z").strip()
    console.print(
        f"[bold]Fear & Greed[/bold] "
        f"[cyan]{snapshot.score:.1f}[/cyan] "
        f"([italic]{snapshot.rating}[/italic]) as of {stamp}"
    )


def _score_columns(snap: FundamentalsSnapshot) -> list[str]:
    scores = snap.composite_scores or CompositeScores()
    return [
        _format_score(scores.quality),
        _format_score(scores.dividend),
        _format_score(scores.growth),
    ]


def _summary_row(snap: FundamentalsSnapshot, show_scores: bool) -> list[str]:
    scores = snap.composite_scores or CompositeScores()
    row = [
        snap.symbol,
        snap.long_name or "-",
        snap.sector or "-",
        _format_ratio(snap.forward_pe),
        _format_ratio(snap.trailing_peg_ratio),
        _format_ratio(snap.beta),
        _format_percent(snap.rd_to_revenue),
        _format_percent(snap.operating_margins),
        _format_percent(snap.return_on_equity),
        _format_percent(snap.return_on_assets),
        _format_ratio(snap.current_ratio),
        _format_ratio(snap.sortino_ratio),
        _format_score(scores.screener_score),
        _format_days_since(snap.sec_last_10q_date),
    ]
    if show_scores:
        row += _score_columns(snap)
    return row


def _print_summary_table(
    console: Console,
    snapshots: list[FundamentalsSnapshot],
    *,
    show_scores: bool = False,
) -> None:
    """Mirrors the demo dashboard's 13-column default view (`ui/`).

    With ``--show-scores`` (env ``SSK_SHOW_SCORES=1``) three legacy
    composite columns (Quality / Dividend / Growth) are appended for
    backwards compatibility.
    """
    table = Table(title="Fundamentals (equities & ETFs)")
    table.add_column("Ticker", style="bold")
    table.add_column("Name")
    table.add_column("Sector")
    table.add_column("P/E (fwd)", justify="right")
    table.add_column("PEG", justify="right")
    table.add_column("Beta", justify="right")
    table.add_column("R&D/Rev %", justify="right")
    table.add_column("Op M %", justify="right")
    table.add_column("ROE %", justify="right")
    table.add_column("ROA %", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Sortino", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Days 10-Q", justify="right")
    if show_scores:
        table.add_column("Quality", justify="right")
        table.add_column("Div", justify="right")
        table.add_column("Growth", justify="right")

    for snap in snapshots:
        if snap.quote_type not in _TABLE_QUOTE_TYPES:
            continue
        table.add_row(*_summary_row(snap, show_scores))
    console.print(table)


def _run_refresh_universe(args: CliArgs) -> Path:
    """Run an orchestrator and persist its outputs; return the preset path."""
    tickers, audit_rows = build_universe()
    base = settings.federal_contractors_dir
    preset_path = args.output or base / "universe.txt"
    audit_path = args.audit_output or (
        base / "audit" / f"{datetime.now(UTC).strftime('%Y-%m-%d')}.json"
    )
    preset_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    preset_path.write_text("\n".join(tickers) + "\n")
    audit_path.write_text(json.dumps([row.model_dump() for row in audit_rows], indent=2))
    return preset_path


def _persist_snapshots(snapshots: list[FundamentalsSnapshot]) -> Path:
    settings.fundamentals_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = settings.fundamentals_dir / f"{stamp}.json"
    payload = [s.model_dump(by_alias=False, mode="json") for s in snapshots]
    out_path.write_text(json.dumps(payload, indent=2))
    return out_path


def main() -> None:
    """Entrypoint: resolve universe, fetch fundamentals, print + persist."""
    console = Console()
    args = CliArgs()
    if args.refresh_universe:
        out_path = _run_refresh_universe(args)
        console.print(f"[green]Wrote universe preset[/green] {out_path}")
        return
    try:
        _print_sentiment_banner(console, fetch_fear_greed())
    except Exception as exc:
        logger.warning("Failed to fetch CNN Fear & Greed: %s", exc)
    tickers = resolve_universe(args)
    console.print(f"[green]analyze-stock-kpi[/green] resolving [bold]{len(tickers)}[/bold] tickers")
    raw_snapshots = fetch_universe_fundamentals(tickers)
    snapshots = [
        snap.model_copy(
            update={
                "composite_scores": compute_scores(snap),
                **enrich_snapshot_sec(snap.symbol),
            }
        )
        for snap in raw_snapshots
    ]
    _print_summary_table(console, snapshots, show_scores=args.show_scores)
    out_path = _persist_snapshots(snapshots)
    console.print(f"[green]Wrote[/green] {out_path}")


if __name__ == "__main__":
    main()
