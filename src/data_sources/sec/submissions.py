"""EDGAR submissions API — last-filed dates per form type.

EDGAR's per-company submissions index is a single JSON document
returned by ``data.sec.gov/submissions/CIK<10-digit>.json``. The
filing history is stored as parallel arrays under ``filings.recent``:

.. code-block:: json

    {
      "filings": {
        "recent": {
          "form":         ["10-K", "10-Q", "8-K", ...],
          "filingDate":   ["2024-11-01", "2024-08-02", "2024-07-15", ...],
          ...
        },
        "files": []
      }
    }

The two arrays are zipped by position — ``form[i]`` was filed on
``filingDate[i]``. We extract the **most-recent** date per US form
type (10-K, 10-Q, 8-K) and expose them as
:class:`LastFiledSnapshot` for attachment to
:class:`src.fundamentals.FundamentalsSnapshot` via
``model_copy(update=...)``.

Public API:

- :class:`LastFiledSnapshot` — frozen pydantic model.
- :func:`fetch_last_filed(cik)` — orchestrator: fetch + parse.
- :func:`_extract_last_filed(payload)` — pure parser (stubbed via
  :func:`monkeypatch.setattr` in tests).

Foreign filers (Form 20-F instead of 10-K) leave all three US-form
fields ``None`` — by design, not an error.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date

from pydantic import BaseModel, ConfigDict
from src.config import settings
from src.data_sources.sec.cik_map import resolve_cik
from src.utils.http_ua import pick_user_agent, require_https

logger = logging.getLogger(__name__)


class LastFiledSnapshot(BaseModel):
    """Most-recent filing dates per US form type from EDGAR submissions."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    last_10k_date: date | None = None
    last_10q_date: date | None = None
    last_8k_date: date | None = None


def _extract_last_filed(payload: dict) -> LastFiledSnapshot:
    """Parse submissions JSON into a :class:`LastFiledSnapshot`."""
    recent = payload["filings"]["recent"]
    forms: list[str] = recent["form"]
    dates: list[str] = recent["filingDate"]

    def first(form_name: str) -> date | None:
        return next(
            (date.fromisoformat(d) for f, d in zip(forms, dates, strict=True) if f == form_name),
            None,
        )

    return LastFiledSnapshot(
        last_10k_date=first("10-K"),
        last_10q_date=first("10-Q"),
        last_8k_date=first("8-K"),
    )


def fetch_last_filed(cik: str) -> LastFiledSnapshot:
    """Fetch submissions for ``cik`` and extract last-filed dates."""
    url = settings.edgar_submissions_url_template.format(cik=cik.zfill(10))
    # S310 / B310: URL is constructed from an HTTPS template plus a zero-
    # padded CIK string; the explicit scheme check below is defense-in-
    # depth for any future refactor that might let external input flow in.
    request = urllib.request.Request(  # noqa: S310  # nosec B310
        url,
        headers={
            "User-Agent": pick_user_agent(),
            "Accept": settings.http_accept,
            "Referer": settings.sec_referer,
        },
    )
    require_https(request.full_url)
    with urllib.request.urlopen(  # noqa: S310  # nosec B310
        request, timeout=settings.request_timeout_sec
    ) as response:
        payload = json.loads(response.read())
    return _extract_last_filed(payload)


def enrich_snapshot_sec(symbol: str) -> dict:
    """Return ``FundamentalsSnapshot`` SEC enrichment fields for ``symbol``.

    Resolves the Yahoo symbol to a CIK; if no CIK (FX, crypto, futures,
    or non-SEC equity), returns ``{}`` and does NOT call EDGAR.

    Network / HTTP errors from the EDGAR fetch are logged as warnings
    and degrade to ``{}`` so one ticker's failure doesn't kill the
    whole universe run (wrap-degrade per ``docs/architecture.md``).
    """
    cik = resolve_cik(symbol)
    if not cik:
        return {}
    try:
        snap = fetch_last_filed(cik)
    except urllib.error.URLError as exc:
        logger.warning("SEC submissions fetch failed for %s (CIK %s): %s", symbol, cik, exc)
        return {}
    return {
        "sec_last_10k_date": snap.last_10k_date,
        "sec_last_10q_date": snap.last_10q_date,
        "sec_last_8k_date": snap.last_8k_date,
    }
