"""Tests for :mod:`src.http_ua` — browser-shape User-Agent pool + mixer."""

from __future__ import annotations

from src.http_ua import USER_AGENTS, pick_user_agent


def test_pick_user_agent_returns_value_from_pool() -> None:
    """Every call returns one of the strings in :data:`USER_AGENTS`."""
    result = pick_user_agent()
    assert result in USER_AGENTS
