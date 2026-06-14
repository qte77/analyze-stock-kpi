"""Audit every bundled universe against current Yahoo coverage (#168).

Thin wrapper around :func:`analyze_stock_kpi.orchestrators.universe_audit.audit_universes`.
Writes the structured report to ``results/audit/universes-<UTC-date>.json``
for operator triage — surfaces stale-US-ticker rot (FI→FISV, RY→RY.TO,
SUEZY→SZU.DE patterns) so per-ticker swap PRs can be opened.

Operator-only one-shot; no cron. Run ad-hoc::

    uv run python scripts/audit_universes.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from analyze_stock_kpi.orchestrators.universe_audit import audit_universes


def main() -> None:
    """Build the audit report and persist to ``results/audit/``."""
    report = audit_universes()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    out_path = Path(f"results/audit/universes-{today}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2))
    print(f"Audited {len(report.entries_by_universe)} universes → {out_path}")
    for universe_id, entries in report.entries_by_universe.items():
        counts: dict[str, int] = {"OK": 0, "SPARSE": 0, "FAIL": 0}
        for entry in entries:
            counts[entry.classification] += 1
        print(
            f"  {universe_id:30s} "
            f"OK={counts['OK']:>4d}  "
            f"SPARSE={counts['SPARSE']:>3d}  "
            f"FAIL={counts['FAIL']:>3d}"
        )


if __name__ == "__main__":
    main()
