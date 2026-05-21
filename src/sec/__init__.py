"""SEC EDGAR integration — keyless public-data access.

All modules here require the SEC-mandated ``User-Agent`` header on
HTTP requests; the value is read from :data:`~src.sec.cik_map.USER_AGENT`.

See [ADR-0006](../../docs/decisions/0006-federal-contractors-universe.md)
for the integration design.
"""
