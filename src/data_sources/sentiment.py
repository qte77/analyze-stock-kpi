"""CNN Fear & Greed Index sentiment via stdlib HTTP.

Public API:
    - :func:`fetch_fear_greed` returns the headline :class:`FearGreedSnapshot`
      (used by the ``make run`` banner).
    - ``python -m src.sentiment`` fetches the full payload and merges the
      headline + ~1y historical points + per-day subindicator readings into
      per-year files at ``results/cnn_fg/YYYY.json`` — sorted-by-date JSON
      arrays. Today's entry is always overwritten with the live headline
      (which carries ``previous_*`` deltas + the precise 0-100 subindicator
      scores CNN only ships for today); older dates are gap-filled and only
      updated if a fresher CNN timestamp arrives.

CNN's WAF requires a browser-shape request — see ``USER_AGENT`` / ``ACCEPT``
/ ``REFERER`` constants. No external dependencies; stdlib ``urllib.request``
only. See ``docs/cnn-fg-api.md`` for the observed CNN payload schema.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict
from src.config import settings
from src.utils.http_ua import STABLE_USER_AGENT, require_https

if TYPE_CHECKING:
    from pathlib import Path

# CNN's WAF rejects unidentified clients with HTTP 418. The headers
# (STABLE_USER_AGENT / http_accept / cnn_fg_referer) mirror
# what edition.cnn.com itself sends when it XHRs the dataviz API. All
# three are required when the egress IP is a datacenter range (e.g.
# GitHub Actions runners); from residential IPs the UA alone usually
# suffices.

# CNN's 10 subindicator blocks. Each ships {timestamp, score, rating, data}
# where `data[]` is ~1y of {x: ms_epoch, y: raw_value, rating} per day.
# The precise 0-100 `score` is only at the top level (today only); historical
# `data[]` points carry `rating` + raw `y` value but no per-day score.
SUBINDICATOR_KEYS: tuple[str, ...] = (
    "market_momentum_sp500",
    "market_momentum_sp125",
    "stock_price_strength",
    "stock_price_breadth",
    "put_call_options",
    "market_volatility_vix",
    "market_volatility_vix_50",
    "junk_bond_demand",
    "safe_haven_demand",
)

logger = logging.getLogger(__name__)


class SubindicatorReading(BaseModel):
    """One subindicator's reading for one date.

    ``score`` (0-100) is only ever set for the **today** row — CNN ships
    per-day historical scores nowhere; only the current top-level value.
    ``rating`` and ``raw_value`` are available for both today and ~1y of
    history via the subindicator's ``data[]`` array.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    score: float | None = None
    rating: str
    raw_value: float | None = None


class FearGreedSnapshot(BaseModel):
    """One CNN Fear & Greed reading + optional subindicator details.

    Used for both the live headline (with ``previous_*`` populated, plus
    per-subindicator scores) and historical points (``previous_*`` and
    per-day subindicator scores are ``None`` because CNN's historical
    blocks don't carry them — only today's top-level fields do).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    score: float
    rating: str
    timestamp: datetime
    previous_close: float | None = None
    previous_1_week: float | None = None
    previous_1_month: float | None = None
    previous_1_year: float | None = None
    subindicators: dict[str, SubindicatorReading] | None = None


def _fetch_payload() -> dict[str, Any]:
    # S310 / B310: settings.cnn_fg_url is an HTTPS string; the explicit
    # scheme check below is the defense-in-depth boundary if a future
    # refactor ever lets external input flow into it. ruff and Bandit
    # (via CodeFactor) each need their own suppression syntax.
    request = urllib.request.Request(  # noqa: S310  # nosec B310
        settings.cnn_fg_url,
        headers={
            "User-Agent": STABLE_USER_AGENT,
            "Accept": settings.http_accept,
            "Referer": settings.cnn_fg_referer,
        },
    )
    require_https(request.full_url)
    with urllib.request.urlopen(  # noqa: S310  # nosec B310
        request, timeout=settings.request_timeout_sec
    ) as response:
        return json.loads(response.read())


def fetch_fear_greed() -> FearGreedSnapshot:
    """Fetch the current CNN Fear & Greed headline reading (no subindicators).

    Used by the ``make run`` banner — keep it cheap, no extra parsing.

    Raises ``urllib.error.URLError`` on transport failure and
    ``pydantic.ValidationError`` on schema mismatch — callers decide whether
    to swallow or surface.
    """
    return FearGreedSnapshot.model_validate(_fetch_payload()["fear_and_greed"])


def _index_subindicator_data_by_date(
    payload: dict[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    """For each known subindicator, build ``{date_str: latest_data_point}``.

    Same-day dedup: keep the entry with the largest ``x`` (latest timestamp).
    """
    indexed: dict[str, dict[str, dict[str, Any]]] = {}
    for key in SUBINDICATOR_KEYS:
        sub = payload.get(key)
        if not sub:
            continue
        by_date: dict[str, dict[str, Any]] = {}
        for point in sub.get("data") or []:
            ts_ms = int(point["x"])
            date_key = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%Y-%m-%d")
            stored = by_date.get(date_key)
            if stored is not None and ts_ms <= stored["_ts_ms"]:
                continue
            by_date[date_key] = {**point, "_ts_ms": ts_ms}
        indexed[key] = by_date
    return indexed


def _build_today_subindicators(
    payload: dict[str, Any],
) -> dict[str, SubindicatorReading]:
    """Build today's subindicator bundle.

    Precise score + rating come from the top-level subindicator block;
    ``raw_value`` from the latest data point.
    """
    out: dict[str, SubindicatorReading] = {}
    for key in SUBINDICATOR_KEYS:
        sub = payload.get(key)
        if not sub:
            continue
        data = sub.get("data") or []
        raw_value = max(data, key=lambda p: p["x"])["y"] if data else None
        out[key] = SubindicatorReading(
            score=sub.get("score"),
            rating=sub["rating"],
            raw_value=raw_value,
        )
    return out


def _build_historical_subindicators(
    sub_index: dict[str, dict[str, dict[str, Any]]], date_key: str
) -> dict[str, SubindicatorReading] | None:
    """For a historical date, pull (rating, raw_value) per subindicator.

    Returns ``None`` if no subindicator has data for that date.
    """
    out: dict[str, SubindicatorReading] = {}
    for key, by_date in sub_index.items():
        point = by_date.get(date_key)
        if point is None:
            continue
        out[key] = SubindicatorReading(
            score=None, rating=point["rating"], raw_value=point["y"]
        )
    return out or None


def parse_historical(payload: dict[str, Any]) -> dict[str, FearGreedSnapshot]:
    """Extract historical headline points + per-date subindicator readings.

    CNN ships multiple intraday entries per day; we keep the latest timestamp
    for each calendar date. Historical subindicator score is always ``None``
    (CNN doesn't carry it in ``data[]``); rating + raw_value are populated.
    """
    historical = payload.get("fear_and_greed_historical", {}).get("data", [])
    sub_index = _index_subindicator_data_by_date(payload)
    by_date: dict[str, tuple[int, FearGreedSnapshot]] = {}
    for point in historical:
        ts_ms = int(point["x"])
        moment = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        date_key = moment.strftime("%Y-%m-%d")
        if date_key in by_date and ts_ms <= by_date[date_key][0]:
            continue
        by_date[date_key] = (
            ts_ms,
            FearGreedSnapshot(
                score=point["y"],
                rating=point["rating"],
                timestamp=moment,
                subindicators=_build_historical_subindicators(sub_index, date_key),
            ),
        )
    return {date: snap for date, (_, snap) in by_date.items()}


def _year_path(year: int, *, root: Path = settings.cnn_fg_cache_dir) -> Path:
    return root / f"{year}.json"


def _load_year(
    year: int, *, root: Path = settings.cnn_fg_cache_dir
) -> dict[str, FearGreedSnapshot]:
    """Load the per-year file as a date-keyed dict, or empty if missing."""
    path = _year_path(year, root=root)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {item["timestamp"][:10]: FearGreedSnapshot.model_validate(item) for item in raw}


def _write_year(
    year: int, by_date: dict[str, FearGreedSnapshot], *, root: Path = settings.cnn_fg_cache_dir
) -> Path:
    """Write a year's snapshots as a date-sorted JSON array.

    ``exclude_none=True`` keeps the per-row payload tight: historical rows
    (which have ``previous_*`` and per-day subindicator scores as ``None``)
    omit those keys entirely. Loading round-trips because the model fills
    missing optional fields with their declared defaults.
    """
    root.mkdir(parents=True, exist_ok=True)
    path = _year_path(year, root=root)
    payload = [
        by_date[k].model_dump(mode="json", exclude_none=True) for k in sorted(by_date)
    ]
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def _upsert(
    by_date: dict[str, FearGreedSnapshot], snap: FearGreedSnapshot, *, force: bool
) -> bool:
    """Insert/replace a snapshot keyed by its UTC date.

    ``force=True`` always wins (used for the live headline). Otherwise:

    - newer CNN timestamp → replace (CNN updated this day intraday);
    - same timestamp but different content → replace (schema upgrade — e.g.
      a row written before subindicator capture needs to gain those fields);
    - older or identical → no-op.
    """
    date_key = snap.timestamp.astimezone(UTC).strftime("%Y-%m-%d")
    existing = by_date.get(date_key)
    if force or existing is None or snap.timestamp > existing.timestamp:
        by_date[date_key] = snap
        return True
    if snap.timestamp == existing.timestamp and snap != existing:
        by_date[date_key] = snap
        return True
    return False


def merge_payload_into_years(
    payload: dict[str, Any], *, root: Path = settings.cnn_fg_cache_dir
) -> dict[int, dict[str, FearGreedSnapshot]]:
    """Apply a CNN payload onto the on-disk per-year history, in memory only.

    Returns the resulting ``{year: {date: snap}}`` mapping. The headline
    upsert is forced (today's reading always wins, including its
    ``previous_*`` fields and precise per-subindicator scores). Historical
    entries fill gaps with rating + raw_value per subindicator (no scores)
    and refresh same-day duplicates that CNN has since updated.
    """
    headline_data = payload["fear_and_greed"]
    headline = FearGreedSnapshot.model_validate(
        {**headline_data, "subindicators": _build_today_subindicators(payload)}
    )
    historical = parse_historical(payload)
    today_year = headline.timestamp.astimezone(UTC).year
    today_key = headline.timestamp.astimezone(UTC).strftime("%Y-%m-%d")

    by_year: dict[int, dict[str, FearGreedSnapshot]] = {}

    def _ensure(year: int) -> dict[str, FearGreedSnapshot]:
        if year not in by_year:
            by_year[year] = _load_year(year, root=root)
        return by_year[year]

    _upsert(_ensure(today_year), headline, force=True)
    for date_key, snap in historical.items():
        if date_key == today_key:
            continue
        _upsert(_ensure(snap.timestamp.astimezone(UTC).year), snap, force=False)
    return by_year


def main() -> None:
    """Cron entrypoint: fetch CNN F&G, merge into per-year files."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    by_year = merge_payload_into_years(_fetch_payload())
    for year, by_date in by_year.items():
        path = _write_year(year, by_date)
        logger.info("Wrote %s with %d entries", path, len(by_date))


if __name__ == "__main__":
    main()
