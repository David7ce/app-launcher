#!/usr/bin/env python3
"""Generate the 10 generic per-category fallback glyphs as plain SVG.

These are used only when a catalog entry's own icon is missing (see
sync_icons.py). Hand-authored here instead of sourced from UXWing/SvgRepo:
zero licensing questions, zero network dependency, trivially reproducible.
One-off script, not run by the app.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "assets" / "icons" / "category"

# category -> (background color, short label)
GLYPHS = {
    "Development": ("#4C6EF5", "</>"),
    "Education":   ("#F59F00", "Edu"),
    "Graphics":    ("#E64980", "Gfx"),
    "Internet":    ("#228BE6", "Net"),
    "Games":       ("#7048E8", "Gm"),
    "Multimedia":  ("#12B886", "A/V"),
    "Office":      ("#5C636A", "Doc"),
    "Science":     ("#15AABF", "Sci"),
    "System":      ("#868E96", "Sys"),
    "Utilities":   ("#FD7E14", "Util"),
}

SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="{color}"/>
  <text x="32" y="38" font-family="sans-serif" font-size="{font_size}" font-weight="600"
        fill="#ffffff" text-anchor="middle">{label}</text>
</svg>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for category, (color, label) in GLYPHS.items():
        font_size = 16 if len(label) <= 3 else 13
        svg = SVG_TEMPLATE.format(color=color, label=label, font_size=font_size)
        (OUT / f"{category}.svg").write_text(svg)
    print(f"wrote {len(GLYPHS)} category glyphs to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
