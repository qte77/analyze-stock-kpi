"""Drift guard for `.github/templates/llms.txt.tpl` (#416).

The template is hand-maintained (the llms-txt workflow only substitutes
variables), so it silently fell behind the tree. This fails when an ADR or a
source module is added without a matching template link.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".github" / "templates" / "llms.txt.tpl"


def _expected_paths() -> list[str]:
    adrs = sorted(ROOT.glob("docs/decisions/[0-9][0-9][0-9][0-9]-*.md"))
    modules = sorted(
        p for p in (ROOT / "src" / "analyze_stock_kpi").rglob("*.py") if p.name != "__init__.py"
    )
    return [p.relative_to(ROOT).as_posix() for p in [*adrs, *modules]]


def test_template_links_every_adr_and_module() -> None:
    template = TEMPLATE.read_text()
    missing = [path for path in _expected_paths() if f"(${{BLOB}}/{path})" not in template]
    assert missing == []
