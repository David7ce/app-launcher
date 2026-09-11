#!/usr/bin/env python3
"""Vendor per-app icons into src/assets/icons/ so the running app never
needs network access. One-off maintenance script, not run by the app.

Two tiers, tried in order per entry:
1. dashboard-icons (homarr-labs), CC0-1.0, PNG via jsDelivr CDN.
2. Iconify's simple-icons set (CC0, brand marks), SVG via the public
   api.iconify.design render endpoint — tried under a couple of slug
   variants since simple-icons names rarely match our ids exactly
   (e.g. "intellij-idea" -> "intellijidea"). Rasterized to PNG via
   ImageMagick (`magick`) for the app — the original SVG resolves
   `fill="currentColor"` to black when rasterized with no surrounding
   CSS context, same as it would loaded via <img> anyway, so this is a
   flat black glyph rather than a colored one, but still a real,
   recognizable icon rather than a generic category fallback. The SVG
   itself is archived to tools/icon_sources/ — not shipped with the
   app, kept only because it's the losslessly-editable original.

CLI-flagged entries and placeholder entries with no `linux` bin (they
can never show up on this OS) are skipped — no point spending a lookup
on something that can't be displayed here.

Anything still missing after both tiers is left for manual sourcing
(UXWing pick, or a Magnific AI-generated icon) and listed in
missing_icons.txt — the app still works fine without it because of the
per-category fallback glyph.
"""
import concurrent.futures
import json
import subprocess
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "src" / "data" / "catalog.json"
ICONS_DIR = ROOT / "src" / "assets" / "icons"
SVG_ARCHIVE = ROOT / "tools" / "icon_sources"
MISSING_FILE = ROOT / "tools" / "missing_icons.txt"

DASHBOARD_ICONS_URL = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/{slug}.png"
ICONIFY_URL = "https://api.iconify.design/simple-icons/{slug}.svg"


def fetch_dashboard_icons(slug: str) -> bool:
    dest = ICONS_DIR / f"{slug}.png"
    if dest.exists():
        return True
    # jsDelivr rate-limits bursts of concurrent requests with a 403 that
    # looks identical to a real miss unless you check the status code —
    # a first pass without this retry mis-marked several very common apps
    # (vlc, obs-studio, kdenlive, ...) as absent from the CDN when they
    # were just being rate-limited. Retry a couple of times before
    # accepting a non-200 as a genuine miss.
    for attempt in range(3):
        try:
            resp = requests.get(DASHBOARD_ICONS_URL.format(slug=slug), timeout=10)
        except requests.RequestException:
            return False
        if resp.status_code == 200 and resp.content:
            dest.write_bytes(resp.content)
            return True
        if resp.status_code == 404:
            return False
        time.sleep(1.5 * (attempt + 1))
    return False


def iconify_slug_candidates(entry_id: str) -> list[str]:
    no_hyphens = entry_id.replace("-", "")
    no_underscores = entry_id.replace("_", "")
    # dict.fromkeys instead of set() to keep a stable, deduplicated order.
    return list(dict.fromkeys([entry_id, no_hyphens, no_underscores]))


def fetch_iconify(entry_id: str) -> bool:
    dest = ICONS_DIR / f"{entry_id}.png"
    if dest.exists():
        return True
    for slug in iconify_slug_candidates(entry_id):
        try:
            resp = requests.get(ICONIFY_URL.format(slug=slug), timeout=10)
        except requests.RequestException:
            continue
        if resp.status_code == 200 and resp.content.startswith(b"<svg"):
            # Archived as SVG (it's a vector, no quality lost by keeping the
            # original around) but shipped to the app as PNG, same as every
            # other icon source — see "Icon format" in SPEC.md.
            svg_path = SVG_ARCHIVE / f"{entry_id}.svg"
            svg_path.write_bytes(resp.content)
            # -density matters: without it, ImageMagick's built-in MSVG
            # delegate (no rsvg-convert on this box) rasterizes at the
            # SVG's native ~24x24 size and then -resize upscales that tiny
            # bitmap, producing a blurry blob instead of a crisp glyph.
            # Rendering at 384 DPI (72 * 128/24, simple-icons' viewBox is
            # always 24x24) makes MSVG rasterize straight to full size.
            subprocess.run(
                ["magick", "-density", "384", str(svg_path), "-background", "none",
                 "-resize", "128x128", str(dest)],
                check=True,
            )
            return True
    return False


def fetch_one(entry_id: str) -> bool:
    return fetch_dashboard_icons(entry_id) or fetch_iconify(entry_id)


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    SVG_ARCHIVE.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text())
    ids = sorted({
        entry["id"] for entry in catalog
        if not entry.get("cli") and "linux" in entry.get("bin", {})
    })

    hits, misses = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for entry_id, ok in zip(ids, pool.map(fetch_one, ids)):
            (hits if ok else misses).append(entry_id)

    MISSING_FILE.write_text("\n".join(misses) + "\n")
    print(f"fetched or already had: {len(hits)}/{len(ids)}")
    print(f"missing: {len(misses)} — see {MISSING_FILE.relative_to(ROOT)}")
    print("missing entries fall back to the per-category glyph at runtime; "
          "no action required unless you want to hand-source specific ones.")


if __name__ == "__main__":
    main()
