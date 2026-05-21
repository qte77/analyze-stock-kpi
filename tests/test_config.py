"""Tests for :mod:`src.config` — runtime config defaults + env override."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.config import AppSettings

if TYPE_CHECKING:
    import pytest


def test_app_settings_defaults_match_pre_refactor_literals() -> None:
    """Default values reproduce the constants that lived in per-module code."""
    s = AppSettings()
    assert s.edgar_tickers_url == (
        "https://www.sec.gov/files/company_tickers_exchange.json"
    )
    assert s.edgar_submissions_url_template == (
        "https://data.sec.gov/submissions/CIK{cik}.json"
    )
    assert s.edgar_cache_dir == Path("results/edgar")
    assert s.cnn_fg_url == (
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    )
    assert s.cnn_fg_referer == "https://edition.cnn.com/"
    assert s.cnn_fg_cache_dir == Path("results/cnn_fg")
    assert s.http_accept == "application/json, text/plain, */*"
    assert s.request_timeout_sec == 10
    assert s.results_dir == Path("results")


def test_app_settings_env_override_via_ssk_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``SSK_<FIELD>`` env vars override the default at construction time."""
    monkeypatch.setenv("SSK_REQUEST_TIMEOUT_SEC", "30")
    monkeypatch.setenv("SSK_RESULTS_DIR", "/tmp/results-override")  # noqa: S108

    s = AppSettings()

    assert s.request_timeout_sec == 30
    assert s.results_dir == Path("/tmp/results-override")  # noqa: S108
