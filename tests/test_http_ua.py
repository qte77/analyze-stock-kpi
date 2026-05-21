"""Tests for :mod:`src.http_ua` — browser-shape User-Agent pool + mixer."""

from __future__ import annotations

import random

from src.http_ua import USER_AGENTS, pick_user_agent


def test_pick_user_agent_returns_value_from_pool() -> None:
    """Every call returns one of the strings in :data:`USER_AGENTS`."""
    result = pick_user_agent()
    assert result in USER_AGENTS


def test_pick_user_agent_delegates_to_provided_rng() -> None:
    """When an ``rng`` is passed, ``pick_user_agent`` uses its ``.choice``."""

    class StubRng:
        def __init__(self) -> None:
            self.choice_arg: tuple[str, ...] | None = None

        def choice(self, seq: tuple[str, ...]) -> str:
            self.choice_arg = seq
            return "STUB_SENTINEL_UA"

    stub = StubRng()
    result = pick_user_agent(stub)

    assert result == "STUB_SENTINEL_UA"
    assert stub.choice_arg is USER_AGENTS


def test_pick_user_agent_seeded_rng_is_deterministic() -> None:
    """Same seed yields the same UA on independent runs."""
    a = pick_user_agent(random.Random(42))  # noqa: S311  # determinism test, not crypto
    b = pick_user_agent(random.Random(42))  # noqa: S311  # determinism test, not crypto
    assert a == b
