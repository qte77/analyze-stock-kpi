"""Browser e2e for the dashboard (plan 010, slice 0).

Renders the page in headless Chromium across phone (portrait + landscape) and
desktop, light and dark, then checks: no unexpected console errors or failed
requests, charts drawn, the universe table filled, and the F&G tabs clickable.
Screenshots (and, with ``--video``, recordings) go to ``--out``.

Needs the sibling ``../polyfetch-scrape`` checkout (Patchright + its Chromium):

    make preview                                   # in another shell
    uv run --project ../polyfetch-scrape python scripts/e2e_ui.py
    uv run --project ../polyfetch-scrape python scripts/e2e_ui.py \
        --url https://qte77.github.io/analyze-stock-kpi/

Exits non-zero when any check fails.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

from patchright.sync_api import sync_playwright

# (name, width, height, touch)
VIEWPORTS = (
    ("phone-portrait", 390, 844, True),
    ("phone-landscape", 844, 390, True),
    ("desktop", 1440, 900, False),
)
SCHEMES = ("light", "dark")

# The dashboard probes one year file per year back from today until a series
# starts; those 404s are expected. Any other >= 400 response is a failure.
_EXPECTED_404 = re.compile(r"/results/(series|backtest)[\w/-]*/\d{4}\.json$")
# Chromium logs every 4xx as a console error without the URL; the response
# check above judges those, so they are not counted twice.
_NETWORK_CONSOLE_NOISE = "Failed to load resource"


def check_page(page, name: str, out: Path) -> list[str]:
    """Run the checks on a loaded page; return the failures."""
    failures: list[str] = []
    page.wait_for_selector("#universe-section tbody tr", timeout=60_000)
    page.wait_for_timeout(1500)  # let charts finish their first draw

    charts = page.evaluate(
        "typeof Chart === 'undefined' ? 0 : Object.keys(Chart.instances).length",
        isolated_context=False,
    )
    if charts == 0:
        failures.append("no Chart.js instances rendered")

    rows = page.locator("#universe-section tbody tr").count()
    if rows == 0:
        failures.append("universe table has no rows")

    failures += check_todays_picks(page)

    # Slice 1: market mood starts collapsed; its summary toggles it by click and keyboard.
    panel = page.locator("#fg-panel")
    summary = page.locator("#fg-panel > summary")
    if panel.evaluate("d => d.open"):
        failures.append("market-mood panel is open on load (should start collapsed)")
    summary.click()
    if not panel.evaluate("d => d.open"):
        failures.append("clicking the market-mood summary did not open it")

    tab = page.locator("#fg-tabs [role=tab]").nth(1)
    tab.click()
    if tab.get_attribute("aria-selected") != "true":
        failures.append("second F&G tab did not become selected on click")

    page.screenshot(path=str(out / f"{name}.png"), full_page=True)
    summary.focus()
    page.keyboard.press("Enter")
    if panel.evaluate("d => d.open"):
        failures.append("Enter on the focused market-mood summary did not close it")
    return failures


def check_todays_picks(page) -> list[str]:
    """Plan 010 slice 2: Best/Worst 25 lead the page; 10 rows + "Show all 25"; Best above
    Worst when stacked on narrow screens (D3), side by side otherwise."""
    failures: list[str] = []
    page.wait_for_selector("#picks-body .picks-list", timeout=30_000)

    def top(sel: str) -> float:
        return page.locator(sel).first.bounding_box()["y"]

    if not top("#todays-picks") < top("#backtest-section") < top("#universe-section"):
        failures.append("Today's picks is not above the backtest and universe sections")
    lists = page.locator("#picks-body .picks-list")
    if lists.count() != 2:
        return [*failures, f"expected 2 pick lists, found {lists.count()}"]
    best, worst = lists.nth(0), lists.nth(1)
    shown = best.locator(":scope > ol > li").count()
    if shown != 10:
        failures.append(f"Best list shows {shown} rows before 'Show all', expected 10")
    best.locator("details > summary").click()
    more = best.locator("details > ol > li").count()
    if more != 15:
        failures.append(f"'Show all 25' revealed {more} more rows, expected 15")
    narrow = page.viewport_size["width"] < 640
    b_box, w_box = best.bounding_box(), worst.bounding_box()
    if narrow and not b_box["y"] < w_box["y"]:
        failures.append("on a narrow screen Best is not stacked above Worst")
    if not narrow and abs(b_box["y"] - w_box["y"]) > 1:
        failures.append("on a wide screen Best and Worst are not side by side")
    return failures


def check_deep_link(browser, url: str) -> list[str]:
    """Plan 010 D1: `?ltFgWindow=` opens the market-mood panel on its long-term tab."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    sep = "&" if "?" in url else "?"
    page.goto(f"{url}{sep}ltFgWindow=5y", wait_until="networkidle", timeout=90_000)
    page.wait_for_selector("#universe-section tbody tr", timeout=60_000)
    failures = []
    if not page.locator("#fg-panel").evaluate("d => d.open"):
        failures.append("?ltFgWindow=5y did not open the market-mood panel")
    if page.locator("#fg-tab-longterm").get_attribute("aria-selected") != "true":
        failures.append("?ltFgWindow=5y did not select the long-term tab")
    # Plan 010 D8: an explicit ?universe= still drives the universe picker.
    page.goto(f"{url}{sep}universe=sp500", wait_until="networkidle", timeout=90_000)
    page.wait_for_selector("#universe-section tbody tr", timeout=60_000)
    picked = page.locator("#universe-picker").input_value()
    if picked != "sp500":
        failures.append(f"?universe=sp500 left the picker on {picked!r}")
    ctx.close()
    return failures


def run(url: str, out: Path, *, video: bool) -> int:
    out.mkdir(parents=True, exist_ok=True)
    failed = False
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp_name, width, height, touch in VIEWPORTS:
            for scheme in SCHEMES:
                name = f"{vp_name}-{scheme}"
                ctx = browser.new_context(
                    viewport={"width": width, "height": height},
                    is_mobile=touch,
                    has_touch=touch,
                    color_scheme=scheme,
                    record_video_dir=str(out / "video") if video else None,
                )
                page = ctx.new_page()
                errors: list[str] = []
                page.on(
                    "console",
                    lambda m, errors=errors: errors.append(f"console: {m.text}")
                    if m.type == "error" and not m.text.startswith(_NETWORK_CONSOLE_NOISE)
                    else None,
                )
                page.on(
                    "response",
                    lambda r, errors=errors: errors.append(f"HTTP {r.status}: {r.url}")
                    if r.status >= 400 and not _EXPECTED_404.search(r.url)
                    else None,
                )
                page.on(
                    "requestfailed",
                    lambda r, errors=errors: errors.append(f"request failed: {r.url}"),
                )
                try:
                    page.goto(url, wait_until="networkidle", timeout=90_000)
                    failures = check_page(page, name, out) + errors
                except Exception as exc:  # report it for this run, keep checking the rest
                    failures = [f"{type(exc).__name__}: {str(exc).splitlines()[0]}", *errors]
                ctx.close()
                failed |= bool(failures)
                print(f"{'FAIL' if failures else 'ok  '} {name}")
                for f in failures:
                    print(f"     {f}")
        try:
            link_failures = check_deep_link(browser, url)
        except Exception as exc:  # report it, don't lose the summary
            link_failures = [f"{type(exc).__name__}: {str(exc).splitlines()[0]}"]
        failed |= bool(link_failures)
        print(f"{'FAIL' if link_failures else 'ok  '} deep-link ?ltFgWindow=5y")
        for f in link_failures:
            print(f"     {f}")
        browser.close()
    print(f"screenshots: {out}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:8000/analyze-stock-kpi/")
    parser.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "e2e-ui")
    parser.add_argument("--video", action="store_true", help="also record a video per run")
    args = parser.parse_args()
    return run(args.url, args.out, video=args.video)


if __name__ == "__main__":
    sys.exit(main())
