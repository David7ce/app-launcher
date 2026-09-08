#!/usr/bin/env python3
"""macOS equivalent of scan_system_apps.py — scan installed .app bundles
and write tools/sources/system_apps_macos.json for build_catalog.py to
merge in (into the `macos` slot of each entry's per-OS `bin` object, same
non-destructive merge as the Linux scan uses).

UNVERIFIED ON REAL macOS — this machine is Fedora/KDE only, so this
script has never actually been run against a real /Applications. What
*has* been checked: the Info.plist parsing logic, using `plistlib`
(pure Python stdlib, no macOS-specific module needed) against a
synthetic fixture built by hand — see the bottom of this file for the
`--self-test` mode that exercises it without needing a Mac. That
confirms the *parsing* is correct; it does not confirm real-world
Info.plist files won't have some quirk this hasn't accounted for.

Each .app bundle's Contents/Info.plist carries a `CFBundleName` (or
`CFBundleDisplayName`), a `CFBundleIconFile` (the icon's filename,
often without its .icns extension, inside Contents/Resources/), and
sometimes an `LSApplicationCategoryType` (an App Store category UTI
string, e.g. "public.app-category.developer-tools") mapped below to
our 10 categories the same way freedesktop's Categories= is on Linux.
"""
import json
import plistlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = ROOT / "src" / "assets" / "icons"
OUT = ROOT / "tools" / "sources" / "system_apps_macos.json"

APPLICATION_DIRS = [
    Path("/Applications"),
    Path("/System/Applications"),
    Path.home() / "Applications",
]

# public.app-category.* UTI suffix -> our 10 fixed categories. Anything
# not listed here defaults to Utilities, same catch-all policy as the
# Linux scan's map_category().
APP_CATEGORY_MAP = {
    "developer-tools": "Development",
    "education": "Education",
    "reference": "Education",
    "graphics-design": "Graphics",
    "photography": "Graphics",
    "games": "Games",
    "action-games": "Games",
    "adventure-games": "Games",
    "arcade-games": "Games",
    "board-games": "Games",
    "card-games": "Games",
    "casino-games": "Games",
    "dice-games": "Games",
    "educational-games": "Games",
    "family-games": "Games",
    "kids-games": "Games",
    "music-games": "Games",
    "puzzle-games": "Games",
    "racing-games": "Games",
    "role-playing-games": "Games",
    "simulation-games": "Games",
    "sports-games": "Games",
    "strategy-games": "Games",
    "trivia-games": "Games",
    "word-games": "Games",
    "music": "Multimedia",
    "video": "Multimedia",
    "productivity": "Office",
    "business": "Office",
    "social-networking": "Internet",
    "news": "Internet",
    "utilities": "Utilities",
}


def map_category(bundle_category: str | None) -> str:
    if not bundle_category:
        return "Utilities"
    suffix = bundle_category.rsplit(".", 1)[-1]
    return APP_CATEGORY_MAP.get(suffix, "Utilities")


def parse_app_bundle(app_path: Path) -> dict | None:
    plist_path = app_path / "Contents" / "Info.plist"
    if not plist_path.is_file():
        return None
    try:
        with plist_path.open("rb") as f:
            info = plistlib.load(f)
    except (plistlib.InvalidFileException, OSError):
        return None

    name = info.get("CFBundleDisplayName") or info.get("CFBundleName") or app_path.stem
    bin_name = app_path.stem  # what `open -a "<name>"` expects
    icon_file = info.get("CFBundleIconFile")
    icon_path = None
    if icon_file:
        if not Path(icon_file).suffix:
            icon_file += ".icns"
        candidate = app_path / "Contents" / "Resources" / icon_file
        if candidate.is_file():
            icon_path = candidate

    return {
        "id": f"macos-{app_path.stem.lower().replace(' ', '-')}",
        "name": name,
        "bin": bin_name,
        "category": map_category(info.get("LSApplicationCategoryType")),
        "icon_path": str(icon_path) if icon_path else None,
    }


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    icons_copied = icons_missing = 0

    for app_dir in APPLICATION_DIRS:
        if not app_dir.is_dir():
            continue
        for app_path in sorted(app_dir.glob("*.app")):
            entry = parse_app_bundle(app_path)
            if entry is None:
                continue
            # .icns needs conversion to something a browser <img> can render
            # (png/svg) -- not attempted here (would need `sips`/`iconutil`,
            # both macOS-only, so this can't be written or tested from this
            # machine either). Every entry falls back to the category glyph
            # for now regardless of whether an .icns was actually found.
            entry.pop("icon_path")
            entry["icon"] = None
            icons_missing += 1
            results.append(entry)

    OUT.write_text(json.dumps(results, indent=2) + "\n")
    print(f"scanned {len(results)} local .app bundles -> {OUT.relative_to(ROOT)}")
    print(f"icons: {icons_copied} converted, {icons_missing} left for the category glyph "
          "(.icns -> web-displayable conversion not implemented, see comment in this file)")


def self_test() -> None:
    """Exercises parse_app_bundle() against a synthetic .app bundle, since
    there's no real macOS machine to test this against. Run with
    `python3 scan_system_apps_macos.py --self-test`."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        app_path = Path(tmp) / "Example Editor.app"
        (app_path / "Contents" / "Resources").mkdir(parents=True)
        plist = {
            "CFBundleName": "Example Editor",
            "CFBundleIconFile": "AppIcon",
            "LSApplicationCategoryType": "public.app-category.developer-tools",
        }
        with (app_path / "Contents" / "Info.plist").open("wb") as f:
            plistlib.dump(plist, f)
        (app_path / "Contents" / "Resources" / "AppIcon.icns").write_bytes(b"fake")

        entry = parse_app_bundle(app_path)
        assert entry is not None, "parse_app_bundle returned None for a valid bundle"
        assert entry["name"] == "Example Editor", entry
        assert entry["bin"] == "Example Editor", entry
        assert entry["category"] == "Development", entry
        assert entry["icon_path"] and entry["icon_path"].endswith("AppIcon.icns"), entry
        print("self-test passed: parse_app_bundle() reads name/bin/category/icon correctly")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        main()
