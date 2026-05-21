"""CIK <-> ticker resolution via EDGAR's ``company_tickers_exchange.json``.

EDGAR publishes a single rolling JSON file that maps every SEC-registered
equity to its 10-digit CIK plus exchange. The file is keyless but the SEC
requires a ``User-Agent`` header identifying the caller; see
https://www.sec.gov/os/accessing-edgar-data.

Public API:

- :class:`CikRecord` — frozen pydantic model for one EDGAR row.
- :func:`lookup_record` — full record lookup by ticker (case-insensitive).
- :func:`resolve_cik` — convenience wrapper that returns only the CIK
  (or ``None`` for non-SEC-registered Yahoo symbols).

The fetched JSON is cached at module level for the lifetime of the
process. Tests reset the cache via the ``_reset_cik_map_cache``
autouse fixture in :mod:`tests.sec.conftest`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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


def _fetch_json() -> dict:
    """Fetch company_tickers_exchange.json from EDGAR.

    Stubbed in tests via ``monkeypatch.setattr(cik_map, "_fetch_json", ...)``.
    """
    raise NotImplementedError


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
                cik=str(cik_int),
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
