"""Tests for :mod:`src.usaspending` — POST top-contractors API client."""

from __future__ import annotations

import json
import urllib.request
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config import settings
from src.usaspending import fetch_top_contractors

if TYPE_CHECKING:
    import pytest


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
