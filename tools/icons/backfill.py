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
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG = ROOT / "src" / "data" / "catalog.json"
ICONS_DIR = ROOT / "src" / "assets" / "icons"
ICON_CACHE = ROOT / "tools" / "icons" / "cache"

# Reuse the scan's extractor rather than duplicating the PowerShell shim.
sys.path.insert(0, str(ROOT / "tools"))
from scan.windows import (  # noqa: E402
    extract_appx_icon,
    extract_exe_icon,
    extract_start_icon,
    slugify,
)

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


# ---- Start Menu lookup: the same matching the running app does (lib.rs) ----------

# Classic Start entries are `{KnownFolderGUID}\relative\app.exe`; the GUIDs that
# matter map to environment variables.
KNOWN_FOLDERS = {
    "{6D809377-6AF0-444B-8957-A3773F02200E}": "%ProgramW6432%",
    "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}": "%ProgramFiles(x86)%",
    "{905E63B6-C1BF-494E-B29C-65B732D3D21A}": "%ProgramFiles%",
    "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}": "%LOCALAPPDATA%",
}
_NOISE = {"x64", "x86", "64bit", "32bit", "64-bit", "32-bit", "microsoft", "oracle", "the", "desktop", "windows"}


def norm_app_name(name: str) -> str:
    """Comparison key for a catalog name against a Start Menu one — a port of
    `norm_app_name` in lib.rs, so this build-time lookup finds the same entry the
    running app will: drop `(...)`, filler words and trailing version numbers."""
    flat = re.sub(r"\([^)]*\)", " ", name.replace("+", "plus")).lower()
    tokens = [t for t in flat.split() if t not in _NOISE]

    def is_version(t: str) -> bool:
        t = t[1:] if t.startswith("v") else t
        return any(c.isdigit() for c in t) and all(c.isdigit() or c == "." for c in t)

    while len(tokens) > 1 and is_version(tokens[-1]):
        tokens.pop()
    return re.sub(r"[^a-z0-9]", "", "".join(tokens))


def expand_start_app_id(app_id: str) -> str:
    r"""`{6D809377-...}\Foo\foo.exe` -> `%ProgramW6432%\Foo\foo.exe`; anything else unchanged."""
    for guid, var in KNOWN_FOLDERS.items():
        if app_id.upper().startswith(guid):
            return var + app_id[len(guid):]
    return app_id


def start_apps() -> dict[str, str]:
    """{normalized name: AppID} for everything in the Start Menu (first one wins)."""
    import subprocess

    out = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
         "ConvertTo-Json -InputObject @(Get-StartApps | Select-Object Name,AppID) -Compress"],
        capture_output=True, timeout=120,
    ).stdout.decode("utf-8", "replace").lstrip("﻿")
    apps: dict[str, str] = {}
    for item in json.loads(out or "[]"):
        apps.setdefault(norm_app_name(item["Name"]), item["AppID"])
    return apps


def extract_from_start_menu(apps: dict[str, str], name: str, dest: Path) -> str | None:
    """Extract an icon for a Start Menu entry: the exe named by a classic AppID,
    else a packaged app's manifest logo, else the shell's own tile. Returns which."""
    app_id = apps.get(norm_app_name(name))
    if not app_id:
        return None
    exe = Path(os.path.expandvars(expand_start_app_id(app_id)))
    if exe.is_absolute() and exe.is_file() and extract_exe_icon(str(exe), dest):
        return "exe"
    if "!" in app_id and extract_appx_icon(app_id, dest):
        return "package"
    if extract_start_icon(app_id, dest):
        return "shell tile"
    return None


def main() -> None:
    if sys.platform != "win32":
        print("this script only runs on Windows (needs winreg) — nothing to do here")
        return

    import winreg

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    ICON_CACHE.mkdir(parents=True, exist_ok=True)

    apps = start_apps()
    considered = resolved = filled = 0
    for entry in catalog:
        target = entry["bin"].get("windows")
        if target is None:  # not a Windows app
            continue
        if (ICONS_DIR / (entry.get("icon") or "")).exists():
            continue
        considered += 1
        staged = ICON_CACHE / f"{slugify(entry['id'])}.png"
        # 1. an executable we can resolve (PATH, App Paths, an absolute path)
        exe = resolve(winreg, target) if target and not target.startswith("start:") else None
        if exe is not None:
            resolved += 1
            if extract_exe_icon(str(exe), staged):
                filled += 1
                print(f"  {entry['id']:<26} <- {exe}")
                continue
        # 2. the Start Menu: `start:<name>` or the catalog name (an empty slot)
        start_name = target[len("start:"):] if target.startswith("start:") else entry["name"]
        how = extract_from_start_menu(apps, start_name, staged)
        if how:
            resolved += exe is None
            filled += 1
            print(f"  {entry['id']:<26} <- Start Menu ({how})")

    print(f"\nentries missing an icon: {considered}")
    print(f"  resolved on this machine: {resolved}")
    print(f"  icon extracted:          {filled}")
    print("staged into tools/icons/cache/ — run build_catalog.py to place them")


if __name__ == "__main__":
    main()
