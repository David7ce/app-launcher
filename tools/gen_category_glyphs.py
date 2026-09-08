#!/usr/bin/env python3
"""Generate the 10 generic per-category fallback glyphs (plus the CLI-tool
glyph) as PNG — the uniform format every icon in the app ships as (see
"Icon format" in SPEC.md).

Authored as SVG first, since a rounded-rect-plus-label vector is much
easier to hand-tweak than raw pixels, then rasterized to PNG via
ImageMagick (`magick`). The SVG source is archived to
tools/icon_sources/category/ — not shipped with the app, just kept
around because it's the losslessly-editable original if these ever need
retouching, unlike the rasterized PNG.

Hand-authored instead of sourced from UXWing/SvgRepo: zero licensing
questions, zero network dependency, trivially reproducible. One-off
script, not run by the app.
"""
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "assets" / "icons" / "category"
SVG_ARCHIVE = ROOT / "tools" / "icon_sources" / "category"

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

# A dedicated glyph for CLI-only tools (terminal-prompt look), distinct from
# the 10 category glyphs so a missing icon on a CLI tool doesn't read the
# same as a missing icon on a GUI app.
CLI_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#1e1e1e"/>
  <text x="10" y="40" font-family="monospace" font-size="22" font-weight="700"
        fill="#4ade80">&gt;_</text>
</svg>
"""


def write_glyph(name: str, svg: str) -> None:
    svg_path = SVG_ARCHIVE / f"{name}.svg"
    svg_path.write_text(svg)
    subprocess.run(
        ["magick", str(svg_path), "-background", "none", "-resize", "128x128", str(OUT / f"{name}.png")],
        check=True,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SVG_ARCHIVE.mkdir(parents=True, exist_ok=True)
    for category, (color, label) in GLYPHS.items():
        font_size = 16 if len(label) <= 3 else 13
        # Text content in SVG is XML — a raw "<" (as in the "</>" label)
        # would otherwise start what looks like a tag, making the file
        # invalid XML that silently fails to render.
        svg = SVG_TEMPLATE.format(color=color, label=escape(label), font_size=font_size)
        write_glyph(category, svg)
    write_glyph("cli-tool", CLI_SVG)
    print(f"wrote {len(GLYPHS)} category glyphs + 1 CLI-tool glyph "
          f"to {OUT.relative_to(ROOT)} (SVG sources archived in {SVG_ARCHIVE.relative_to(ROOT)})")


if __name__ == "__main__":
    main()
