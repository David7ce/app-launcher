#!/usr/bin/env python3
"""Merge tools/sources/* into src/data/catalog.json.

One-off maintenance script, not run by the app itself. Safe to re-run: it
regenerates the file from sources each time, so if you've hand-edited
src/data/catalog.json directly, re-running this will overwrite those edits
(that's the tradeoff of a single source-of-truth file — re-sync sources
first, or reapply hand edits after).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "tools" / "sources"
OUT = ROOT / "src" / "data" / "catalog.json"

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


def guess_bin(pkg_manager: dict) -> str | None:
    for field in BIN_FIELD_PRIORITY:
        value = pkg_manager.get(field)
        if value:
            return value
    return None


def category_for(cat_map: dict, category: str, subcategory: str | None) -> str:
    by_sub = cat_map.get("by_subcategory", {})
    if subcategory and subcategory in by_sub:
        return by_sub[subcategory]
    return cat_map["by_category"][category]


def main() -> None:
    desktop_pkgs = json.loads((SOURCES / "desktop-pkgs.json").read_text())["packages"]
    vendor_apps = json.loads((SOURCES / "vendor_apps.json").read_text())["apps"]
    cat_map = json.loads((SOURCES / "category_map.json").read_text())

    catalog: dict[str, dict] = {}
    skipped_no_linux_bin = []

    for app_id, entry in desktop_pkgs.items():
        bin_name = guess_bin(entry.get("package_manager", {}))
        if not bin_name:
            skipped_no_linux_bin.append(app_id)
            continue
        category = category_for(cat_map, entry["category"], entry.get("subcategory"))
        catalog[app_id] = {
            "id": app_id,
            "name": entry["name"],
            "vendor": "",
            "category": category,
            "bin": bin_name,
            "icon": f"{app_id}.png",
            "hidden": False,
        }

    # Hand-curated entries win over dataset-derived ones on id collisions.
    for entry in vendor_apps:
        catalog[entry["id"]] = {
            "id": entry["id"],
            "name": entry["name"],
            "vendor": entry.get("vendor", ""),
            "category": entry["category"],
            "bin": entry["bin"],
            "icon": f"{entry['id']}.png",
            "hidden": False,
        }

    # Two catalog entries that launch the identical binary are the same app
    # to the user, however they got there (dataset vs. hand-curated, or a
    # dataset package-name guess that collides with another one) — keep one.
    by_bin: dict[str, dict] = {}
    dropped_dupes = []
    for entry in sorted(catalog.values(), key=lambda e: e["id"]):
        existing = by_bin.get(entry["bin"])
        if existing is None:
            by_bin[entry["bin"]] = entry
        else:
            dropped_dupes.append((entry["id"], entry["bin"], existing["id"]))

    result = sorted(by_bin.values(), key=lambda e: (e["category"], e["name"].lower()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")

    print(f"wrote {len(result)} entries to {OUT.relative_to(ROOT)}")
    print(f"skipped {len(skipped_no_linux_bin)} dataset entries with no plausible Linux bin "
          f"(flatpak/macOS/Windows-only in the source data)")
    if dropped_dupes:
        print(f"dropped {len(dropped_dupes)} duplicate-bin entries (kept the other id):")
        for dropped_id, bin_name, kept_id in dropped_dupes:
            print(f"  {dropped_id!r} -> bin {bin_name!r} also used by {kept_id!r}")


if __name__ == "__main__":
    main()
