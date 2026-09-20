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
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = ROOT / "src" / "assets" / "icons"
OUT = ROOT / "tools" / "sources" / "system_apps_windows.json"

# Registry Uninstall entries include a lot that isn't a launchable app:
# runtimes, redistributables, drivers, and update packages all register
# themselves the same way a real program does. `SystemComponent=1` catches
# some of them, but plenty (notably the .NET/ASP.NET runtimes) don't set it,
# so filter by name pattern too. Verified against a real scan on Windows:
# without this, the catalog gained entries like "Microsoft .NET Runtime -
# 10.0.12 (x64)" and "Windows Driver Package - Silicon Laboratories ...".
NON_APP_NAME_PATTERNS = [
    r"^Microsoft \.NET Runtime",
    r"^Microsoft ASP\.NET Core",
    r"^Microsoft Windows Desktop Runtime",
    r"^Windows Driver Package",
    r"^Update for ",
    r"^Security Update",
    r"^Hotfix for ",
    r"Redistributable",  # VC++/DirectX/etc. — installed as a dependency, never launched
    r"^Microsoft Edge WebView2 Runtime",
    r"^Microsoft Edge Update",
    r"^Microsoft Visual Studio Installer",
    r"Maintenance Service$",  # background updater service, not an app
    r"^Python \d.*(Launcher|Core|Development|Documentation|Test Suite|Executables|Standard Library)",
    r"^Node\.js$",
    r"^Git version ",
    r"^Denuvo Anti-Cheat$",
    r"^Bonjour$",
    r"^Microsoft Update Health Tools$",
]

# Trailing version strings the registry appends to DisplayName, e.g.
# "Heroic 2.22.0", "darktable 5.6.1", "Koodo Reader 2.4.4", "7-Zip 26.03 (x64)".
# Requires either a `v` prefix or a dotted version, so a bare year that's part
# of the product name ("Microsoft Office Home 2024") is left alone.
VERSION_SUFFIX_RE = re.compile(
    r"\s+(?:v\.?\s*\d[\w.]*|\d+\.\d[\w.]*)\s*$",
    re.IGNORECASE,
)

# Other registry-only noise appended to DisplayName, all seen in a real scan:
#   "Notepad++ (64-bit x64)"              -> "Notepad++"
#   "PowerToys (Preview) x64"             -> "PowerToys (Preview)"
#   "Golden Cheetah v3.8 (64bit)"         -> "Golden Cheetah v3.8"
#   "MyTourbook with Java Runtime 26.3.0" -> "MyTourbook"
#   "Microsoft Office Home 2024 - en-us"  -> "Microsoft Office Home 2024"
#   "PlayTorrioMov version 1.2"           -> "PlayTorrioMov"
ARCH_SUFFIX_RE = re.compile(
    r"\s*\((?:x64|x86|64-bit|32-bit|64bit|32bit)(?:\s+\w+)?\)\s*$|\s+(?:x64|x86|64bit|32bit)\s*$",
    re.IGNORECASE,
)
BUNDLED_RUNTIME_RE = re.compile(r"\s+with (?:Java|Python|\.NET) Runtime.*$", re.IGNORECASE)
LOCALE_SUFFIX_RE = re.compile(r"\s+-\s+[a-z]{2}(?:-[A-Za-z]{2,4})?\s*$")
LOOSE_VERSION_RE = re.compile(r"\s+v\.?\s*[A-Z]?\d[\w.]*\s*$", re.IGNORECASE)
BARE_VERSION_WORD_RE = re.compile(r"\s+version\s*$", re.IGNORECASE)


def clean_name(name: str) -> str:
    cleaned = name
    # Order matters: strip the parenthesised/bare architecture suffix *first*,
    # otherwise it sits between the version and the end of the string and the
    # `$`-anchored version patterns never match ("Golden Cheetah v3.8 (64bit)"
    # would keep its version).
    for pattern in (
        BUNDLED_RUNTIME_RE,
        LOCALE_SUFFIX_RE,
        ARCH_SUFFIX_RE,
        VERSION_SUFFIX_RE,
        LOOSE_VERSION_RE,
        BARE_VERSION_WORD_RE,
    ):
        cleaned = pattern.sub("", cleaned)
    return cleaned.strip() or name


def is_non_app(name: str) -> bool:
    return any(re.search(pattern, name, re.IGNORECASE) for pattern in NON_APP_NAME_PATTERNS)


def slugify(name: str) -> str:
    # A readable id derived from the app's name, rather than the registry
    # key — which is frequently a GUID or an Inno Setup `..._is1` suffix
    # (e.g. "win-{c7054d61-...}" or "win-darktable_is1"). Falls back to the
    # raw key only if the name slugifies to nothing.
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "app"


# The registry has no category concept, so a scanned app needs one inferred.
# Without this every added app landed in "Utilities" — which put Android
# Studio, Bun, CapCut, Eagle and AdGuard there. Rules are checked in order
# and the first match wins, so put the specific before the general.
# Deliberately conservative: a wrong guess is visible but harmless, and any
# app that also matches a curated entry never reaches this (the curated
# category wins in build_catalog.py).
CATEGORY_KEYWORDS = [
    (r"\b(android studio|visual studio|intellij|pycharm|webstorm|eclipse|unity|"
     r"unreal|godot|jetbrains|sublime|notepad\+\+|vim|emacs|zed|"
     r"python|node|bun|deno|dotnet|\.net|jdk|java|golang|rust|git|"
     r"docker|postman|insomnia|dbeaver|pgadmin|laragon|xampp|wamp|"
     r"tesseract|source sdk|responsively)\b", "Development"),
    (r"\b(gimp|photoshop|illustrator|inkscape|krita|blender|darktable|digikam|"
     r"eagle|upscayl|rapidraw|affinity|kdenlive|openshot|shotcut|figma|"
     r"canva|paint|screenshot|sharex|flameshot|greenshot|screenpresso)\b", "Graphics"),
    (r"\b(obs|capcut|handbrake|vlc|mpc-hc|kodi|stremio|iptv|audacity|"
     r"spotify|itunes|musicbee|foobar|davinci|premiere|wave|youtube|"
     r"balabolka|ivona|voice|media player|plex|jellyfin|playtorrio)\w*\b", "Multimedia"),
    (r"\b(steam|heroic|lutris|retroarch|pcsx2|ppsspp|dolphin|duckstation|"
     r"melonds|xemu|emulator|chess|epic games|gog|battle\.net|ubisoft|"
     r"minecraft|xbox|ultrastar)\b", "Games"),
    (r"\b(adguard|mullvad|wireshark|npcap|firewall|antivirus|defender|"
     r"bitdefender|kaspersky|nordvpn|proton|avast|avira|malwarebytes|"
     r"winmerge|sysinternals|process explorer)\b", "System"),
    (r"\b(firefox|chrome|chromium|edge|brave|opera|vivaldi|safari|"
     r"telegram|whatsapp|discord|slack|signal|thunderbird|outlook|"
     r"zoom|teams|skype|thunder|responsively)\b", "Internet"),
    (r"\b(office|word|excel|powerpoint|onenote|libreoffice|onlyoffice|"
     r"kindle|calibre|koodo|obsidian|notion|evernote|sumatrapdf|"
     r"adobe acrobat|foxit|pdf|gramps|mendeley|zotero|wps)\b", "Office"),
    (r"\b(geogebra|qgis|google earth|stellarium|kstars|matlab|mathematica|"
     r"octave|scilab|gis|astronom)\b", "Science"),
    (r"\b(anki|duolingo|calibre|gramps|dictionary|reference)\b", "Education"),
]


def guess_category(name: str) -> str:
    for pattern, category in CATEGORY_KEYWORDS:
        if re.search(pattern, name, re.IGNORECASE):
            return category
    return "Utilities"


# PowerShell script that pulls an executable's own icon out of its embedded
# resources. Pure-Python is not an option here: the icon lives in the PE
# resource section, and the only practical reader is the Win32 API. Shelling
# out to PowerShell keeps this dependency-free (no pywin32/Pillow install)
# and, unlike the common `ExtractAssociatedIcon` route, `PrivateExtractIcons`
# asked for 256x256 returns the *largest* size the exe actually embeds —
# `ExtractAssociatedIcon` always yields a blurry 32x32. Verified on real
# Windows: a 7-Zip install produced a clean 256x256 PNG.
ICON_EXTRACT_PS = r"""
param([string]$Exe, [string]$Out)
Add-Type -AssemblyName System.Drawing
$sig = @'
[DllImport("user32.dll", CharSet=CharSet.Unicode)]
public static extern int PrivateExtractIcons(string lpszFile, int nIconIndex, int cxIcon, int cyIcon,
    IntPtr[] phicon, int[] piconid, int nIcons, int flags);
[DllImport("user32.dll")] public static extern bool DestroyIcon(IntPtr h);
'@
Add-Type -MemberDefinition $sig -Name Ico -Namespace Ex | Out-Null
$h = New-Object IntPtr[] 1
$id = New-Object int[] 1
$n = [Ex.Ico]::PrivateExtractIcons($Exe, 0, 256, 256, $h, $id, 1, 0)
if ($n -le 0 -or $h[0] -eq [IntPtr]::Zero) { exit 1 }
try {
    $bmp = [System.Drawing.Bitmap]::FromHicon($h[0])
    $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
} finally {
    [Ex.Ico]::DestroyIcon($h[0]) | Out-Null
}
"""


def extract_exe_icon(exe_path: str, dest_png: Path) -> bool:
    import subprocess
    import tempfile

    if not Path(exe_path).is_file():
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as fh:
        fh.write(ICON_EXTRACT_PS)
        script = fh.name
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", script, "-Exe", exe_path, "-Out", str(dest_png)],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        Path(script).unlink(missing_ok=True)
    return result.returncode == 0 and dest_png.is_file() and dest_png.stat().st_size > 0


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
    if is_non_app(name):
        return None  # a runtime/redistributable/driver, not a launchable app
    bin_path = extract_exe_path(display_icon)
    if not bin_path:
        return None

    icon_path = None
    icon_candidate = display_icon.strip().strip('"')
    if icon_candidate.lower().endswith(".ico") and Path(icon_candidate).is_file():
        icon_path = icon_candidate

    clean = clean_name(name)
    return {
        "id": f"win-{slugify(clean)}",
        "name": clean,
        "bin": bin_path,
        "category": guess_category(clean),
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
        dest_png = ICONS_DIR / f"win-{slugify(entry['name'])}.png"
        # Prefer the exe's own embedded icon at its largest size — that's the
        # real app artwork and works for essentially every installed program,
        # unlike DisplayIcon, which usually points at the exe's resource and
        # is therefore not a standalone .ico file at all. The .ico path is
        # kept as a cheap fallback for the rare entry that ships one.
        if extract_exe_icon(entry["bin"], dest_png):
            entry["icon"] = dest_png.name
            icons_copied += 1
        elif icon_path:
            import shutil
            dest_ico = ICONS_DIR / f"win-{slugify(entry['name'])}.ico"
            if not dest_ico.exists():
                shutil.copy(icon_path, dest_ico)
            entry["icon"] = dest_ico.name
            icons_copied += 1
        else:
            entry["icon"] = None
            icons_missing += 1
        results.append(entry)

    OUT.write_text(json.dumps(results, indent=2) + "\n")
    print(f"scanned {len(results)} installed programs -> {OUT.relative_to(ROOT)}")
    print(f"icons: {icons_copied} extracted from the exe's own resources, "
          f"{icons_missing} left for the category glyph")


if __name__ == "__main__":
    main()
