"""usaspending.gov top-contractors API client.

Wraps the POST
``/api/v2/search/spending_by_category/recipient/`` endpoint. Tier-0
keyless source; see ``docs/data-sources.md`` for the response schema,
ToS verdict, and ``MULTIPLE RECIPIENTS`` aggregate-row gotcha.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date  # noqa: TC003 — pydantic needs runtime access in callers

from pydantic import BaseModel, ConfigDict

from analyze_stock_kpi.config import settings
from analyze_stock_kpi.utils.http_ua import require_https


class RecipientRecord(BaseModel):
    """One result entry from usaspending ``spending_by_category/recipient``.

    Per the upstream contract (verified 2026-05-21), ``code`` is the
    legacy DUNS, ``uei`` is the modern SAM identifier, and both may be
    ``None``. ``recipient_id`` is the only reliable dedupe key.
    ``rank`` is derived from post-aggregate-filter list position
    (1-based) — the API does not return a rank field.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str
    recipient_id: str | None = None
    code: str | None = None
    uei: str | None = None
    amount: float
    total_outlays: float | None = None
    rank: int


def _build_body(
    fy_start: date,
    fy_end: date,
    limit: int,
    naics_codes: list[str] | None,
    award_type_codes: tuple[str, ...],
) -> dict:
    """Construct the POST body per the recipient.md contract."""
    filters: dict = {
        "award_type_codes": list(award_type_codes),
        "time_period": [
            {"start_date": fy_start.isoformat(), "end_date": fy_end.isoformat()},
        ],
    }
    if naics_codes is not None:
        filters["naics_codes"] = {"require": list(naics_codes)}
    return {
        "category": "recipient",
        "filters": filters,
        "limit": limit,
        "page": 1,
    }


def _parse_results(raw_results: list[dict]) -> list[RecipientRecord]:
    """Drop ``MULTIPLE RECIPIENTS`` aggregate rows; rank from list position."""
    records: list[RecipientRecord] = []
    for raw in raw_results:
        if raw.get("recipient_id") is None:
            continue
        rank = len(records) + 1
        records.append(RecipientRecord(**raw, rank=rank))
    return records


def fetch_top_contractors(
    fy_start: date,
    fy_end: date,
    *,
    limit: int = 100,
    naics_codes: list[str] | None = None,
    award_type_codes: tuple[str, ...] = ("A", "B", "C", "D"),
) -> list[RecipientRecord]:
    """Fetch top contractors by trailing-FY obligated dollars."""
    body = _build_body(fy_start, fy_end, limit, naics_codes, award_type_codes)
    # S310 / B310: settings.usaspending_url is an HTTPS string; the explicit
    # scheme check below is the defense-in-depth boundary if a future refactor
    # ever lets external input flow into it.
    req = urllib.request.Request(  # noqa: S310  # nosec B310
        settings.usaspending_url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
    )
    require_https(req.full_url)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(  # noqa: S310  # nosec B310
        req,
        timeout=settings.usaspending_timeout_sec,
    ) as resp:
        payload = json.loads(resp.read())
    return _parse_results(payload.get("results", []))
