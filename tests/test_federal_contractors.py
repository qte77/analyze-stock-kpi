"""Tests for :mod:`src.federal_contractors`."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from src.federal_contractors import (
    CURATED_TICKERS,
    AuditRow,
    _ensure_seed,
    _last_completed_fy_window,
    _match_to_edgar,
    _resolve_candidates,
    _smoke_test_yfinance,
    build_universe,
)
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


class _StubTicker:
    """Stand-in for ``yfinance.Ticker`` — controls ``fast_info`` truthiness."""

    _UNRESOLVABLE: frozenset[str] = frozenset({"FAKE", "DELISTED"})

    def __init__(self, symbol: str) -> None:
        self.fast_info = {} if symbol in self._UNRESOLVABLE else {"lastPrice": 1.0}


def test_smoke_test_drops_unresolvable_tickers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tickers whose yfinance fast_info is empty are filtered out."""
    monkeypatch.setattr("src.federal_contractors.yf.Ticker", _StubTicker)

    resolved = _smoke_test_yfinance(["AAPL", "FAKE", "MSFT", "DELISTED", "LMT"])

    assert resolved == ["AAPL", "MSFT", "LMT"]


def test_smoke_test_preserves_input_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolution is order-preserving — sorting is a separate concern (cycle 9)."""
    monkeypatch.setattr("src.federal_contractors.yf.Ticker", _StubTicker)

    resolved = _smoke_test_yfinance(["MSFT", "LMT", "AAPL"])

    assert resolved == ["MSFT", "LMT", "AAPL"]


def test_curated_seed_contains_dod_top_25_count() -> None:
    """The curated seed has the documented 26 entries (DoD Top-25 + ICF)."""
    assert len(CURATED_TICKERS) == 26
    # All entries are (legal_name, ticker) tuples
    assert all(isinstance(t, tuple) and len(t) == 2 for t in CURATED_TICKERS)
    # Key primes must be present
    tickers = {t for _, t in CURATED_TICKERS}
    assert {"LMT", "RTX", "NOC", "GD", "BA"}.issubset(tickers)


def test_ensure_seed_appends_missing_curated_tickers() -> None:
    """_ensure_seed adds any CURATED tickers not already in the input list."""
    result = _ensure_seed(["AAPL", "MSFT"])

    # Input preserved at the front
    assert result[:2] == ["AAPL", "MSFT"]
    # All curated tickers present, no duplicates
    for _, ticker in CURATED_TICKERS:
        assert ticker in result
    assert len(result) == len(set(result))


def test_ensure_seed_does_not_duplicate_already_present_tickers() -> None:
    """When a curated ticker is already in input, it stays at its input position."""
    result = _ensure_seed(["LMT", "AAPL", "RTX"])

    # Original ordering preserved at the front
    assert result[:3] == ["LMT", "AAPL", "RTX"]
    # No duplicates
    assert result.count("LMT") == 1
    assert result.count("RTX") == 1


def test_last_completed_fy_window_mid_fy() -> None:
    """Mid-FY (May) reads the previous Oct 1 -> last Sep 30."""
    assert _last_completed_fy_window(today=date(2026, 5, 22)) == (
        date(2024, 10, 1),
        date(2025, 9, 30),
    )


def test_last_completed_fy_window_just_after_fy_close() -> None:
    """Day after FY end (Oct 1 of a new FY) — last completed is the FY that just ended."""
    assert _last_completed_fy_window(today=date(2025, 10, 1)) == (
        date(2024, 10, 1),
        date(2025, 9, 30),
    )


def test_last_completed_fy_window_last_day_of_fy() -> None:
    """On Sep 30 the FY is just ending; last completed is one earlier."""
    assert _last_completed_fy_window(today=date(2025, 9, 30)) == (
        date(2023, 10, 1),
        date(2024, 9, 30),
    )


def test_build_universe_orchestrator_e2e(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end against stubbed deps — assembles ticker list + AuditRow trail."""
    # Two split-line-items for the same prime contractor — exercises dedup
    # via identical legal names (the realistic case under plain
    # SequenceMatcher; subsidiary-name matching is a future enhancement).
    fake_recipients = [
        _recipient(1, "LOCKHEED MARTIN CORPORATION"),
        _recipient(2, "LOCKHEED MARTIN CORPORATION"),
        _recipient(3, "RTX CORPORATION"),
        _recipient(4, "WIDGET FOUNDRY INTERNATIONAL LLC"),  # no EDGAR match
    ]
    monkeypatch.setattr(
        "src.federal_contractors.fetch_top_contractors",
        lambda *_a, **_kw: fake_recipients,
    )
    monkeypatch.setattr(
        "src.federal_contractors._load_records",
        lambda: _records(
            ("LMT", "Lockheed Martin Corp", "936468"),
            ("RTX", "RTX Corp", "1011059"),
        ),
    )
    monkeypatch.setattr("src.federal_contractors.yf.Ticker", _StubTicker)

    tickers, audit = build_universe(fy=2025, top_n=10)

    # Tickers: sorted ASCII-ascending + deduplicated + curated seed always included
    assert tickers == sorted(set(tickers))
    assert "LMT" in tickers
    assert "RTX" in tickers
    assert "NOC" in tickers  # curated seed entry (not in usaspending fixture)

    # Audit: one row per usaspending recipient, in input order
    assert len(audit) == len(fake_recipients)
    assert all(isinstance(r, AuditRow) for r in audit)
    audit_by_rank = {r.rank: r for r in audit}

    first_lmt = audit_by_rank[1]
    assert first_lmt.candidate_ticker == "LMT"
    assert first_lmt.final_ticker == "LMT"
    assert first_lmt.yfinance_resolves is True

    dupe_lmt = audit_by_rank[2]
    assert dupe_lmt.candidate_ticker == "LMT"
    assert dupe_lmt.final_ticker is None  # deduped — same ticker already claimed
    assert dupe_lmt.note is not None
    assert "dedup" in dupe_lmt.note

    widget_row = audit_by_rank[4]
    assert widget_row.candidate_ticker is None
    assert widget_row.final_ticker is None


def test_audit_row_model_dump_validate_round_trip() -> None:
    """AuditRow serialises + deserialises losslessly via pydantic model_dump."""
    row = AuditRow(
        rank=1,
        recipient_name="LOCKHEED MARTIN CORPORATION",
        uei="ZDG4N3MGLDR9",
        obligated_usd=17_388_378_311.33,
        candidate_ticker="LMT",
        edgar_match_score=0.92,
        yfinance_resolves=True,
        final_ticker="LMT",
        note=None,
    )

    assert AuditRow.model_validate(row.model_dump()) == row


def test_build_universe_defaults_use_last_completed_fy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fy=None passes the FY window from _last_completed_fy_window to the fetcher."""
    captured: dict[str, object] = {}

    def fake_fetch(
        fy_start: date,
        fy_end: date,
        **_kw: object,
    ) -> list[RecipientRecord]:
        captured["fy_start"] = fy_start
        captured["fy_end"] = fy_end
        return []

    monkeypatch.setattr("src.federal_contractors.fetch_top_contractors", fake_fetch)
    monkeypatch.setattr(
        "src.federal_contractors._load_records",
        lambda: _records(("AAPL", "Apple Inc.", "320193")),
    )
    monkeypatch.setattr("src.federal_contractors.yf.Ticker", _StubTicker)

    build_universe(fy=None, top_n=10)

    expected_start, expected_end = _last_completed_fy_window()
    assert captured["fy_start"] == expected_start
    assert captured["fy_end"] == expected_end
