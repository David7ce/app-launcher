import json
import shutil
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
catalog = json.loads((ROOT / "src" / "data" / "catalog.json").read_text())

print("--- catalog windows bins for the expected apps ---")
for e in catalog:
    if e["id"] in ("vlc", "inkscape", "win-excel", "win-word", "win-outlook"):
        print(f"  {e['id']:<14} bin.windows={e['bin'].get('windows')!r}")

b = "vlc.exe"
print(f"\nshutil.which({b!r}) -> {shutil.which(b)}")

APP_PATHS = [
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
]


def registry_lookup(name):
    exe = name if name.lower().endswith(".exe") else f"{name}.exe"
    for hive, sub in APP_PATHS:
        try:
            root = winreg.OpenKey(hive, sub)
        except OSError:
            continue
        try:
            k = winreg.OpenKey(root, exe)
        except OSError:
            continue
        raw = winreg.QueryValueEx(k, "")[0].strip()
        cleaned = raw.split('"')[1] if raw.startswith('"') else raw.split()[0]
        p = Path(cleaned)
        print(f"    {exe}: raw={raw!r} -> is_file={p.is_file()}")
        if p.is_file():
            return p
    return None


print(f"registry_lookup({b!r}) -> {registry_lookup(b)}")
