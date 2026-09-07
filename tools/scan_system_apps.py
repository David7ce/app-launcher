#!/usr/bin/env python3
"""Scan this machine's installed .desktop files and write them to
tools/sources/system_apps.json for build_catalog.py to merge in.

Why: the curated desktop-pkgs.json dataset only covers ~250 well-known
apps. Every real Linux desktop already has a complete, authoritative list
of what's actually installed — the XDG .desktop files each package drops
into /usr/share/applications (and friends) — including a name, a
freedesktop Categories= (the same vocabulary our 10 categories map from),
and an Icon= that the current icon theme (or an absolute path) resolves
to a real file already on disk. So: read those instead of guessing.

Icons resolved this way are copied straight into src/assets/icons/ (the
one shared icon folder) so the running app never has to repeat the
lookup — this script is the only thing that touches the icon theme.

One-off maintenance script, not run by the app. Machine-specific by
nature (it reflects what's installed *here*) — re-run it after installing
new software you want to show up.
"""
import configparser
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = ROOT / "src" / "assets" / "icons"
OUT = ROOT / "tools" / "sources" / "system_apps.json"

APPLICATION_DIRS = [
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
    Path.home() / ".local/share/applications",
    Path("/var/lib/flatpak/exports/share/applications"),
    Path.home() / ".local/share/flatpak/exports/share/applications",
    Path("/var/lib/snapd/desktop/applications"),
]

ICON_BASE_DIRS = [
    Path.home() / ".local/share/icons",
    Path.home() / ".icons",
    Path("/usr/share/icons"),
    Path("/usr/local/share/icons"),
]

# freedesktop.org registered Categories= tokens -> our 10 fixed categories.
FREEDESKTOP_CATEGORY_MAP = {
    "AudioVideo": "Multimedia", "Audio": "Multimedia", "Video": "Multimedia",
    "Development": "Development",
    "Education": "Education",
    "Game": "Games",
    "Graphics": "Graphics",
    "Network": "Internet", "WebBrowser": "Internet", "Email": "Internet",
    "InstantMessaging": "Internet", "Chat": "Internet",
    "Office": "Office",
    "Science": "Science",
    "Settings": "System", "System": "System", "Security": "System",
    "Utility": "Utilities", "Accessibility": "Utilities",
}

FIELD_CODE_RE = re.compile(r"%[a-zA-Z%]")


def active_icon_theme() -> str:
    for tool in ("kreadconfig6", "kreadconfig5"):
        try:
            result = subprocess.run(
                [tool, "--file", "kdeglobals", "--group", "Icons", "--key", "Theme"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except FileNotFoundError:
            continue
    return "breeze"


def first_exec_token(exec_line: str) -> str | None:
    cleaned = FIELD_CODE_RE.sub("", exec_line).strip()
    if not cleaned:
        return None
    parts = cleaned.split()
    token = parts[0].strip('"')
    return Path(token).name  # strip any leading path


def map_category(categories: str) -> str:
    for token in categories.split(";"):
        if token in FREEDESKTOP_CATEGORY_MAP:
            return FREEDESKTOP_CATEGORY_MAP[token]
    return "Utilities"  # unrecognized tokens still get a home, not dropped


def find_icon_file(icon_value: str, theme_priority: list[str]) -> Path | None:
    if not icon_value:
        return None
    if icon_value.startswith("/"):
        p = Path(icon_value)
        return p if p.is_file() else None

    for base in ICON_BASE_DIRS:
        for theme in theme_priority:
            theme_dir = base / theme
            if not theme_dir.is_dir():
                continue
            hits: list[Path] = []
            for ext in ("svg", "png"):
                # hicolor-style: <size>/apps/<name>.<ext>
                hits += list(theme_dir.glob(f"**/apps/{icon_value}.{ext}"))
                # breeze-style: apps/<size>/<name>.<ext>
                hits += list(theme_dir.glob(f"apps/**/{icon_value}.{ext}"))
            if hits:
                svgs = [h for h in hits if h.suffix == ".svg"]
                return svgs[0] if svgs else hits[0]

    for ext in ("svg", "png", "xpm"):
        p = Path(f"/usr/share/pixmaps/{icon_value}.{ext}")
        if p.is_file():
            return p
    return None


def parse_desktop_file(path: Path) -> dict | None:
    parser = configparser.RawConfigParser(strict=False)
    try:
        parser.read(path, encoding="utf-8")
    except (UnicodeDecodeError, configparser.Error):
        return None
    if not parser.has_section("Desktop Entry"):
        return None
    entry = parser["Desktop Entry"]

    if entry.get("Type", "Application") != "Application":
        return None
    if entry.get("NoDisplay", "false").lower() == "true":
        return None
    if entry.get("Hidden", "false").lower() == "true":
        return None

    name = entry.get("Name")
    exec_line = entry.get("Exec")
    if not name or not exec_line:
        return None
    bin_name = first_exec_token(exec_line)
    if not bin_name:
        return None

    return {
        "id": path.stem,
        "name": name,
        "bin": bin_name,
        "category": map_category(entry.get("Categories", "")),
        "icon_name": entry.get("Icon", ""),
    }


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    theme_priority = [active_icon_theme(), "breeze", "Adwaita", "hicolor"]

    seen_paths: set[Path] = set()
    results = []
    icons_copied = icons_missing = 0

    for app_dir in APPLICATION_DIRS:
        if not app_dir.is_dir():
            continue
        for desktop_file in sorted(app_dir.glob("*.desktop")):
            resolved = desktop_file.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)

            parsed = parse_desktop_file(desktop_file)
            if parsed is None:
                continue

            icon_path = find_icon_file(parsed.pop("icon_name"), theme_priority)
            icon_field = None
            if icon_path is not None:
                dest = ICONS_DIR / f"{parsed['id']}{icon_path.suffix}"
                if not dest.exists():
                    shutil.copy(icon_path, dest)
                icon_field = dest.name
                icons_copied += 1
            else:
                icons_missing += 1

            parsed["icon"] = icon_field
            results.append(parsed)

    OUT.write_text(json.dumps(results, indent=2) + "\n")
    print(f"scanned {len(results)} local .desktop apps -> {OUT.relative_to(ROOT)}")
    print(f"icons: {icons_copied} resolved from the system theme, {icons_missing} missing "
          f"(those fall back to the category/CLI glyph, same as before)")


if __name__ == "__main__":
    main()
