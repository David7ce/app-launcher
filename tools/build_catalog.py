#!/usr/bin/env python3
"""Merge tools/sources/* into src/data/catalog.json.

One-off maintenance script, not run by the app itself. Safe to re-run: it
regenerates the file from sources each time, so if you've hand-edited
src/data/catalog.json directly, re-running this will overwrite those edits
(that's the tradeoff of a single source-of-truth file — re-sync sources
first, or reapply hand edits after).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "tools" / "sources"
OUT = ROOT / "src" / "data" / "catalog.json"
ICONS_DIR = ROOT / "src" / "assets" / "icons"


def default_icon(app_id: str) -> str:
    # sync_icons.py may have vendored either a dashboard-icons PNG or an
    # Iconify SVG (or neither yet) — point at whichever actually exists so
    # the frontend's onerror fallback isn't the only thing standing between
    # a real icon and the generic category glyph.
    if (ICONS_DIR / f"{app_id}.svg").exists():
        return f"{app_id}.svg"
    return f"{app_id}.png"

# Preference order for guessing a Linux executable name from the dataset's
# package identifiers. Package name often equals the binary name but not
# always (e.g. Fedora's p7zip package ships a `7z`/`7za` binary) — wrong
# guesses simply fail the is_installed check at runtime and stay hidden,
# they don't crash anything. Fix mismatches by hand-editing catalog.json.
BIN_FIELD_PRIORITY = [
    "linux_fedora_rpm",
    "linux_debian_apt",
    "linux_arch_pacman",
    "linux_snap",
    "linux_arch_aur",
]

# Dataset subcategories that are unambiguously terminal-only tools.
CLI_SUBCATEGORIES = {"CLI Utility", "Compiler"}

# A few well-known CLI-only tools whose dataset subcategory is shared with
# GUI apps (e.g. "System Monitor" also covers GNOME System Monitor), so the
# subcategory heuristic alone would miss them. Extend by hand as needed —
# getting this perfect isn't the point, just keeping obvious CLI tools from
# looking like GUI apps with a broken icon.
CLI_ID_OVERRIDES = {"btop", "htop", "fastfetch", "neofetch", "rsync", "tmux", "tree", "curl"}

# Dataset-derived entries whose default `<id>.png` icon guess is wrong —
# e.g. a real icon sourced from KDE's breeze-icons repo instead (SVG, no
# branded PNG exists anywhere). Same idea as vendor_apps.json's per-entry
# `icon` override, but for entries that come from the dataset, not
# hand-written ones.
ICON_OVERRIDES = {
    "gwenview": "gwenview.svg",
    "elisa": "elisa.svg",
}


# Apps worth getting a confidently-correct cross-OS bin for, by hand,
# rather than trusting the low-confidence heuristics below. Unverified on
# real Windows/macOS hardware — these are just the names those platforms
# are known to use.
BIN_OVERRIDES: dict[str, dict[str, str]] = {
    "visual-studio-code": {"windows": "Code.exe", "macos": "Visual Studio Code"},
    "firefox": {"windows": "firefox.exe", "macos": "Firefox"},
}


def guess_bin(pkg_manager: dict) -> str | None:
    for field in BIN_FIELD_PRIORITY:
        value = pkg_manager.get(field)
        if value:
            return value
    return None


def guess_windows_bin(pkg_manager: dict, linux_bin: str) -> str | None:
    # Low-confidence heuristic: plenty of CLI/dev tools ship an identically
    # named binary on Windows (git, python, node, ...); plenty of GUI apps
    # don't. No worse than the Linux package-name guess above — wrong
    # guesses just fail `is_installed` silently. Unverified on real Windows.
    if pkg_manager.get("windows_winget"):
        return linux_bin
    return None


def guess_macos_bin(pkg_manager: dict) -> str | None:
    # Low-confidence heuristic: title-case the Homebrew slug as a guess at
    # the .app bundle's display name (`open -a` needs, e.g., "Visual Studio
    # Code", not "visual-studio-code"). Wrong for acronyms ("vlc" -> "Vlc"
    # instead of "VLC") and anything Homebrew names differently from the
    # app itself. Unverified on real macOS — hand-fix via BIN_OVERRIDES.
    brew = pkg_manager.get("macos_brew")
    if not brew:
        return None
    words = re.split(r"[-_]", brew)
    return " ".join(w.capitalize() for w in words if w)


def build_bin(pkg_manager: dict, linux_bin: str, app_id: str) -> dict[str, str]:
    bin_obj = {"linux": linux_bin}
    windows = guess_windows_bin(pkg_manager, linux_bin)
    if windows:
        bin_obj["windows"] = windows
    macos = guess_macos_bin(pkg_manager)
    if macos:
        bin_obj["macos"] = macos
    bin_obj.update(BIN_OVERRIDES.get(app_id, {}))
    return bin_obj


def dedupe_key(entry: dict) -> str | None:
    # Linux first: it's the one platform this app actually runs and gets
    # tested on. Falling back to windows/macos still catches a collision
    # between two placeholder entries that share a bin on the same OS.
    bin_obj = entry["bin"]
    return bin_obj.get("linux") or bin_obj.get("windows") or bin_obj.get("macos")


def is_cli(app_id: str, subcategory: str | None) -> bool:
    return subcategory in CLI_SUBCATEGORIES or app_id in CLI_ID_OVERRIDES


def category_for(cat_map: dict, category: str, subcategory: str | None) -> str:
    by_sub = cat_map.get("by_subcategory", {})
    if subcategory and subcategory in by_sub:
        return by_sub[subcategory]
    return cat_map["by_category"][category]


# Ids hidden from the final catalog regardless of which source they came
# from: this machine's own app-launcher shortcut (self-referential, shows
# up in the system scan since it drops a .desktop file too), near-duplicate
# entries for something already covered by a more useful one (extra KDE
# Connect variants, a second address-book style bin), obscure single-purpose
# sub-editors bundled with the Kontact/KMail suite that clutter without
# being an "important" app on their own, and a crash-reporter applet.
# Extend by hand as more low-value clutter turns up in a system scan.
EXCLUDED_IDS = {
    "app-launcher",
    "kde-connect",  # dataset-derived dupe of org.kde.kdeconnect.app, wrong bin anyway
    "org.kde.kdeconnect.nonplasma",  # KDE Connect Indicator — same app as KDE Connect
    "org.kde.kdeconnect.sms",  # KDE Connect SMS — same app as KDE Connect
    "org.kde.kwrite",  # Kate covers this
    "org.kde.contactprintthemeeditor",
    "org.kde.contactthemeeditor",
    "org.kde.headerthemeeditor",
    "org.kde.sieveeditor",
    "org.kde.akonadiimportwizard",
    "org.freedesktop.GnomeAbrt",  # "Problem Reporting" crash applet, not a real app
    "org.kde.drkonqi.coredump.gui",  # "Crashed Processes Viewer" — same idea, KDE's version
    "org.kde.plasma-welcome",  # "Welcome Center" — first-run onboarding screen, not an app
    "org.kde.kdebugsettings",  # dev-only debug-logging config, not a user app
    "org.kde.kjournaldbrowser",  # systemd journal log viewer, sysadmin meta tool
    "org.kde.kmenuedit",  # editor for the start menu this launcher replaces
    "im-chooser",  # input-method setup wizard, onboarding-ish system config
    "setroubleshoot",  # SELinux diagnostic tool, same spirit as the crash reporters above
}


def main() -> None:
    desktop_pkgs = json.loads((SOURCES / "desktop-pkgs.json").read_text())["packages"]
    vendor_apps = json.loads((SOURCES / "vendor_apps.json").read_text())["apps"]
    cat_map = json.loads((SOURCES / "category_map.json").read_text())
    system_apps_path = SOURCES / "system_apps.json"
    system_apps = json.loads(system_apps_path.read_text()) if system_apps_path.exists() else []

    catalog: dict[str, dict] = {}
    skipped_no_linux_bin = []

    for app_id, entry in desktop_pkgs.items():
        pkg_manager = entry.get("package_manager", {})
        bin_name = guess_bin(pkg_manager)
        if not bin_name:
            skipped_no_linux_bin.append(app_id)
            continue
        category = category_for(cat_map, entry["category"], entry.get("subcategory"))
        catalog[app_id] = {
            "id": app_id,
            "name": entry["name"],
            "vendor": "",
            "category": category,
            "bin": build_bin(pkg_manager, bin_name, app_id),
            "icon": ICON_OVERRIDES.get(app_id, default_icon(app_id)),
            "hidden": False,
            "cli": is_cli(app_id, entry.get("subcategory")),
        }

    # Hand-curated entries win over dataset-derived ones on id collisions.
    # vendor_apps.json entries already carry `bin` as a per-OS object.
    for entry in vendor_apps:
        catalog[entry["id"]] = {
            "id": entry["id"],
            "name": entry["name"],
            "vendor": entry.get("vendor", ""),
            "category": entry["category"],
            "bin": entry["bin"],
            "icon": entry.get("icon", default_icon(entry["id"])),
            "hidden": False,
            "cli": entry.get("cli", False),
        }

    # Two catalog entries that launch the identical binary are the same app
    # to the user, however they got there (dataset vs. hand-curated, or a
    # dataset package-name guess that collides with another one) — keep one.
    by_bin: dict[str, dict] = {}
    dropped_dupes = []
    for entry in sorted(catalog.values(), key=lambda e: e["id"]):
        key = dedupe_key(entry)
        existing = by_bin.get(key)
        if existing is None:
            by_bin[key] = entry
        else:
            dropped_dupes.append((entry["id"], key, existing["id"]))

    # This machine's actual installed .desktop files are ground truth: a
    # real name, a real system-theme icon, and a bin taken straight from
    # Exec= rather than guessed from a package name. They always win over
    # a dataset/vendor entry for the same bin, and add anything new.
    # scan_system_apps.py only ever scans this Linux machine, so its `bin`
    # is a flat string — merge it into the Linux slot of whatever per-OS
    # object already existed for this bin (rather than replacing the whole
    # object), so a dataset/vendor entry's windows/macos guess isn't lost
    # just because the Linux side also happens to be locally installed.
    new_from_system = 0
    for entry in system_apps:
        if entry["id"] in EXCLUDED_IDS:
            continue
        key = entry["bin"]
        existing = by_bin.get(key)
        if existing is None:
            new_from_system += 1
        bin_obj = dict(existing["bin"]) if existing else {}
        bin_obj["linux"] = entry["bin"]
        by_bin[key] = {
            "id": entry["id"],
            "name": entry["name"],
            "vendor": "",
            "category": entry["category"],
            "bin": bin_obj,
            "icon": entry["icon"] or f"{entry['id']}.png",
            "hidden": False,
            "cli": False,
        }

    result = sorted(
        (e for e in by_bin.values() if e["id"] not in EXCLUDED_IDS),
        key=lambda e: (e["category"], e["name"].lower()),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")

    print(f"wrote {len(result)} entries to {OUT.relative_to(ROOT)}")
    print(f"skipped {len(skipped_no_linux_bin)} dataset entries with no plausible Linux bin "
          f"(flatpak/macOS/Windows-only in the source data)")
    if dropped_dupes:
        print(f"dropped {len(dropped_dupes)} duplicate-bin entries (kept the other id):")
        for dropped_id, bin_name, kept_id in dropped_dupes:
            print(f"  {dropped_id!r} -> bin {bin_name!r} also used by {kept_id!r}")
    if system_apps:
        print(f"merged {len(system_apps)} locally-scanned apps ({new_from_system} new, "
              f"the rest replaced a dataset/vendor guess with the real local name+icon)")


if __name__ == "__main__":
    main()
