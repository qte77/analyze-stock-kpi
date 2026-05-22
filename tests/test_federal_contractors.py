"""Tests for :mod:`src.federal_contractors`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.federal_contractors import _match_to_edgar, _resolve_candidates
from src.sec.cik_map import CikRecord
from src.usaspending import RecipientRecord

if TYPE_CHECKING:
    import pytest


def _records(*pairs: tuple[str, str, str]) -> dict[str, CikRecord]:
    """Build an EDGAR-shape records dict from (ticker, title, cik) triples."""
    return {
        ticker.upper(): CikRecord(
            cik=cik.zfill(10), ticker=ticker, title=title, exchange="NYSE",
        )
        for ticker, title, cik in pairs
    }


def _recipient(rank: int, name: str) -> RecipientRecord:
    """RecipientRecord with plausible stub fields for orchestrator tests."""
    return RecipientRecord(
        name=name,
        recipient_id=f"stub-id-{rank}",
        code=None,
        uei=None,
        amount=1_000_000.0 * (100 - rank),
        total_outlays=None,
        rank=rank,
    )


def test_fuzzy_match_lockheed_recipient_to_lmt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SAM-style 'LOCKHEED MARTIN CORPORATION' resolves to ticker LMT >= 0.85."""
    monkeypatch.setattr(
        "src.federal_contractors._load_records",
        lambda: _records(
            ("LMT", "Lockheed Martin Corp", "936468"),
            ("MSFT", "Microsoft Corp", "789019"),
        ),
    )

    ticker, score = _match_to_edgar("LOCKHEED MARTIN CORPORATION")

    assert ticker == "LMT"
    assert score is not None
    assert score >= 0.85


def test_fuzzy_match_unrelated_recipient_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A name with no EDGAR match returns (None, None)."""
    monkeypatch.setattr(
        "src.federal_contractors._load_records",
        lambda: _records(
            ("MSFT", "Microsoft Corp", "789019"),
            ("AAPL", "Apple Inc.", "320193"),
        ),
    )

    ticker, score = _match_to_edgar("WIDGET FOUNDRY INTERNATIONAL LLC")

    assert ticker is None
    assert score is None


def test_resolve_candidates_dedupes_subsidiary_to_parent_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple recipient names collapsing to one EDGAR ticker yield one entry."""
    monkeypatch.setattr(
        "src.federal_contractors._load_records",
        lambda: _records(
            ("LMT", "Lockheed Martin Corp", "936468"),
            ("MSFT", "Microsoft Corp", "789019"),
        ),
    )

    candidates = _resolve_candidates([
        _recipient(1, "LOCKHEED MARTIN CORPORATION"),
        _recipient(2, "LOCKHEED MARTIN AERONAUTICS COMPANY"),
        _recipient(3, "MICROSOFT CORPORATION"),
    ])

    assert candidates == ["LMT", "MSFT"]


def test_resolve_candidates_drops_unmatched_recipients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recipients with no EDGAR match above threshold are skipped silently."""
    monkeypatch.setattr(
        "src.federal_contractors._load_records",
        lambda: _records(("AAPL", "Apple Inc.", "320193")),
    )

    candidates = _resolve_candidates([
        _recipient(1, "WIDGET FOUNDRY INTERNATIONAL LLC"),
        _recipient(2, "APPLE INC"),
    ])

    assert candidates == ["AAPL"]
