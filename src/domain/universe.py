"""Asset universe resolver.

A universe is the list of Yahoo-symbol tickers a single ``make run`` invocation
will operate on. The resolver accepts three input modes (precedence highest
first); exactly one wins:

1. ``CliArgs.tickers`` — comma-separated symbols, e.g. ``"AAPL,SPY,EURUSD=X"``
2. ``CliArgs.tickers_file`` — path to a file with one symbol per line
3. ``CliArgs.universe`` — preset name; resolved against
   :data:`PRESET_DIR` (``src/assets/universes/<name>.txt``)

Preset files and inline ticker files use the same format: one Yahoo symbol per
line, ``#`` and blank lines ignored.

See :mod:`src.utils.parse_args` for the ``CliArgs`` shape and
``docs/architecture.md`` for module placement.
"""

from pathlib import Path

from src.utils.parse_args import CliArgs

PRESET_DIR = Path(__file__).parent.parent / "assets" / "universes"


class UniverseError(ValueError):
    """Raised when a universe spec cannot be resolved into a non-empty ticker list."""


def resolve_universe(args: CliArgs) -> list[str]:
    """Resolve the active asset universe from ``args``.

    Precedence: ``tickers`` > ``tickers_file`` > ``universe`` (preset name).
    Returns a list of stripped, deduplicated Yahoo symbols.

    Raises :class:`UniverseError` when:

    - the requested preset / file is missing (fail-loud — config error), or
    - inline ``tickers`` / ``tickers_file`` modes resolve to an empty list
      (fail-loud — operator typo / wrong file)

    Preset mode tolerates an existing-but-empty file and returns ``[]``.
    This is the orchestrator-driven case: ``enhanced-kpi-screener-longs``
    starts as a 0-byte placeholder until the first cron populates it, and
    later cron passes can also yield zero candidates conjunctively (per
    issue #192's "counts vary; could be 0 each side"). An empty preset is
    a valid state; ``make run UNIVERSE=…`` over it produces an empty
    snapshot rather than aborting the demo-snapshot cron.
    """
    if args.tickers is not None:
        symbols = _split_csv_tickers(args.tickers)
    elif args.tickers_file is not None:
        symbols = _read_symbol_file(args.tickers_file)
    else:
        # Preset mode: tolerate empty (orchestrator-driven; see docstring).
        return _read_symbol_file(PRESET_DIR / f"{args.universe}.txt")

    if not symbols:
        raise UniverseError("resolved universe is empty")
    return symbols


def _split_csv_tickers(raw: str) -> list[str]:
    """Parse ``"AAPL, SPY ,EURUSD=X"`` -> ``["AAPL", "SPY", "EURUSD=X"]``."""
    return _dedup_preserve([s.strip() for s in raw.split(",") if s.strip()])


def _read_symbol_file(path: Path) -> list[str]:
    """Read one-symbol-per-line file. Strips ``#`` comments and blank lines.

    Raises :class:`UniverseError` if the file does not exist (so user-facing
    errors are actionable instead of falling through as generic OSError).
    """
    if not path.is_file():
        raise UniverseError(f"universe file not found: {path}")
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    return _dedup_preserve(_strip_comments(raw_lines))


def _strip_comments(lines: list[str]) -> list[str]:
    """Drop blank lines and ``#``-prefixed comments; strip whitespace."""
    cleaned: list[str] = []
    for line in lines:
        token = line.split("#", 1)[0].strip()
        if token:
            cleaned.append(token)
    return cleaned


def _dedup_preserve(items: list[str]) -> list[str]:
    """Remove duplicates while preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
