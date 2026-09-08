#!/usr/bin/env python3
"""Windows equivalent of scan_system_apps.py — enumerate installed
programs via the registry's Uninstall keys and write
tools/sources/system_apps_windows.json for build_catalog.py to merge in
(into the `windows` slot of each entry's per-OS `bin` object).

UNVERIFIED — CANNOT BE RUN ON THIS MACHINE AT ALL. This is Fedora/KDE;
`winreg` is a Windows-only stdlib module that doesn't exist on Linux,
so unlike scan_system_apps_macos.py (which could at least be smoke-
tested against a synthetic fixture with pure-Python `plistlib`), there
is no way to exercise this script's logic at all without a real
Windows machine. It has been reviewed carefully but treat it as
unverified Python, not just unverified behavior.

Windows has no equivalent of a `.desktop` file's Categories=, so every
entry defaults to "Utilities" — there's nothing to map from, unlike
Linux (freedesktop Categories=) or macOS (LSApplicationCategoryType).

Registry entries are meant for uninstalling, not launching, so the
executable path is a best-effort extraction from DisplayIcon (usually
"C:\\path\\to\\app.exe" or "C:\\path\\to\\app.exe,0" with a resource-index
suffix) rather than a guaranteed-correct launch command. Entries where
no plausible .exe path can be extracted are skipped rather than
guessed at further.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = ROOT / "src" / "assets" / "icons"
OUT = ROOT / "tools" / "sources" / "system_apps_windows.json"

# (hive, subkey) pairs to enumerate — HKLM's two views (native + WOW6432Node
# for 32-bit apps on 64-bit Windows) plus HKCU for per-user installs.
UNINSTALL_KEYS = [
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKEY_CURRENT_USER", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def extract_exe_path(display_icon: str) -> str | None:
    # DisplayIcon is often "C:\path\app.exe,0" (a resource-index suffix) or
    # occasionally just "C:\path\app.exe". Strip a trailing ",<digits>" and
    # keep only paths that plausibly point at the app's own executable.
    path = display_icon.strip().strip('"')
    if "," in path:
        head, _, tail = path.rpartition(",")
        if tail.lstrip("-").isdigit():
            path = head
    if not path.lower().endswith(".exe"):
        return None
    return path


def read_uninstall_entries():
    import winreg  # Windows-only; deliberately imported here, not at module
    # level, so this file can still be parsed/inspected (though not run)
    # on a non-Windows machine without an ImportError on load.

    for hive_name, subkey in UNINSTALL_KEYS:
        hive = getattr(winreg, hive_name)
        try:
            key = winreg.OpenKey(hive, subkey)
        except FileNotFoundError:
            continue
        with key:
            for i in range(winreg.QueryInfoKey(key)[0]):
                subkey_name = winreg.EnumKey(key, i)
                try:
                    with winreg.OpenKey(key, subkey_name) as entry_key:
                        yield read_entry(winreg, entry_key, subkey_name)
                except OSError:
                    continue


def read_entry(winreg, entry_key, subkey_name: str) -> dict | None:
    def get(name, default=None):
        try:
            return winreg.QueryValueEx(entry_key, name)[0]
        except FileNotFoundError:
            return default

    if get("SystemComponent", 0) == 1:
        return None  # an OS component, not a user-facing app
    name = get("DisplayName")
    display_icon = get("DisplayIcon")
    if not name or not display_icon:
        return None
    bin_path = extract_exe_path(display_icon)
    if not bin_path:
        return None

    icon_path = None
    icon_candidate = display_icon.strip().strip('"')
    if icon_candidate.lower().endswith(".ico") and Path(icon_candidate).is_file():
        icon_path = icon_candidate

    return {
        "id": f"win-{subkey_name.lower().replace(' ', '-')}",
        "name": name,
        "bin": bin_path,
        "category": "Utilities",
        "icon_path": icon_path,
    }


def main() -> None:
    if sys.platform != "win32":
        print("this script only runs on Windows (needs the winreg module) — nothing to do here")
        return

    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    seen_ids = set()
    results = []
    icons_copied = icons_missing = 0

    for entry in read_uninstall_entries():
        if entry is None or entry["id"] in seen_ids:
            continue
        seen_ids.add(entry["id"])
        icon_path = entry.pop("icon_path")
        if icon_path:
            import shutil
            dest = ICONS_DIR / f"{entry['id']}.ico"
            if not dest.exists():
                shutil.copy(icon_path, dest)
            entry["icon"] = dest.name
            icons_copied += 1
        else:
            entry["icon"] = None
            icons_missing += 1
        results.append(entry)

    OUT.write_text(json.dumps(results, indent=2) + "\n")
    print(f"scanned {len(results)} installed programs -> {OUT.relative_to(ROOT)}")
    print(f"icons: {icons_copied} copied (.ico only), {icons_missing} left for the category glyph "
          "(most DisplayIcon values point at an .exe's embedded resource, which this doesn't extract)")


if __name__ == "__main__":
    main()
