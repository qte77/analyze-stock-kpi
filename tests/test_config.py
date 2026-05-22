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


def test_app_settings_item3_field_defaults() -> None:
    """Federal-contractors universe fields default to in-repo `results/` paths."""
    s = AppSettings()
    assert s.federal_contractors_dir == Path("results/federal_contractors")
    assert s.usaspending_url == (
        "https://api.usaspending.gov/api/v2/search/spending_by_category/recipient/"
    )
    assert s.usaspending_timeout_sec == 30


def test_app_settings_sec_referer_default() -> None:
    """``sec_referer`` defaults to the SEC root for browser-shape blending."""
    assert AppSettings().sec_referer == "https://www.sec.gov/"


def test_app_settings_user_agents_pool_non_empty_browser_shape() -> None:
    """``user_agents`` is a non-empty pool of browser-shape UA strings."""
    s = AppSettings()
    assert isinstance(s.user_agents, tuple)
    assert len(s.user_agents) >= 3
    # All entries must look like real browser UAs (start with Mozilla/...).
    assert all(ua.startswith("Mozilla/") for ua in s.user_agents)


def test_app_settings_item3_field_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``SSK_<FIELD>`` env vars override Item 3 fields at construction time."""
    monkeypatch.setenv("SSK_FEDERAL_CONTRACTORS_DIR", "/tmp/fc-override")  # noqa: S108  # nosec B108
    monkeypatch.setenv("SSK_USASPENDING_TIMEOUT_SEC", "60")

    s = AppSettings()

    assert s.federal_contractors_dir == Path("/tmp/fc-override")  # noqa: S108  # nosec B108
    assert s.usaspending_timeout_sec == 60
