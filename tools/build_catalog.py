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
# Icons extracted by a system scan are staged here by the scan script (which
# doesn't know an app's final catalog id), then copied into ICONS_DIR under
# the id that actually references them — see `place_scan_icons`.
ICON_CACHE = ROOT / "tools" / "icon_cache"


def default_icon(app_id: str) -> str:
    # Every icon source (dashboard-icons, Iconify, the system-theme scan,
    # the generated category/CLI glyphs) is normalized to PNG at vendoring
    # time — see "Icon format" in SPEC.md — so this is just the naming
    # convention, not a check against what's actually on disk.
    return f"{app_id}.png"


# Normalizes a display name to a comparison key: lowercase, alphanumerics
# only. Used to join a Windows-scanned app ("Microsoft Visual Studio Code
# (User)") to its curated entry ("Visual Studio Code"). Strips the same
# vendor/edition noise the scan's clean_name() removes, so the two sides
# actually meet: without dropping "microsoft", "visualstudiocodeuser" never
# matches "visualstudiocode".
_NAME_NOISE_RE = re.compile(
    r"\b(microsoft|mozilla|the|inc|llc|ltd|corporation|corp|user|"
    r"community|preview|desktop|client|app|application|x64|x86|64bit|32bit)\b"
    r"|\b[a-z]{2}[-_][a-z]{2,4}\b"  # locale tags: "en-US", "pt_BR"
)
# A trailing 4-digit year, e.g. "Visual Studio Community 2022" -> "Visual
# Studio". Anchored to the end and requiring a preceding space, so a name
# that *is* a number ("2048") is left intact.
_TRAILING_YEAR_RE = re.compile(r"\s+(?:19|20)\d{2}\s*$")


def normalize_name(name: str) -> str:
    lowered = _TRAILING_YEAR_RE.sub("", name.lower())
    stripped = _NAME_NOISE_RE.sub(" ", lowered)
    key = re.sub(r"[^a-z0-9]", "", stripped)
    # "Responsively App" loses its " app" word above, but "ResponsivelyApp" is
    # one word — so drop a glued-on trailing "app" too. Guarded by length so a
    # short name that merely ends in "app" is left alone.
    if key.endswith("app") and len(key) > 8:
        key = key[:-3]
    return key

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
#
# The test is "does clicking it show anything": a tool that prints usage and
# exits (git, bun, pandoc, nmap) or has no window at all needs the terminal
# wrapper, while GUI apps that merely happen to be console-subsystem exes
# (darktable, scrcpy, UltraStar) must NOT be listed — a PE-header check would
# misfile those, so this stays a hand-kept list. Interactive shells that already
# open fine on their own (PowerShell, mitmproxy) are left out.
CLI_ID_OVERRIDES = {
    "btop", "htop", "fastfetch", "neofetch", "rsync", "tmux", "tree", "curl",
    "ansible", "borg", "claude-code", "codex", "deno", "distrobox", "docker",
    "ffmpeg", "git", "go", "hugo", "imagemagick", "instaloader", "jj", "k9s",
    "kubectl", "lazygit", "llama-cpp", "nmap", "nodejs", "opencode", "pandoc",
    "podman", "python", "rclone", "sqlite", "starship", "terraform", "vagrant",
    "yt-dlp",
    "win-bun", "win-tesseract-ocr",  # scan-created ids (no dataset entry)
}

# Dataset-derived entries whose default `<id>.png` icon guess is wrong —
# e.g. a real icon sourced from KDE's breeze-icons repo instead (SVG, no
# branded PNG exists anywhere). Same idea as vendor_apps.json's per-entry
# `icon` override, but for entries that come from the dataset, not
# hand-written ones.
ICON_OVERRIDES = {
    "gwenview": "gwenview.png",
    "elisa": "elisa.png",
}


# Apps worth getting a confidently-correct cross-OS bin for, by hand,
# rather than trusting the low-confidence heuristics below. Unverified on
# real Windows/macOS hardware — these are just the names those platforms
# are known to use.
BIN_OVERRIDES: dict[str, dict[str, str]] = {
    "visual-studio-code": {"windows": "Code.exe", "macos": "Visual Studio Code"},
    "firefox": {"windows": "firefox.exe", "macos": "Firefox"},
    # Linux says python3, but on Windows `python3.exe` is usually the Microsoft
    # Store *stub* in WindowsApps (present even when Python isn't installed);
    # the real interpreter is python.exe.
    "python": {"windows": "python.exe"},
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
    # don't. Unverified on real Windows.
    #
    # Guard against the worst failure mode: the Linux bin is often a *package
    # id*, not a binary name (`dbeaver-ce`, `github-desktop-bin`,
    # `intellij-idea-community-edition`, `dotnet-runtime-6.0`). Emitting those
    # as Windows bins produces entries that can never resolve, so the tile
    # silently never appears. Only guess when the name is a plausible bare
    # executable: no hyphens, no version-ish dots, no path separators. A
    # missing guess is strictly better than a wrong one. But the app *does*
    # exist on Windows (it has a winget id), so the slot is present with an
    # empty value rather than absent: `lib.rs` then resolves it by display name
    # against the Start Menu, which is how apps that install outside $PATH and
    # App Paths (Discord, LibreOffice, KeePassXC, ...) are found. An absent
    # key still means "not on Windows", so unrelated Linux apps that merely
    # share a name with a Windows one (KDE Dolphin vs the emulator) stay hidden.
    if not pkg_manager.get("windows_winget"):
        return None
    if re.fullmatch(r"[A-Za-z0-9_]+", linux_bin):
        return f"{linux_bin}.exe"
    return ""


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
    if windows is not None:  # "" is meaningful: on Windows, exe unknown
        bin_obj["windows"] = windows
    macos = guess_macos_bin(pkg_manager)
    if macos:
        bin_obj["macos"] = macos
    bin_obj.update(BIN_OVERRIDES.get(app_id, {}))
    return bin_obj


def load_json_list(path: Path) -> list[dict]:
    return json.loads(path.read_text()) if path.exists() else []


def merge_system_scan(by_bin: dict[str, dict], entries: list[dict], os_key: str) -> int:
    # Shared by all three system scans (Linux/Windows/macOS): a locally-
    # scanned entry is ground truth for its OS, so it wins the name/icon/
    # category for that bin — but it only overwrites its *own* slot in the
    # per-OS `bin` object, preserving whatever the dataset/vendor guess had
    # for the other two OSes (see the Firefox/VS Code bug this fixed for
    # the Linux scan — same fix applies here by construction, not by luck).
    #
    # Windows needs a different match key: the Linux/macOS scans emit a bare
    # command name (which is what `by_bin` is keyed on), but the Windows scan
    # emits a full path (`C:\Program Files\7-Zip\7zFM.exe`) because that's
    # what the registry stores. Keying on the raw path would never match an
    # existing entry, so every scanned app would land as a brand-new
    # GUID-named duplicate instead of upgrading the real entry. Match on the
    # exe's basename against existing `bin.windows` values instead.
    if os_key == "windows":
        by_windows_bin = {
            e["bin"]["windows"].lower(): e
            for e in by_bin.values()
            if e["bin"].get("windows")
        }
        # Matching on the exe basename alone misses most apps: a curated
        # entry only has a `bin.windows` when the dataset happened to list a
        # winget id *and* the name looked like a bare executable, so the
        # common case is no Windows bin at all. Without a second key, every
        # scanned app became a brand-new entry carrying the scan's hardcoded
        # "Utilities" category — which put GIMP, Steam, Spotify, OBS and
        # Android Studio all in Utilities. The app's display name is the
        # reliable join: 64 of 68 scanned apps matched a curated entry by
        # normalized name, versus 0 by basename.
        by_windows_name = {
            normalize_name(e["name"]): e for e in by_bin.values()
        }
    new_count = 0
    for entry in entries:
        if entry["id"] in EXCLUDED_IDS:
            continue
        if os_key == "windows":
            basename = entry["bin"].replace("/", "\\").rsplit("\\", 1)[-1].lower()
            existing = by_windows_bin.get(basename) or by_windows_name.get(
                normalize_name(entry["name"])
            )
            key = existing["id"] if existing else entry["bin"]
        else:
            key = entry["bin"]
            existing = by_bin.get(key)
        if existing is None:
            new_count += 1
        bin_obj = dict(existing["bin"]) if existing else {}
        bin_obj[os_key] = entry["bin"]
        # A positive cli classification from *either* source wins — don't
        # let a system scan with no Terminal=/cli signal of its own (the
        # Windows/macOS scans don't set one at all) silently clobber a
        # dataset/vendor entry's correct cli:true (this was a real bug:
        # btop is explicitly CLI_ID_OVERRIDES'd but also has a local
        # .desktop file, so the scan was unconditionally resetting it to
        # cli:false, defeating the terminal-launch wrapping entirely).
        cli = entry.get("cli", False) or (existing["cli"] if existing else False)
        if existing is not None:
            # Matched an existing curated entry: the scan's only real
            # contribution is the authoritative launch path. Its name
            # ("7-Zip 26.03 (x64)") and category (always "Utilities", since
            # the registry has no category concept) are both worse than the
            # curated ones, so keep the existing entry and just take the bin.
            existing["bin"] = bin_obj
            existing["cli"] = cli
            # The curated `icon` field is a naming convention, not a check —
            # plenty of dataset entries reference a `<id>.png` that was never
            # actually vendored, which renders as a placeholder. The scan
            # extracted a real icon from the exe's own resources, so prefer
            # it whenever the curated file isn't actually on disk.
            scan_icon = entry.get("icon_source")
            if scan_icon and not (ICONS_DIR / (existing.get("icon") or "")).exists():
                existing["_scan_icon"] = scan_icon
            continue
        new_entry = {
            "id": entry["id"],
            "name": entry["name"],
            "vendor": "",
            "category": entry["category"],
            "bin": bin_obj,
            "icon": f"{entry['id']}.png",
            "hidden": False,
            "cli": cli,
        }
        # A staged icon is applied by `place_scan_icons` under the final
        # `<id>.png` name, same as for a matched entry.
        if entry.get("icon_source"):
            new_entry["_scan_icon"] = entry["icon_source"]
        by_bin[key] = new_entry
    return new_count


def place_scan_icons(entries: list[dict]) -> tuple[int, int]:
    """Copy scan-staged icons into ICONS_DIR as `<catalog-id>.png`, and
    delete any icon file no longer referenced by the catalog.

    Keeps `src/assets/icons/` self-consistent: every file is named after the
    id that uses it, and nothing is left behind. Before this, the Windows
    scan named files after the *registry* display name, so a file like
    `win-microsoft-visual-studio-code-user.png` was referenced by the entry
    `visual-studio-code` — nothing linked the two but the JSON — and every
    app the catalog later dropped left an orphan behind (62 of them, 1.4 MB).
    """
    import shutil

    def slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "app"

    placed = 0
    for entry in entries:
        staged = entry.pop("_scan_icon", None)
        # A scan only supplies icons for apps it discovered itself. Anything
        # that resolved some other way — e.g. an Office app found via the
        # registry's App Paths key rather than the Uninstall keys — has no
        # staged icon from that path, but `backfill_icons.py` may have put one
        # in the cache keyed by the entry's own id. Use it when the entry
        # still has no icon file on disk.
        if not staged and not (ICONS_DIR / f"{entry['id']}.png").exists():
            candidate = ICON_CACHE / f"{slugify(entry['id'])}.png"
            if candidate.exists():
                staged = candidate.name
        if not staged:
            continue
        src = ICON_CACHE / staged
        if not src.exists():
            continue
        dest = ICONS_DIR / f"{entry['id']}.png"
        entry["icon"] = dest.name
        shutil.copy(src, dest)
        placed += 1

    referenced = {e["icon"] for e in entries if e.get("icon")}
    pruned = 0
    # Only top-level files: category/ holds the fallback glyphs, which are
    # referenced by convention (`category/<Category>.png`) rather than from
    # any catalog entry's `icon` field.
    for path in ICONS_DIR.glob("*"):
        if path.is_file() and path.name not in referenced:
            path.unlink()
            pruned += 1
    return placed, pruned


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
    "org.kde.pimdataexporter",  # Kontact's export sub-tool, same icon/app as Kontact itself
    "org.freedesktop.GnomeAbrt",  # "Problem Reporting" crash applet, not a real app
    "org.kde.drkonqi.coredump.gui",  # "Crashed Processes Viewer" — same idea, KDE's version
    "org.kde.plasma-welcome",  # "Welcome Center" — first-run onboarding screen, not an app
    "org.kde.kdebugsettings",  # dev-only debug-logging config, not a user app
    "org.kde.kjournaldbrowser",  # systemd journal log viewer, sysadmin meta tool
    "org.kde.kmenuedit",  # editor for the start menu this launcher replaces
    "win-thermaltake-tool",  # vendor RGB utility, uninstalled from the dev machine
    # UltraStar is one program: the game (UltraStar Deluxe) plus two companion
    # editors it installs as separate entries. One tile is enough, same call as
    # the Kontact/KMail sub-tools above.
    "win-ultrastar-creator",
    "win-ultrastar-manager",
    "im-chooser",  # input-method setup wizard, onboarding-ish system config
    "setroubleshoot",  # SELinux diagnostic tool, same spirit as the crash reporters above
}


def main() -> None:
    desktop_pkgs = json.loads((SOURCES / "desktop-pkgs.json").read_text())["packages"]
    vendor_apps = json.loads((SOURCES / "vendor_apps.json").read_text())["apps"]
    cat_map = json.loads((SOURCES / "category_map.json").read_text())
    system_apps = load_json_list(SOURCES / "system_apps.json")
    system_apps_windows = load_json_list(SOURCES / "system_apps_windows.json")
    system_apps_macos = load_json_list(SOURCES / "system_apps_macos.json")

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

    # Each machine's actual installed apps are ground truth: a real name,
    # a real system-theme icon, and a bin taken straight from the OS's own
    # records rather than guessed from a package name. They always win over
    # a dataset/vendor entry for the same bin, and add anything new. Only
    # the scan matching the machine that generated these files will ever
    # be non-empty for a given run (e.g. system_apps.json is always empty
    # on a Windows machine, system_apps_windows.json always empty here).
    new_from_system = merge_system_scan(by_bin, system_apps, "linux")
    new_from_system += merge_system_scan(by_bin, system_apps_windows, "windows")
    new_from_system += merge_system_scan(by_bin, system_apps_macos, "macos")

    result = sorted(
        (e for e in by_bin.values() if e["id"] not in EXCLUDED_IDS),
        key=lambda e: (e["category"], e["name"].lower()),
    )
    # Scan-created entries never pass through is_cli(), so apply the curated
    # list to the final result rather than only to dataset entries.
    for entry in result:
        if entry["id"] in CLI_ID_OVERRIDES:
            entry["cli"] = True
    icons_placed, icons_pruned = place_scan_icons(result)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")

    print(f"wrote {len(result)} entries to {OUT.relative_to(ROOT)}")
    print(f"icons: {icons_placed} placed as <id>.png, {icons_pruned} orphaned file(s) pruned")
    print(f"skipped {len(skipped_no_linux_bin)} dataset entries with no plausible Linux bin "
          f"(flatpak/macOS/Windows-only in the source data)")
    if dropped_dupes:
        print(f"dropped {len(dropped_dupes)} duplicate-bin entries (kept the other id):")
        for dropped_id, bin_name, kept_id in dropped_dupes:
            print(f"  {dropped_id!r} -> bin {bin_name!r} also used by {kept_id!r}")
    total_system_apps = len(system_apps) + len(system_apps_windows) + len(system_apps_macos)
    if total_system_apps:
        print(f"merged {total_system_apps} locally-scanned apps ({new_from_system} new, "
              f"the rest replaced a dataset/vendor guess with the real local name+icon)")


if __name__ == "__main__":
    main()
