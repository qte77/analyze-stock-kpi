"""Browser-shape User-Agent string pool for HTTP requests.

Some endpoints (CNN's WAF, SEC's rate-limit profile) treat unidentified
clients as bots; sending a current desktop-browser ``User-Agent`` blends
the egress with regular visitor traffic. Refresh :data:`USER_AGENTS`
quarterly from https://useragents.me/ — pick top entries from the
"Most common desktop user-agents" table.

Callers wanting per-request rotation use :func:`pick_user_agent`;
callers needing a stable UA (CNN's WAF profiles by UA over time)
pin one specific entry from :data:`USER_AGENTS` directly.

The mixer is intentionally pure string utility — no HTTP client
concerns here. The actual ``urllib.request`` calls live in each
endpoint's module (``src.sentiment`` for CNN, ``src.sec.cik_map`` etc.
for EDGAR).
"""

from __future__ import annotations

import random  # UA shuffling, not crypto
from typing import Protocol

from analyze_stock_kpi.config import settings

# Re-exports from settings (the canonical UA pool lives in AppSettings).
# Refresh ``settings.user_agents`` quarterly from https://useragents.me/.
USER_AGENTS: tuple[str, ...] = settings.user_agents

STABLE_USER_AGENT: str = settings.user_agents[0]
"""Pinned User-Agent for endpoints that profile per-UA over time.

CNN's WAF observed to flag clients whose UA changes between requests as
likely bots. Callers hitting such endpoints import ``STABLE_USER_AGENT``
directly; callers hitting SEC-style rate limiters that don't track per-UA
behaviour use :func:`pick_user_agent` for rotation.
"""


class _RngLike(Protocol):
    """Duck-type for any object with ``random.Random``-style ``choice``."""

    def choice(self, seq: tuple[str, ...]) -> str: ...


def pick_user_agent(rng: _RngLike | None = None) -> str:
    """Return a randomly-chosen User-Agent from :data:`USER_AGENTS`.

    Pass a seeded :class:`random.Random` (or any duck-typed object with
    a compatible ``choice`` method) for deterministic tests; omit for
    the module-level ``random`` instance.
    """
    chooser: _RngLike = rng if rng is not None else random
    return chooser.choice(USER_AGENTS)


def require_https(url: str) -> None:
    """Raise ``ValueError`` if ``url`` does not begin with ``https://``.

    Defence-in-depth guard at every ``urllib.urlopen()`` call site:
    the URLs come from :class:`analyze_stock_kpi.config.AppSettings` strings that
    ARE HTTPS today, but a future refactor could route external input
    through them.
    """
    if not url.startswith("https://"):
        raise ValueError(f"Refusing non-HTTPS URL: {url!r}")
