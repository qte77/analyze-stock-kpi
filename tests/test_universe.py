"""Tests for ``src.universe.resolve_universe``.

Per the project's "tests must add value" rule, these cover **only**
non-trivial behavior: precedence, parsing edge cases, and error paths.
Happy-path "returns a list of strings" is not tested — pydantic validates
the input shape at the CliArgs boundary.
"""

from pathlib import Path

import pytest

from analyze_stock_kpi.domain.universe import UniverseError, resolve_universe
from analyze_stock_kpi.utils.parse_args import CliArgs


def _args(**overrides: object) -> CliArgs:
    """Build a CliArgs without parsing sys.argv (model_construct skips validation)."""
    base: dict[str, object] = {
        "universe": "qte77-watchlist",
        "tickers": None,
        "tickers_file": None,
    }
    base.update(overrides)
    return CliArgs.model_construct(**base)


# precedence


def test_tickers_inline_wins_over_file_and_universe(tmp_path: Path) -> None:
    """Inline ``tickers`` takes precedence over both ``tickers_file`` and ``universe``."""
    file = tmp_path / "ignored.txt"
    file.write_text("ZZZZ\n")
    args = _args(tickers="AAPL,MSFT", tickers_file=file, universe="qte77-watchlist")
    assert resolve_universe(args) == ["AAPL", "MSFT"]


def test_tickers_file_wins_over_universe(tmp_path: Path) -> None:
    """``tickers_file`` takes precedence over ``universe`` when ``tickers`` is unset."""
    file = tmp_path / "list.txt"
    file.write_text("VTI\nVXUS\n")
    args = _args(tickers_file=file, universe="qte77-watchlist")
    assert resolve_universe(args) == ["VTI", "VXUS"]


# parsing edge cases (the actual logic worth testing)


def test_inline_tickers_strip_whitespace_and_dedup() -> None:
    """Comma-split tolerates whitespace; duplicates collapse, first-seen order kept."""
    args = _args(tickers=" AAPL ,MSFT,  AAPL ,GOOGL")
    assert resolve_universe(args) == ["AAPL", "MSFT", "GOOGL"]


def test_symbol_file_skips_comments_and_blanks(tmp_path: Path) -> None:
    """``#`` comments (full-line and trailing) and blank lines are ignored."""
    file = tmp_path / "u.txt"
    file.write_text(
        "# header comment\nAAPL\n\nMSFT  # inline comment\n  # indented comment\nGOOGL\n"
    )
    args = _args(tickers_file=file)
    assert resolve_universe(args) == ["AAPL", "MSFT", "GOOGL"]


# error paths


def test_missing_preset_raises_universe_error() -> None:
    """Resolving an unknown preset name surfaces a clear, actionable error."""
    args = _args(universe="does-not-exist")
    with pytest.raises(UniverseError, match="universe file not found"):
        resolve_universe(args)


def test_missing_tickers_file_raises_universe_error(tmp_path: Path) -> None:
    """Pointing at a non-existent file fails with a path-explicit error."""
    args = _args(tickers_file=tmp_path / "nope.txt")
    with pytest.raises(UniverseError, match="universe file not found"):
        resolve_universe(args)


def test_empty_inline_tickers_raises_universe_error() -> None:
    """A ``tickers`` string of only whitespace/commas resolves to an empty list and fails."""
    args = _args(tickers="  , , ")
    with pytest.raises(UniverseError, match="empty"):
        resolve_universe(args)


def test_empty_symbol_file_raises_universe_error(tmp_path: Path) -> None:
    """A file with only comments / blanks resolves to an empty list and fails."""
    file = tmp_path / "empty.txt"
    file.write_text("# only a comment\n\n# another\n")
    args = _args(tickers_file=file)
    with pytest.raises(UniverseError, match="empty"):
        resolve_universe(args)


def test_empty_preset_tolerated_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An existing-but-empty preset returns ``[]`` instead of raising.

    Per the orchestrator-driven case (#192 Phase 2a): the longshort presets
    start as 0-byte placeholders until the first cron populates them. The
    demo-snapshot cron must be able to ``make run UNIVERSE=…`` over an
    empty preset and produce an empty snapshot rather than abort.
    """
    preset_dir = tmp_path / "universes"
    preset_dir.mkdir()
    (preset_dir / "phase2a-longs.txt").write_text("")
    monkeypatch.setattr("analyze_stock_kpi.domain.universe.PRESET_DIR", preset_dir)
    args = _args(universe="phase2a-longs")
    assert resolve_universe(args) == []


# preset shipping smoke check (catches accidental deletion of qte77-watchlist)


def test_default_preset_resolves_to_nonempty_list() -> None:
    """The shipped default preset must always resolve."""
    args = _args()
    result = resolve_universe(args)
    assert len(result) > 0
    assert all(isinstance(s, str) and s for s in result)


def test_federal_contractors_preset_resolves_to_curated_seed() -> None:
    """The bundled `federal-contractors` preset includes the DoD Top-25 seed."""
    from analyze_stock_kpi.orchestrators.federal_contractors import CURATED_TICKERS

    args = _args(universe="federal-contractors")
    result = resolve_universe(args)

    seed = {ticker for _, ticker in CURATED_TICKERS}
    assert seed.issubset(set(result))
