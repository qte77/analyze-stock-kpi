"""SEC EDGAR integration — keyless public-data access.

**SEC** = US Securities and Exchange Commission, the federal agency
that regulates public companies. **EDGAR** = Electronic Data Gathering,
Analysis, and Retrieval — SEC's electronic filing system and its
public API surface (``data.sec.gov`` / ``www.sec.gov/files/...``).

All modules here send a browser-shape ``User-Agent`` header on every
HTTP request. The pool of UA strings lives in :mod:`src.http_ua`;
refresh it quarterly from https://useragents.me/.

See [ADR-0006](../../docs/decisions/0006-federal-contractors-universe.md)
for the integration design.
"""
