"""Tests for :mod:`analyze_stock_kpi.data_sources.options_oi` (plan 011).

Non-trivial behaviour only: level derivation (max pain, walls, ratio, null and
zero-OI handling), expiry selection incl. the holiday-Thursday monthly, the
(date, expiry_kind) merge key, wrap-degrade, and the raw-chain write path. One
``@pytest.mark.network`` smoke pins the live yfinance contract.
"""

from __future__ import annotations

import json
from datetime import date as date_cls
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

import pandas as pd
import pytest

from analyze_stock_kpi.data_sources.options_oi import (
    OptionsOiRow,
    _write_year,
    build_row,
    collect_options_oi,
    merge_rows_into_years,
    pick_expiries,
    write_raw_chains,
)

if TYPE_CHECKING:
    from pathlib import Path

_DAY = date_cls(2026, 11, 23)
_EXP = date_cls(2026, 11, 23)


def _recs(pairs: list[tuple[float, float | None]]) -> list[dict[str, float | None]]:
    return [{"strike": s, "openInterest": oi, "impliedVolatility": 0.2} for s, oi in pairs]


def _chain(
    calls: list[tuple[float, float | None]], puts: list[tuple[float, float | None]]
) -> dict[str, list[dict[str, float | None]]]:
    return {"calls": _recs(calls), "puts": _recs(puts)}


def _row(chain: dict[str, list[dict[str, float | None]]]) -> OptionsOiRow:
    return build_row(_DAY, "nearest", _EXP, chain)


# ----- build_row: levels -----


def test_max_pain_minimises_holder_payout() -> None:
    # Calls OI at 100/110, puts OI at 90/100: payout is 0 at K=100, 100 at 90 and 110.
    row = _row(_chain([(100, 10), (110, 10)], [(90, 10), (100, 10)]))
    assert row.max_pain == 100.0


def test_max_pain_tie_picks_lowest_strike() -> None:
    # One call and one put at the same OI around symmetric strikes: equal payout
    # at 100 and 110 (call 10@100, put 10@110 -> any K in [100,110] pays 100).
    row = _row(_chain([(100, 10)], [(110, 10)]))
    assert row.max_pain == 100.0


def test_call_wall_and_put_floor_ties_pick_lowest_strike() -> None:
    row = _row(_chain([(105, 5), (100, 5), (110, 1)], [(95, 7), (90, 7)]))
    assert row.call_wall == 100.0
    assert row.put_floor == 90.0


def test_pc_oi_ratio_and_total() -> None:
    row = _row(_chain([(100, 10)], [(100, 5)]))
    assert row.pc_oi_ratio == pytest.approx(0.5)
    assert row.total_oi == 15


def test_pc_oi_ratio_none_when_call_oi_zero() -> None:
    row = _row(_chain([(100, 0)], [(100, 5)]))
    assert row.pc_oi_ratio is None
    assert row.call_wall is None
    assert row.put_floor == 100.0


def test_null_oi_counts_as_zero_and_is_reported() -> None:
    row = _row(_chain([(100, 10), (110, None)], [(100, None), (90, 10)]))
    assert row.total_oi == 20
    assert row.oi_null_share == pytest.approx(0.5)


def test_zero_total_oi_keeps_row_with_none_levels() -> None:
    row = _row(_chain([(100, None)], [(100, 0)]))
    assert row.total_oi == 0
    assert (row.max_pain, row.call_wall, row.put_floor, row.pc_oi_ratio) == (None,) * 4
    assert row.oi_null_share == pytest.approx(0.5)


# ----- pick_expiries -----


def test_pick_nearest_is_first_on_or_after_today() -> None:
    listed = [date_cls(2026, 11, 20), date_cls(2026, 11, 23), date_cls(2026, 11, 24)]
    assert pick_expiries(listed, date_cls(2026, 11, 23))["nearest"] == date_cls(2026, 11, 23)


def test_pick_monthly_is_third_friday() -> None:
    listed = [date_cls(2026, 11, 23), date_cls(2026, 12, 11), date_cls(2026, 12, 18)]
    picks = pick_expiries(listed, date_cls(2026, 11, 23))
    assert picks["monthly"] == date_cls(2026, 12, 18)


def test_pick_monthly_holiday_thursday() -> None:
    # 2025-04-18 (third Friday, Good Friday) was closed; expiry listed Thu 04-17.
    listed = [date_cls(2025, 4, 14), date_cls(2025, 4, 17), date_cls(2025, 4, 25)]
    picks = pick_expiries(listed, date_cls(2025, 4, 14))
    assert picks["monthly"] == date_cls(2025, 4, 17)


def test_pick_monthly_is_friday_when_daily_expiries_are_listed() -> None:
    # Daily Mon-Fri expiries across the third-Friday week: Thursday must not win.
    listed = [date_cls(2026, 12, d) for d in (14, 15, 16, 17, 18)]
    assert pick_expiries(listed, date_cls(2026, 12, 14))["monthly"] == date_cls(2026, 12, 18)


def test_pick_ignores_non_third_week_thursday() -> None:
    listed = [date_cls(2026, 12, 10), date_cls(2026, 12, 18)]
    assert pick_expiries(listed, date_cls(2026, 12, 1))["monthly"] == date_cls(2026, 12, 18)


def test_pick_same_expiry_for_both_kinds() -> None:
    listed = [date_cls(2026, 12, 18), date_cls(2026, 12, 21)]
    picks = pick_expiries(listed, date_cls(2026, 12, 18))
    assert picks["nearest"] == picks["monthly"] == date_cls(2026, 12, 18)


# ----- collect_options_oi: mocked yfinance -----


def _frame(pairs: list[tuple[float, float | None]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "strike": [s for s, _ in pairs],
            "openInterest": [oi for _, oi in pairs],
            "impliedVolatility": [0.25] * len(pairs),
        }
    )


def _ticker(options: tuple[str, ...]) -> SimpleNamespace:
    def option_chain(_expiry: str) -> SimpleNamespace:
        return SimpleNamespace(
            calls=_frame([(100, 10), (110, None)]), puts=_frame([(90, 4), (100, 6)])
        )

    return SimpleNamespace(options=options, option_chain=option_chain)


def test_collect_writes_both_kinds_even_when_same_expiry() -> None:
    with patch(
        "analyze_stock_kpi.data_sources.options_oi.yf.Ticker",
        return_value=_ticker(("2026-12-18", "2026-12-21")),
    ):
        rows, raw = collect_options_oi(date_cls(2026, 12, 18))
    assert {r.expiry_kind for r in rows} == {"nearest", "monthly"}
    assert set(raw) == {"2026-12-18"}
    assert rows[0].total_oi == 20
    assert rows[0].oi_null_share == pytest.approx(0.25)
    assert raw["2026-12-18"]["calls"][1]["openInterest"] is None


def _boom(_expiry: str) -> None:
    raise ConnectionError("chain failed")


@pytest.mark.parametrize(
    "patch_kwargs",
    [
        {"side_effect": ConnectionError("yahoo timed out")},
        {"return_value": SimpleNamespace(options=("2026-11-23",), option_chain=_boom)},
    ],
    ids=["ticker_error", "chain_error"],
)
def test_collect_wrap_degrades_on_yfinance_error(patch_kwargs: dict[str, object]) -> None:
    with patch("analyze_stock_kpi.data_sources.options_oi.yf.Ticker", **patch_kwargs):
        assert collect_options_oi(_DAY) == ([], {})


# ----- raw write path + merge -----


def test_write_raw_chains_path_and_payload(tmp_path: Path) -> None:
    raw = {"2026-11-23": _chain([(100, 1)], [(90, None)])}
    path = write_raw_chains(_DAY, raw, root=tmp_path)
    assert path == tmp_path / "options" / "SPY" / "2026-11-23.json"
    assert json.loads(path.read_text()) == raw


def test_merge_replaces_same_day_rows_keyed_by_kind(tmp_path: Path) -> None:
    def row(kind: str, oi: float) -> OptionsOiRow:
        return build_row(_DAY, kind, _EXP, _chain([(100, oi)], [(100, 1)]))  # type: ignore[arg-type]

    first = merge_rows_into_years([row("nearest", 5), row("monthly", 5)], root=tmp_path)
    _write_year(2026, first[2026], root=tmp_path)
    by_year = merge_rows_into_years([row("nearest", 9)], root=tmp_path)
    year = by_year[2026]
    assert len(year) == 2
    assert year[("2026-11-23", "nearest")].total_oi == 10
    assert year[("2026-11-23", "monthly")].total_oi == 6


@pytest.mark.network
def test_live_collect_options_oi() -> None:
    """One live round-trip — pins that yfinance still ships SPY chains with OI."""
    rows, raw = collect_options_oi(pd.Timestamp.now(tz="UTC").date())
    assert {r.expiry_kind for r in rows} == {"nearest", "monthly"}
    assert raw
    assert all(r.total_oi > 0 for r in rows)
