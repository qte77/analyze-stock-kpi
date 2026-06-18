"""Centralised runtime config: URLs, paths, HTTP shape, timeouts.

Single `AppSettings(BaseSettings)` carries every value that previously
lived as a module-level constant in `src/sec/`, `src/sentiment.py`,
and `src/__main__.py`. Env-var override via the ``SSK_`` prefix
(e.g. ``SSK_REQUEST_TIMEOUT_SEC=30``). Defaults reproduce the pre-
refactor literals.

Domain / algorithm constants (`_PROFIT_MIN`, `_TRADING_DAYS`,
`_STALE_10Q_DAYS`, etc.) intentionally stay co-located with the
algorithm — they are not user-overridable runtime config.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Runtime config for every I/O boundary in the package."""

    model_config = SettingsConfigDict(env_prefix="SSK_", frozen=True, env_ignore_empty=True)

    edgar_tickers_url: str = "https://www.sec.gov/files/company_tickers_exchange.json"
    edgar_submissions_url_template: str = "https://data.sec.gov/submissions/CIK{cik}.json"
    edgar_cache_dir: Path = Path("results/edgar")
    sec_referer: str = "https://www.sec.gov/"
    sec_user_agent: str = "opensource-research-client contact@example.com"
    """Caller-identifying ``User-Agent`` for SEC EDGAR HTTPS requests.

    Identity-shape per SEC's published access policy
    (https://www.sec.gov/os/accessing-edgar-data); the default uses the
    RFC 2606 documentation domain ``example.com`` so the value is
    self-evidently a placeholder. Operators override via
    ``SSK_SEC_USER_AGENT`` env (CI: repository variable
    ``vars.SEC_USER_AGENT``) with their actual contact. No PII and no
    repo fingerprint committed in source. See ADR-0006 amendment for
    rationale.
    """
    cnn_fg_url: str = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    cnn_fg_referer: str = "https://edition.cnn.com/"
    cnn_fg_cache_dir: Path = Path("results/series/cnn_fg")
    yield_curve_cache_dir: Path = Path("results/series/yield_curve")
    demo_dir: Path = Path("results/demo")
    audit_dir: Path = Path("results/audit")
    user_agents: tuple[str, ...] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.10 Safari/605.1.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36",
    )
    http_accept: str = "application/json, text/plain, */*"
    request_timeout_sec: int = 10
    results_dir: Path = Path("results")
    fundamentals_dir: Path = Path("results/fundamentals")
    usaspending_url: str = (
        "https://api.usaspending.gov/api/v2/search/spending_by_category/recipient/"
    )
    usaspending_timeout_sec: int = 30
    federal_contractors_dir: Path = Path("results/federal_contractors")


settings = AppSettings()
