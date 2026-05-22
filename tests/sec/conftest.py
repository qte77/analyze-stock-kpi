"""Shared fixtures for SEC integration tests.

Provides:

- ``edgar_tickers_fixture``: loads the committed
  ``company_tickers_exchange.json`` subset used by ``cik_map`` tests.
- ``_reset_cik_map_cache`` (autouse): clears the module-level cache in
  :mod:`src.sec.cik_map` before and after every test in this package
  so tests don't bleed state into each other.
- ``_set_sec_user_agent`` (autouse): provides a deterministic sentinel
  ``SSK_SEC_USER_AGENT`` so the fail-loud guard in :func:`cik_map._fetch_json`
  and :func:`submissions.fetch_last_filed` is satisfied during tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from src.config import AppSettings
from src.data_sources.sec import cik_map, submissions

if TYPE_CHECKING:
    from collections.abc import Iterator

_FIXTURES_DIR = Path(__file__).parent / "fixtures"

_TEST_SEC_USER_AGENT = "pytest-suite ua@example.invalid"


@pytest.fixture
def edgar_tickers_fixture() -> dict:
    """Return the committed EDGAR ``company_tickers_exchange.json`` subset."""
    path = _FIXTURES_DIR / "company_tickers_exchange.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _reset_cik_map_cache() -> Iterator[None]:
    """Reset the cik_map module-level cache around every test."""
    cik_map._records_cache = None
    yield
    cik_map._records_cache = None


@pytest.fixture(autouse=True)
def _isolate_edgar_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point ``cik_map._CACHE_PATH`` at ``tmp_path`` so tests never touch repo."""
    monkeypatch.setattr(cik_map, "_CACHE_PATH", tmp_path / "edgar.json", raising=False)


@pytest.fixture(autouse=True)
def _set_sec_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a sentinel ``SSK_SEC_USER_AGENT`` so the fail-loud guard is satisfied.

    ``AppSettings`` reads env on construction, so we both set the env var and
    swap the module-level ``settings`` reference in both SEC fetchers to a
    fresh instance that reflects it. Sentinel value never identifies the suite.
    """
    monkeypatch.setenv("SSK_SEC_USER_AGENT", _TEST_SEC_USER_AGENT)
    fresh = AppSettings()
    monkeypatch.setattr(cik_map, "settings", fresh, raising=False)
    monkeypatch.setattr(submissions, "settings", fresh, raising=False)
