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

from datetime import date

from pydantic import BaseModel, ConfigDict

from src.sec.cik_map import resolve_cik


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
    raise NotImplementedError


def enrich_snapshot_sec(symbol: str) -> dict:
    """Return ``FundamentalsSnapshot`` SEC enrichment fields for ``symbol``.

    Resolves the Yahoo symbol to a CIK; if no CIK (FX, crypto, futures,
    or non-SEC equity), returns ``{}`` and does NOT call EDGAR. Otherwise
    returns the three optional date fields ready for
    ``model_copy(update=...)``.
    """
    cik = resolve_cik(symbol)
    if not cik:
        return {}
    snap = fetch_last_filed(cik)
    return {
        "sec_last_10k_date": snap.last_10k_date,
        "sec_last_10q_date": snap.last_10q_date,
        "sec_last_8k_date": snap.last_8k_date,
    }
