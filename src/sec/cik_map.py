"""CIK <-> ticker resolution via EDGAR's ``company_tickers_exchange.json``.

**CIK** = Central Index Key, the 10-digit numeric identifier SEC
assigns to every entity that files with EDGAR. CIKs are stable
across name changes, mergers, and ticker swaps, which makes them the
canonical join key for all other EDGAR endpoints
(``data.sec.gov/submissions/CIK<10>.json``, XBRL company facts, etc.).

EDGAR publishes a single rolling JSON file mapping every SEC-registered
equity to its CIK plus listing exchange. The file is keyless. SEC asks
clients to send a ``User-Agent`` header so they can rate-limit per
caller (see https://www.sec.gov/os/accessing-edgar-data); we send a
browser-shape UA from :mod:`src.http_ua`.

Public API:

- :class:`CikRecord` — frozen pydantic model for one EDGAR row.
- :func:`lookup_record` — full record lookup by ticker (case-insensitive).
- :func:`resolve_cik` — convenience wrapper that returns only the
  10-digit zero-padded CIK string (or ``None`` for non-SEC-registered
  Yahoo symbols like FX, crypto, futures).

The fetched JSON is cached at module level for the lifetime of the
process. Tests reset the cache via the ``_reset_cik_map_cache``
autouse fixture in :mod:`tests.sec.conftest`.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from email.utils import formatdate, parsedate_to_datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from src.config import settings
from src.http_ua import pick_user_agent

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pathlib import Path

_CACHE_PATH: Path = settings.edgar_cache_dir / "company_tickers_exchange.json"
"""Persistent disk cache for the EDGAR ticker registry.

mtime is set to the server's ``Last-Modified`` header (not "when we
wrote it") so we can echo it back as ``If-Modified-Since`` on the
next call. Tests monkeypatch this via the ``_isolate_edgar_cache``
autouse fixture in :mod:`tests.sec.conftest`.
"""


class CikRecord(BaseModel):
    """Single EDGAR ticker registry entry."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    cik: str
    """10-digit zero-padded CIK (e.g., ``"0000320193"`` for AAPL)."""

    ticker: str
    """Exchange ticker symbol (e.g., ``"AAPL"``)."""

    title: str
    """Issuer name as registered with EDGAR (e.g., ``"Apple Inc."``)."""

    exchange: str | None = None
    """Listing exchange (``"Nasdaq"`` / ``"NYSE"`` / ``"OTC"`` / etc.)."""


def _http_error_cache_fallback(exc: urllib.error.HTTPError) -> dict | None:
    """Return cached body when ``exc.code`` warrants stale-cache fallback."""
    if not _CACHE_PATH.is_file():
        return None
    if exc.code == 304:
        return json.loads(_CACHE_PATH.read_bytes())
    if exc.code == 403:
        logger.warning(
            "EDGAR fetch returned 403 Forbidden (anti-bot likely); "
            "reusing stale cache at %s",
            _CACHE_PATH,
        )
        return json.loads(_CACHE_PATH.read_bytes())
    return None


def _fetch_json() -> dict:
    """Fetch company_tickers_exchange.json from EDGAR.

    Conditional GET: when ``_CACHE_PATH`` exists, send
    ``If-Modified-Since`` (cache mtime → HTTP-date) and treat ``304 Not
    Modified`` as a hit by returning the cached body.

    Stubbed in tests via ``monkeypatch.setattr(cik_map, "_fetch_json", ...)``.
    """
    headers = {
        "User-Agent": pick_user_agent(),
        "Accept": settings.http_accept,
        "Referer": settings.sec_referer,
    }
    if _CACHE_PATH.is_file():
        headers["If-Modified-Since"] = formatdate(
            _CACHE_PATH.stat().st_mtime, usegmt=True
        )
    # S310 / B310: settings.edgar_tickers_url is an HTTPS string; the explicit
    # scheme check below is the defense-in-depth boundary if a future refactor
    # ever lets external input flow into it.
    request = urllib.request.Request(  # noqa: S310  # nosec B310
        settings.edgar_tickers_url,
        headers=headers,
    )
    if not request.full_url.startswith("https://"):
        raise ValueError(f"Refusing non-HTTPS URL: {request.full_url!r}")
    try:
        with urllib.request.urlopen(  # noqa: S310  # nosec B310
            request, timeout=settings.request_timeout_sec
        ) as response:
            body = response.read()
            last_modified = getattr(response, "headers", {}).get("Last-Modified")
    except urllib.error.HTTPError as exc:
        cached = _http_error_cache_fallback(exc)
        if cached is not None:
            return cached
        raise
    except urllib.error.URLError as exc:
        if _CACHE_PATH.is_file():
            logger.warning(
                "EDGAR fetch failed (%s); reusing stale cache at %s",
                exc, _CACHE_PATH,
            )
            return json.loads(_CACHE_PATH.read_bytes())
        raise
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_bytes(body)
    if last_modified:
        ts = parsedate_to_datetime(last_modified).timestamp()
        os.utime(_CACHE_PATH, (ts, ts))
    return json.loads(body)


_records_cache: dict[str, CikRecord] | None = None


def _load_records() -> dict[str, CikRecord]:
    """Parse the EDGAR JSON into a dict keyed by upper-case ticker."""
    global _records_cache
    if _records_cache is None:
        data = _fetch_json()
        records: dict[str, CikRecord] = {}
        for row in data["data"]:
            cik_int, name, ticker, exchange = row
            records[ticker.upper()] = CikRecord(
                cik=str(cik_int).zfill(10),
                ticker=ticker,
                title=name,
                exchange=exchange,
            )
        _records_cache = records
    return _records_cache


def lookup_record(ticker: str) -> CikRecord | None:
    """Resolve ``ticker`` to a full :class:`CikRecord`, or ``None``."""
    return _load_records().get(ticker.upper())


def resolve_cik(ticker: str) -> str | None:
    """Resolve ``ticker`` to a 10-digit zero-padded CIK, or ``None``."""
    record = lookup_record(ticker)
    return record.cik if record else None
