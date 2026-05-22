"""Tests for :mod:`src.fundamentals`."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from src.data_sources.fundamentals import (
    FundamentalsSnapshot,
    fetch_fundamentals,
    fetch_price_history,
    fetch_universe_fundamentals,
)

from tests.conftest import load_fundamentals_fixture


def test_snapshot_parses_full_info_dict() -> None:
    info = load_fundamentals_fixture("AAPL")
    snap = FundamentalsSnapshot.model_validate(info)
    assert snap.symbol == "AAPL"
    assert snap.long_name == "Apple Inc."
    assert snap.sector == "Technology"
    assert snap.quote_type == "EQUITY"
    assert snap.market_cap is not None
    assert snap.market_cap > 0
    assert snap.trailing_pe == 32.5
    assert snap.return_on_equity == 1.45
    assert snap.dividend_yield == 0.0048
    assert snap.beta == 1.24
    assert snap.trailing_peg_ratio == 1.4


def test_snapshot_parses_trailing_peg_ratio() -> None:
    """Trailing PEG ratio populates via the yfinance ``trailingPegRatio`` alias.

    yfinance ships ``info["pegRatio"]`` broken since June 2025 (issue #2570);
    ``trailingPegRatio`` continues to work and is fetched from a separate
    fundamentals-timeseries endpoint. We model only the working one.
    """
    snap = FundamentalsSnapshot.model_validate(
        {"symbol": "X", "trailingPegRatio": 1.23}
    )
    assert snap.trailing_peg_ratio == 1.23


def test_normalize_yfinance_info_divides_dividend_yield() -> None:
    """Recent yfinance ships dividendYield as a percentage value (e.g.
    0.37 for AAPL's 0.37 %). `_normalize_yfinance_info` divides by 100 at
    the fetch boundary so the rest of the codebase sees a fraction.
    """
    from src.data_sources.fundamentals import _normalize_yfinance_info

    normalized = _normalize_yfinance_info({"dividendYield": 0.37, "trailingPE": 35.0})
    assert normalized["dividendYield"] == 0.0037
    assert normalized["trailingPE"] == 35.0  # untouched


def test_normalize_yfinance_info_handles_missing_yield() -> None:
    """Sparse snapshots (FX, futures, crypto) have no `dividendYield` key.
    The normalizer leaves the input dict structurally unchanged.
    """
    from src.data_sources.fundamentals import _normalize_yfinance_info

    assert _normalize_yfinance_info({"symbol": "X"}) == {"symbol": "X"}


def test_fetch_fundamentals_normalizes_live_yield() -> None:
    """End-to-end: a mocked yf.Ticker.info shipping percentage-shaped
    dividendYield (current schema) reaches `fetch_fundamentals` and
    emerges with a fractional value on the snapshot.
    """
    from unittest.mock import patch

    class _FakeTicker:
        info: ClassVar[dict[str, object]] = {
            "symbol": "AAPL",
            "shortName": "Apple Inc.",
            "dividendYield": 0.37,  # current yfinance: percentage-shaped
        }

    with patch("src.data_sources.fundamentals.yf.Ticker", return_value=_FakeTicker()):
        snap = fetch_fundamentals("AAPL")
    assert snap.dividend_yield == 0.0037


def test_compute_roi_full_inputs() -> None:
    """ROI computed from five raw ``info`` keys.

    Inputs chosen so the arithmetic is exact:
    book_equity = marketCap / priceToBook = 1000 / 10 = 100
    invested_capital = book_equity + totalDebt - totalCash = 100 + 50 - 30 = 120
    roi = netIncomeToCommon / invested_capital = 24 / 120 = 0.20
    """
    from src.data_sources.fundamentals import _compute_roi

    info = {
        "netIncomeToCommon": 24.0,
        "marketCap": 1000.0,
        "priceToBook": 10.0,
        "totalDebt": 50.0,
        "totalCash": 30.0,
    }
    assert _compute_roi(info) == 0.20


def test_compute_roi_missing_input_returns_none() -> None:
    """A single missing input collapses ROI to ``None``."""
    from src.data_sources.fundamentals import _compute_roi

    info = {
        "netIncomeToCommon": 24.0,
        "marketCap": 1000.0,
        # priceToBook missing — ROI is not computable
        "totalDebt": 50.0,
        "totalCash": 30.0,
    }
    assert _compute_roi(info) is None


def test_compute_roi_zero_price_to_book_returns_none() -> None:
    """Avoid ``ZeroDivisionError`` when book equity cannot be derived."""
    from src.data_sources.fundamentals import _compute_roi

    info = {
        "netIncomeToCommon": 24.0,
        "marketCap": 1000.0,
        "priceToBook": 0.0,
        "totalDebt": 50.0,
        "totalCash": 30.0,
    }
    assert _compute_roi(info) is None


def test_compute_roi_zero_invested_capital_returns_none() -> None:
    """``book_equity + totalDebt - totalCash == 0`` -> ``None``.

    Inputs: book_equity = 100, debt = 0, cash = 100 -> invested_capital = 0.
    """
    from src.data_sources.fundamentals import _compute_roi

    info = {
        "netIncomeToCommon": 24.0,
        "marketCap": 1000.0,
        "priceToBook": 10.0,
        "totalDebt": 0.0,
        "totalCash": 100.0,
    }
    assert _compute_roi(info) is None


def test_fetch_fundamentals_attaches_roi() -> None:
    """End-to-end: a mocked yfinance ``info`` dict with the five ROI
    inputs reaches the snapshot's ``roi`` field via ``model_copy``."""

    class _FakeTicker:
        info: ClassVar[dict[str, object]] = {
            "symbol": "AAPL",
            "shortName": "Apple Inc.",
            "netIncomeToCommon": 24.0,
            "marketCap": 1000.0,
            "priceToBook": 10.0,
            "totalDebt": 50.0,
            "totalCash": 30.0,
        }

    with patch("src.data_sources.fundamentals.yf.Ticker", return_value=_FakeTicker()):
        snap = fetch_fundamentals("AAPL")
    assert snap.roi == 0.20


def test_fetch_rd_to_revenue_equity_happy_path() -> None:
    """R&D / Total Revenue read from the latest income_stmt column.

    Chosen so the arithmetic is exact: 20 / 100 = 0.20.
    """
    import pandas as pd
    from src.data_sources.fundamentals import _fetch_rd_to_revenue

    income_stmt = pd.DataFrame(
        {"latest": [20.0, 100.0]},
        index=["Research And Development", "Total Revenue"],
    )
    fake = SimpleNamespace(income_stmt=income_stmt)
    assert _fetch_rd_to_revenue(fake, {"quoteType": "EQUITY"}) == 0.20


def test_fetch_rd_to_revenue_non_equity_skips_fetch() -> None:
    """Non-EQUITY quote types must not touch ``.income_stmt``."""
    from src.data_sources.fundamentals import _fetch_rd_to_revenue

    class _Tripwire:
        @property
        def income_stmt(self) -> None:
            raise AssertionError("income_stmt accessed for non-EQUITY ticker")

    assert _fetch_rd_to_revenue(_Tripwire(), {"quoteType": "ETF"}) is None


def test_fetch_rd_to_revenue_missing_quote_type_returns_none() -> None:
    """Missing ``quoteType`` is treated as non-EQUITY (defensive)."""
    from src.data_sources.fundamentals import _fetch_rd_to_revenue

    class _Tripwire:
        @property
        def income_stmt(self) -> None:
            raise AssertionError("income_stmt accessed when quoteType absent")

    assert _fetch_rd_to_revenue(_Tripwire(), {}) is None


def test_fetch_rd_to_revenue_missing_row_returns_none() -> None:
    """``income_stmt`` without an ``Research And Development`` row -> ``None``."""
    import pandas as pd
    from src.data_sources.fundamentals import _fetch_rd_to_revenue

    income_stmt = pd.DataFrame(
        {"latest": [100.0, 50.0]},
        index=["Total Revenue", "Net Income"],
    )
    fake = SimpleNamespace(income_stmt=income_stmt)
    assert _fetch_rd_to_revenue(fake, {"quoteType": "EQUITY"}) is None


def test_fetch_rd_to_revenue_zero_revenue_returns_none() -> None:
    """Avoid ``ZeroDivisionError`` when Total Revenue is zero."""
    import pandas as pd
    from src.data_sources.fundamentals import _fetch_rd_to_revenue

    income_stmt = pd.DataFrame(
        {"latest": [20.0, 0.0]},
        index=["Research And Development", "Total Revenue"],
    )
    fake = SimpleNamespace(income_stmt=income_stmt)
    assert _fetch_rd_to_revenue(fake, {"quoteType": "EQUITY"}) is None


def test_fetch_rd_to_revenue_exception_returns_none() -> None:
    """Network errors / IFRS schema drift swallowed; returns ``None``."""
    from src.data_sources.fundamentals import _fetch_rd_to_revenue

    class _Broken:
        @property
        def income_stmt(self) -> None:
            raise RuntimeError("simulated yfinance failure")

    assert _fetch_rd_to_revenue(_Broken(), {"quoteType": "EQUITY"}) is None


def test_fetch_fundamentals_attaches_rd_to_revenue() -> None:
    """End-to-end: rd_to_revenue lands on the snapshot for an EQUITY ticker."""
    import pandas as pd

    income_stmt_df = pd.DataFrame(
        {"latest": [20.0, 100.0]},
        index=["Research And Development", "Total Revenue"],
    )

    class _FakeTicker:
        info: ClassVar[dict[str, object]] = {
            "symbol": "AAPL",
            "shortName": "Apple Inc.",
            "quoteType": "EQUITY",
        }
        income_stmt = income_stmt_df

    with patch("src.data_sources.fundamentals.yf.Ticker", return_value=_FakeTicker()):
        snap = fetch_fundamentals("AAPL")
    assert snap.rd_to_revenue == 0.20


def test_compute_sortino_positive_skew_series() -> None:
    """Sortino > 0 for a mostly-up series with a single drawdown.

    Construct 31 prices via cumulative product of 29 returns of +0.5%
    plus one of -5%. Daily mean = 0.095/30 ≈ 0.003167; annualized
    ≈ 0.798. Downside-deviation squared mean = 0.05^2 / 30 ≈ 8.33e-5;
    annualized ≈ 0.1449. Sortino ≈ 5.51.
    """
    import pandas as pd
    from src.data_sources.fundamentals import _compute_sortino

    returns = [0.005] * 29 + [-0.05]
    prices = [100.0]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    close = pd.Series(prices)
    sortino = _compute_sortino(close)
    assert sortino is not None
    assert sortino == pytest.approx(5.51, rel=1e-2)


def test_compute_sortino_too_few_datapoints_returns_none() -> None:
    """Series shorter than 30 returns -> ``None`` (insufficient sample)."""
    import pandas as pd
    from src.data_sources.fundamentals import _compute_sortino

    close = pd.Series([100.0 + i for i in range(20)])
    assert _compute_sortino(close) is None


def test_compute_sortino_all_positive_returns_none() -> None:
    """No losing days -> downside_dev is zero -> ``None`` (undefined)."""
    import pandas as pd
    from src.data_sources.fundamentals import _compute_sortino

    close = pd.Series([100.0 * (1.001 ** i) for i in range(50)])
    assert _compute_sortino(close) is None


def test_compute_sortino_with_target_annual_shifts_result() -> None:
    """``target_annual`` subtracts a daily MAR from each return.

    Same positive-skew series as ``test_compute_sortino_positive_skew_series``
    (29 returns of +0.005, 1 of -0.05). With ``target_annual = 0`` the
    Sortino is ≈ 5.51. With ``target_annual = 1.26`` (daily target
    = 0.005) every "up" day becomes an excess of 0 and the single
    down day becomes -0.055, flipping the sign:

    mean(excess) * 252 = (-0.055 / 30) * 252 ≈ -0.4620
    downside_dev_daily = sqrt((0.055^2) / 30) ≈ 0.01004
    downside_dev_annual = 0.01004 * sqrt(252) ≈ 0.15942
    sortino = -0.4620 / 0.15942 ≈ -2.898

    Confirms the canonical Sortino convention `(R - T) / DR` rather
    than our prior T=0-only behaviour.
    """
    import pandas as pd
    from src.data_sources.fundamentals import _compute_sortino

    returns = [0.005] * 29 + [-0.05]
    prices = [100.0]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    close = pd.Series(prices)
    sortino = _compute_sortino(close, target_annual=1.26)
    assert sortino is not None
    assert sortino == pytest.approx(-2.898, rel=1e-2)


def test_compute_sortino_empty_series_returns_none() -> None:
    """Empty close-series -> ``None``."""
    import pandas as pd
    from src.data_sources.fundamentals import _compute_sortino

    assert _compute_sortino(pd.Series([], dtype=float)) is None


def test_snapshot_handles_sparse_info() -> None:
    info = load_fundamentals_fixture("GC=F")
    snap = FundamentalsSnapshot.model_validate(info)
    assert snap.symbol == "GC=F"
    assert snap.quote_type == "FUTURE"
    assert snap.currency == "USD"
    assert snap.market_cap is None
    assert snap.trailing_pe is None
    assert snap.return_on_equity is None
    assert snap.dividend_yield is None


def test_snapshot_extra_keys_ignored() -> None:
    info = {
        "symbol": "TEST",
        "longName": "Test Co",
        "junkKey1": "x",
        "another_junk": 42,
    }
    snap = FundamentalsSnapshot.model_validate(info)
    assert snap.symbol == "TEST"
    assert snap.long_name == "Test Co"


def test_snapshot_is_frozen() -> None:
    snap = FundamentalsSnapshot(symbol="X")
    with pytest.raises(ValidationError):
        snap.symbol = "Y"  # type: ignore[misc]


def test_fetch_universe_continues_on_error(caplog: pytest.LogCaptureFixture) -> None:
    aapl_info = load_fundamentals_fixture("AAPL")
    gold_info = load_fundamentals_fixture("GC=F")

    class _FakeTicker:
        def __init__(self, info: dict) -> None:
            self.info = info

    def fake_ticker(symbol: str) -> _FakeTicker:
        if symbol == "BROKEN":
            raise RuntimeError("simulated yfinance failure")
        return _FakeTicker(aapl_info if symbol == "AAPL" else gold_info)

    with (
        caplog.at_level("WARNING", logger="src.data_sources.fundamentals"),
        patch("src.data_sources.fundamentals.yf.Ticker", side_effect=fake_ticker),
        patch(
            "src.data_sources.fundamentals.yf.download",
            side_effect=RuntimeError("batch skipped in unit test"),
        ),
    ):
        results = fetch_universe_fundamentals(
            ["AAPL", "BROKEN", "GC=F"], show_progress=False
        )

    assert len(results) == 2
    assert {s.symbol for s in results} == {"AAPL", "GC=F"}
    assert any("BROKEN" in rec.message for rec in caplog.records)


def test_fetch_universe_fundamentals_attaches_sortino_via_batch() -> None:
    """Batched ``yf.download`` at universe level feeds per-ticker Sortino.

    The orchestrator calls ``yf.download(tickers, period="1y", ...)``
    once before the per-ticker loop. Each snapshot's ``sortino_ratio``
    is attached via ``model_copy`` from the matching column of the
    batched close-price DataFrame.
    """
    import pandas as pd

    returns_mixed = [0.005] * 29 + [-0.05]
    prices_mixed = [100.0]
    for r in returns_mixed:
        prices_mixed.append(prices_mixed[-1] * (1 + r))
    prices_uptrend = [100.0 * (1.001**i) for i in range(31)]

    close_df = pd.DataFrame(
        {
            ("Close", "AAPL"): prices_mixed,
            ("Close", "MSFT"): prices_uptrend,
        }
    )
    close_df.columns = pd.MultiIndex.from_tuples(close_df.columns)

    class _FakeTicker:
        def __init__(self, info: dict) -> None:
            self.info = info

    aapl_info = {"symbol": "AAPL", "shortName": "Apple", "quoteType": "EQUITY"}
    msft_info = {"symbol": "MSFT", "shortName": "Microsoft", "quoteType": "EQUITY"}

    def fake_ticker(symbol: str) -> _FakeTicker:
        return _FakeTicker(aapl_info if symbol == "AAPL" else msft_info)

    with (
        patch("src.data_sources.fundamentals.yf.Ticker", side_effect=fake_ticker),
        patch("src.data_sources.fundamentals.yf.download", return_value=close_df) as mock_dl,
    ):
        snapshots = fetch_universe_fundamentals(
            ["AAPL", "MSFT"], show_progress=False
        )

    mock_dl.assert_called_once()
    call_args = mock_dl.call_args
    assert call_args.args[0] == ["AAPL", "MSFT"]
    assert call_args.kwargs.get("period") == "1y"

    by_symbol = {s.symbol: s for s in snapshots}
    assert by_symbol["AAPL"].sortino_ratio == pytest.approx(5.51, rel=1e-2)
    # MSFT had only positive returns -> downside_dev = 0 -> Sortino is None
    assert by_symbol["MSFT"].sortino_ratio is None


def test_fetch_universe_fundamentals_batch_failure_gives_none_sortino() -> None:
    """``yf.download`` raising -> all snapshots get ``sortino_ratio=None``."""

    class _FakeTicker:
        info: ClassVar[dict[str, object]] = {
            "symbol": "AAPL",
            "shortName": "Apple",
            "quoteType": "EQUITY",
        }

    with (
        patch("src.data_sources.fundamentals.yf.Ticker", return_value=_FakeTicker()),
        patch(
            "src.data_sources.fundamentals.yf.download",
            side_effect=RuntimeError("simulated batch failure"),
        ),
    ):
        snapshots = fetch_universe_fundamentals(["AAPL"], show_progress=False)

    assert len(snapshots) == 1
    assert snapshots[0].sortino_ratio is None


@pytest.mark.network
def test_live_fetch_aapl() -> None:
    snap = fetch_fundamentals("AAPL")
    assert snap.symbol == "AAPL"
    assert snap.market_cap is not None
    assert snap.market_cap > 0
    assert snap.sector is not None


@pytest.mark.network
def test_live_fetch_history_returns_dataframe() -> None:
    df = fetch_price_history("AAPL", period="1mo")
    assert not df.empty
    assert "Close" in df.columns


def test_snapshot_accepts_sec_last_filed_fields() -> None:
    """`sec_last_10k_date / 10q / 8k` are optional date fields on the model."""
    snap = FundamentalsSnapshot(
        symbol="AAPL",
        sec_last_10k_date=date(2024, 11, 1),
        sec_last_10q_date=date(2024, 8, 2),
        sec_last_8k_date=date(2024, 10, 31),
    )

    assert snap.sec_last_10k_date == date(2024, 11, 1)
    assert snap.sec_last_10q_date == date(2024, 8, 2)
    assert snap.sec_last_8k_date == date(2024, 10, 31)


def test_snapshot_attaches_sec_fields_via_model_copy() -> None:
    """SEC enrichment fields round-trip via `model_copy(update=...)`."""
    snap = FundamentalsSnapshot(symbol="AAPL")

    enriched = snap.model_copy(
        update={
            "sec_last_10k_date": date(2024, 11, 1),
            "sec_last_10q_date": date(2024, 8, 2),
            "sec_last_8k_date": date(2024, 10, 31),
        }
    )

    assert enriched.sec_last_10k_date == date(2024, 11, 1)
    assert enriched.sec_last_10q_date == date(2024, 8, 2)
    assert enriched.sec_last_8k_date == date(2024, 10, 31)


def test_snapshot_sec_fields_default_none() -> None:
    """Without enrichment, the three SEC date fields default to None."""
    snap = FundamentalsSnapshot(symbol="AAPL")

    assert snap.sec_last_10k_date is None
    assert snap.sec_last_10q_date is None
    assert snap.sec_last_8k_date is None
