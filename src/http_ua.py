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

# Current desktop User-Agents per useragents.me — refresh quarterly.
# Last refreshed: 2026-05-20.
USER_AGENTS: tuple[str, ...] = (
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.10 Safari/605.1.1",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) "
    "Gecko/20100101 Firefox/135.0",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36",
)


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
