"""Build a demo dashboard manifest by scanning dated snapshot files.

Used by .github/workflows/demo-snapshot.yml to keep
``results/demo/<UNIVERSE>/index.json`` in sync with the dated snapshot files
in the same directory. The manifest enables the static dashboard to discover
which dates have snapshots without calling the GitHub API at page load.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def main(directory: Path) -> int:
    if not directory.is_dir():
        print(f"not a directory: {directory}", file=sys.stderr)
        return 1
    dates = sorted(f.stem for f in directory.glob("*.json") if _DATE_PATTERN.match(f.name))
    if not dates:
        print(f"no YYYY-MM-DD.json files in {directory}", file=sys.stderr)
        return 1
    manifest = {
        "universe": directory.name,
        "latest": dates[-1],
        "dates": dates,
        "updated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (directory / "index.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {directory / 'index.json'} ({len(dates)} dates)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: build_demo_manifest.py <dir>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
