"""Refresh the federal-contractors preset + audit JSON.

Thin wrapper around :func:`analyze_stock_kpi.orchestrators.federal_contractors.build_universe`.
Writes the preset to ``src/analyze_stock_kpi/assets/universes/federal-contractors.txt`` (the
bundled asset shipped in the wheel) and the audit JSON to
``results/federal_contractors/audit/<UTC-date>.json``.

Invoked by ``.github/workflows/federal-contractors-refresh.yaml`` on a
Sunday cron; can also be run ad-hoc locally.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from analyze_stock_kpi.config import settings
from analyze_stock_kpi.orchestrators.federal_contractors import build_universe


def main() -> None:
    """Build the universe and persist both outputs."""
    tickers, audit_rows = build_universe()

    preset_path = Path("src/analyze_stock_kpi/assets/universes/federal-contractors.txt")
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    audit_path = settings.federal_contractors_dir / "audit" / f"{today}.json"

    preset_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    preset_path.write_text("\n".join(sorted(set(tickers))) + "\n")
    audit_path.write_text(json.dumps([row.model_dump() for row in audit_rows], indent=2))
    print(f"Wrote {len(tickers)} tickers to {preset_path}")
    print(f"Wrote {len(audit_rows)} audit rows to {audit_path}")


if __name__ == "__main__":
    main()
