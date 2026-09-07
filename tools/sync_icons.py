#!/usr/bin/env python3
"""Vendor per-app icons into src/assets/icons/ so the running app never
needs network access. One-off maintenance script, not run by the app.

Primary source: dashboard-icons (homarr-labs), CC0-1.0, PNG via jsDelivr CDN.
Anything not found there is left for manual sourcing (UXWing pick, or a
Magnific AI-generated icon) and listed in missing_icons.txt — the app still
works fine without it because of the per-category fallback glyph.
"""
import concurrent.futures
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "src" / "data" / "catalog.json"
ICONS_DIR = ROOT / "src" / "assets" / "icons"
MISSING_FILE = ROOT / "tools" / "missing_icons.txt"

CDN_URL = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/{slug}.png"


def fetch_one(slug: str) -> bool:
    dest = ICONS_DIR / f"{slug}.png"
    if dest.exists():
        return True
    try:
        resp = requests.get(CDN_URL.format(slug=slug), timeout=10)
    except requests.RequestException:
        return False
    if resp.status_code == 200 and resp.content:
        dest.write_bytes(resp.content)
        return True
    return False


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text())
    slugs = sorted({entry["id"] for entry in catalog})

    hits, misses = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for slug, ok in zip(slugs, pool.map(fetch_one, slugs)):
            (hits if ok else misses).append(slug)

    MISSING_FILE.write_text("\n".join(misses) + "\n")
    print(f"fetched or already had: {len(hits)}/{len(slugs)}")
    print(f"missing: {len(misses)} — see {MISSING_FILE.relative_to(ROOT)}")
    print("missing entries fall back to the per-category glyph at runtime; "
          "no action required unless you want to hand-source specific ones.")


if __name__ == "__main__":
    main()
