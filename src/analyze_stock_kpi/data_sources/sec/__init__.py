"""SEC EDGAR integration — keyless public-data access.

**SEC** = US Securities and Exchange Commission, the federal agency
that regulates public companies. **EDGAR** = Electronic Data Gathering,
Analysis, and Retrieval — SEC's electronic filing system and its
public API surface (``data.sec.gov`` / ``www.sec.gov/files/...``).

All modules here send a browser-shape ``User-Agent`` header on every
HTTP request (from :mod:`analyze_stock_kpi.utils.http_ua`, refresh quarterly from
https://useragents.me/) plus the shared ``Accept`` header from
``settings.http_accept``.

See [ADR-0006](../../docs/decisions/0006-federal-contractors-universe.md)
for the integration design.
"""
