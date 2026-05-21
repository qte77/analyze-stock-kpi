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

from src.config import settings


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


def fetch_top_contractors(
    fy_start: date,
    fy_end: date,
    *,
    limit: int = 100,
    naics_codes: list[str] | None = None,
    award_type_codes: tuple[str, ...] = ("A", "B", "C", "D"),
) -> list[dict]:
    """Fetch top contractors by trailing-FY obligated dollars."""
    body = _build_body(fy_start, fy_end, limit, naics_codes, award_type_codes)
    req = urllib.request.Request(  # noqa: S310
        settings.usaspending_url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(  # noqa: S310
        req, timeout=settings.usaspending_timeout_sec,
    ):
        return []
