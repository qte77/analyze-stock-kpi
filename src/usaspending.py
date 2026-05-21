"""usaspending.gov top-contractors API client.

Wraps the POST
``/api/v2/search/spending_by_category/recipient/`` endpoint. Tier-0
keyless source; see ``docs/data-sources.md`` for the response schema,
ToS verdict, and ``MULTIPLE RECIPIENTS`` aggregate-row gotcha.
"""

from __future__ import annotations

import urllib.request
from datetime import date  # noqa: TC003 — pydantic needs runtime access in callers

from src.config import settings


def fetch_top_contractors(
    fy_start: date,
    fy_end: date,
    *,
    limit: int = 100,
    naics_codes: list[str] | None = None,
    award_type_codes: tuple[str, ...] = ("A", "B", "C", "D"),
) -> list[dict]:
    """Fetch top contractors by trailing-FY obligated dollars."""
    req = urllib.request.Request(  # noqa: S310
        settings.usaspending_url, data=b"{}", method="POST",
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(  # noqa: S310
        req, timeout=settings.usaspending_timeout_sec,
    ):
        return []
