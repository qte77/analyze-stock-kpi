"""Tests for :mod:`analyze_stock_kpi.data_sources.usaspending` — POST top-contractors API client."""

from __future__ import annotations

import json
import urllib.request
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from analyze_stock_kpi.config import settings
from analyze_stock_kpi.data_sources.usaspending import RecipientRecord, fetch_top_contractors

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "usaspending_top_recipients.json"


class _FakeResponse(BytesIO):
    """urllib-style response supporting the context-manager protocol."""

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def test_post_body_matches_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_top_contractors POSTs the documented filter + pagination payload."""
    captured: dict[str, Any] = {}
    payload = _FIXTURE_PATH.read_bytes()

    def fake_urlopen(
        req: urllib.request.Request,
        *_args: object,
        **_kwargs: object,
    ) -> _FakeResponse:
        captured["req"] = req
        captured["body"] = req.data
        return _FakeResponse(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    fetch_top_contractors(
        fy_start=date(2024, 10, 1),
        fy_end=date(2025, 9, 30),
        limit=10,
    )

    req = captured["req"]
    assert req.get_method() == "POST"
    assert req.full_url == settings.usaspending_url
    assert req.headers["Content-type"] == "application/json"

    body = json.loads(captured["body"])
    assert body["category"] == "recipient"
    assert body["limit"] == 10
    assert body["page"] == 1
    assert body["filters"]["award_type_codes"] == ["A", "B", "C", "D"]
    assert body["filters"]["time_period"] == [
        {"start_date": "2024-10-01", "end_date": "2025-09-30"}
    ]


def test_response_parses_to_recipient_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parsed results drop the MULTIPLE RECIPIENTS aggregate and rank from 1."""
    payload = _FIXTURE_PATH.read_bytes()
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_a, **_k: _FakeResponse(payload),
    )

    records = fetch_top_contractors(
        fy_start=date(2024, 10, 1),
        fy_end=date(2025, 9, 30),
        limit=10,
    )

    assert len(records) == 9

    lmt = records[0]
    assert isinstance(lmt, RecipientRecord)
    assert lmt.rank == 1
    assert lmt.name == "LOCKHEED MARTIN CORPORATION"
    assert lmt.recipient_id == "005a8812-bab5-2780-533b-b62c33271882-C"
    assert lmt.code == "008016958"
    assert lmt.uei is None
    assert lmt.amount == 17388378311.33
    assert lmt.total_outlays is None

    rtx = records[1]
    assert rtx.rank == 2
    assert rtx.name == "RTX CORPORATION"
    assert rtx.uei == "U7XCNYDDGCM4"

    last = records[-1]
    assert last.rank == 9
    assert last.name == "BOOZ ALLEN HAMILTON INC"


def test_naics_filter_passed_through_as_require_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """naics_codes=[...] serialises to `filters.naics_codes = {"require": [...]}`."""
    captured: dict[str, Any] = {}
    payload = _FIXTURE_PATH.read_bytes()

    def fake_urlopen(
        req: urllib.request.Request,
        *_args: object,
        **_kwargs: object,
    ) -> _FakeResponse:
        captured["body"] = req.data
        return _FakeResponse(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    fetch_top_contractors(
        fy_start=date(2024, 10, 1),
        fy_end=date(2025, 9, 30),
        limit=10,
        naics_codes=["3364", "5417"],
    )

    body = json.loads(captured["body"])
    assert body["filters"]["naics_codes"] == {"require": ["3364", "5417"]}


def test_naics_filter_default_none_omits_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default naics_codes=None omits `filters.naics_codes` entirely."""
    captured: dict[str, Any] = {}
    payload = _FIXTURE_PATH.read_bytes()

    def fake_urlopen(
        req: urllib.request.Request,
        *_args: object,
        **_kwargs: object,
    ) -> _FakeResponse:
        captured["body"] = req.data
        return _FakeResponse(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    fetch_top_contractors(
        fy_start=date(2024, 10, 1),
        fy_end=date(2025, 9, 30),
        limit=10,
    )

    body = json.loads(captured["body"])
    assert "naics_codes" not in body["filters"]


@pytest.mark.network
def test_fetch_top_contractors_live_fy2025() -> None:
    """Live POST against api.usaspending.gov for FY2025 (Oct 2024 - Sep 2025)."""
    records = fetch_top_contractors(
        fy_start=date(2024, 10, 1),
        fy_end=date(2025, 9, 30),
        limit=10,
    )

    assert len(records) >= 5
    assert all(isinstance(r, RecipientRecord) for r in records)
    assert all(r.recipient_id is not None for r in records)
    assert all(r.amount > 0 for r in records)
    assert records[0].rank == 1
    assert all(records[i].rank == i + 1 for i in range(len(records)))
