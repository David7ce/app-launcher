#!/usr/bin/env python3
"""Fill in missing icons for catalog entries that resolve on this machine.

The Windows system scan (`scan/windows.py`) only sees apps the
registry lists under its Uninstall keys. Plenty of launchable apps never
appear there — Office's Word/Excel/PowerPoint/OneNote, for instance, are
installed as one suite and registered only in the App Paths key — so they
have a launch target but no icon and render as a generic placeholder.

This walks the catalog, resolves each Windows entry's launch target the same
way the app does ($PATH, then the registry's App Paths key), and pulls the
icon out of the executable's own resources for anything still missing one.

Windows-only: the equivalent gaps on Linux/macOS are handled by their own
scans (the Linux `.desktop` icon-theme lookup, and — not yet implemented —
macOS `.icns` extraction). Run from the repo root; icons are staged into
tools/icons/cache/ and placed by `build_catalog.py`.
"""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG = ROOT / "src" / "data" / "catalog.json"
ICONS_DIR = ROOT / "src" / "assets" / "icons"
ICON_CACHE = ROOT / "tools" / "icons" / "cache"

# Reuse the scan's extractor rather than duplicating the PowerShell shim.
sys.path.insert(0, str(ROOT / "tools"))
from scan.windows import extract_exe_icon, slugify  # noqa: E402

APP_PATHS_SUBKEYS = [
    ("HKEY_CURRENT_USER", r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
]


def registry_lookup(winreg, name: str) -> Path | None:
    """Mirror lib.rs's windows_registry_lookup, including trying the whole
    value before its first token (registry paths are usually unquoted and
    contain spaces)."""
    exe = name if name.lower().endswith(".exe") else f"{name}.exe"
    for hive_name, subkey in APP_PATHS_SUBKEYS:
        try:
            root = winreg.OpenKey(getattr(winreg, hive_name), subkey)
        except FileNotFoundError:
            continue
        try:
            with winreg.OpenKey(root, exe) as key:
                raw = winreg.QueryValueEx(key, "")[0].strip()
        except FileNotFoundError:
            continue
        unquoted = raw.split('"')[1] if raw.startswith('"') else raw
        for candidate in dict.fromkeys([unquoted, raw.split()[0]]):
            path = Path(candidate)
            if path.is_file():
                return path
    return None


def resolve(winreg, target: str) -> Path | None:
    target = os.path.expandvars(target)  # catalog bins may be %LOCALAPPDATA%-relative
    if "\\" in target or "/" in target:
        path = Path(target)
        return path if path.is_file() else None
    found = shutil.which(target)
    if found:
        return Path(found)
    return registry_lookup(winreg, target)


def main() -> None:
    if sys.platform != "win32":
        print("this script only runs on Windows (needs winreg) — nothing to do here")
        return

    import winreg

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    ICON_CACHE.mkdir(parents=True, exist_ok=True)

    considered = resolved = filled = 0
    for entry in catalog:
        target = entry["bin"].get("windows")
        if not target:
            continue
        if (ICONS_DIR / (entry.get("icon") or "")).exists():
            continue
        considered += 1
        exe = resolve(winreg, target)
        if exe is None:
            continue
        resolved += 1
        staged = ICON_CACHE / f"{slugify(entry['id'])}.png"
        if extract_exe_icon(str(exe), staged):
            filled += 1
            print(f"  {entry['id']:<24} <- {exe}")

    print(f"\nentries missing an icon: {considered}")
    print(f"  resolved on this machine: {resolved}")
    print(f"  icon extracted:          {filled}")
    print("staged into tools/icons/cache/ — run build_catalog.py to place them")


if __name__ == "__main__":
    main()
