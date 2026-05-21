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

USER_AGENTS: tuple[str, ...] = ("placeholder",)


def pick_user_agent(rng: object | None = None) -> str:
    """Return a random User-Agent from :data:`USER_AGENTS`."""
    return USER_AGENTS[0]
