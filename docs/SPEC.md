# Technical spec

## Categories (fixed, exactly 10)

Chosen because they mirror freedesktop.org's Desktop Menu Specification "Main Categories" (the vocabulary KDE, GNOME, AppStream and Flatpak/Flathub already use), so classification isn't invented from scratch:

`Development`, `Education`, `Graphics`, `Internet`, `Games`, `Multimedia`, `Office`, `Science`, `System`, `Utilities`

Freedesktop → our label mapping used when assigning categories: `AudioVideo → Multimedia`, `Network → Internet`, `Game → Games`, `Utility → Utilities`; `Development`, `Education`, `Graphics`, `Office`, `Science`, `System` map by name directly.

Display order on screen is this fixed order; empty categories (no installed apps) are skipped, not shown empty.

## Catalog schema — `src/data/catalog.json`

Flat JSON array, one object per app. This file is the **single source of truth**, hand-edited directly going forward (deliberately no separate "overrides" layer — one file to touch, not two).

```json
{
  "id": "firefox",
  "name": "Firefox",
  "vendor": "Mozilla",
  "category": "Internet",
  "bin": { "linux": "firefox", "windows": "firefox.exe", "macos": "Firefox" },
  "icon": "firefox.png",
  "hidden": false,
  "cli": false
}
```

| Field | Meaning |
|---|---|
| `id` | Stable slug, also used as the icon-lookup key by convention (`icon` can override) |
| `name` | Display title on the tile |
| `vendor` | Provenance only (Mozilla, KDE, GNOME, Microsoft, Apple, etc.) — not used for grouping in v1, kept for future "by company" view if ever wanted |
| `category` | One of the 10 fixed categories above |
| `bin` | Per-OS launch identifier, keyed `linux`/`windows`/`macos` — **any key can be absent**, meaning the app doesn't exist on that OS. On Linux/Windows it's the executable name checked on `$PATH`; on macOS it's the `.app` bundle's display name (no `$PATH` for GUI apps there — see "Cross-platform support" below) |
| `icon` | Filename under `src/assets/icons/` (PNG or SVG); if missing at runtime, frontend falls back to `assets/icons/category/<category>.svg` |
| `hidden` | Manual override to hide an entry without deleting it |
| `cli` | Terminal-only tool (no real GUI icon will ever exist for it) — frontend shows the dedicated `assets/icons/category/cli-tool.svg` glyph instead of trying `icon`/category fallback, so it reads as "no icon expected" rather than "icon missing by accident" |

## Data sources for seeding the catalog

- `tools/sources/desktop-pkgs.json` — vendored snapshot of the user-supplied dataset (originally `https://raw.githubusercontent.com/interneto/tui-toolbox-installer/refs/heads/main/interneto_install/data/desktop-pkgs.json`). ~250 apps, each with `name`, `category`, `subcategory`, and package identifiers across 11 package managers (apt, pacman, AUR, dnf, emerge, flatpak, snap, brew, winget, nix, freebsd pkg). For Linux `bin` values, prefer the apt/pacman/flatpak id (usually equals the package name; a handful will need manual correction where the binary name differs from the package name).
- `tools/sources/vendor_apps.json` — hand-written entries not covered by the dataset above: KDE apps (Dolphin, Konsole, Kate, Okular, Spectacle, KCalc), GNOME apps (Files/Nautilus, Console, Text Editor, Calculator, Loupe), and ~65 Microsoft/Apple entries (`win-*`/`mac-*` ids, most single-platform placeholders; Edge/PowerShell/OneDrive have a real, hand-verified triple across all three OSes). Each entry's `bin` is already the per-OS object described above. An entry can set an explicit `"icon"` (e.g. `"konsole.svg"`) to override the default `<id>.png` guess — used for the KDE apps, see the icon pipeline note below. This file (and its breeze-icons downloads) is now mostly a **portability fallback**: it's what a fresh clone has before anyone runs the system scan below on their own machine.
- `tools/sources/category_map.json` — one-time mapping table from the dataset's own `category`/`subcategory` strings to our 10 labels. Built by dumping the dataset's unique category values once and assigning each by hand.
- `tools/sources/system_apps.json` — **generated**, not hand-written: the output of `tools/scan_system_apps.py` scanning this machine's actual installed `.desktop` files (see "System app scan" below). Machine-specific, regenerate after installing new software.

`tools/build_catalog.py` merges all of these into `src/data/catalog.json`, with `system_apps.json` entries winning any bin collision (they're ground truth for this machine — see the merge-priority note below). It is run manually/occasionally — not part of the running app, and re-running it should not silently blow away hand-edits the user has made directly to `catalog.json` (diff before overwriting, or merge by `id`).

A final pass drops anything in `EXCLUDED_IDS` (in `build_catalog.py`), applied after all sources are merged so it catches an unwanted id regardless of where it came from. This is for curation, not correctness: near-duplicates of something already covered by a better entry (extra KDE Connect variants, KWrite when Kate exists), obscure single-purpose sub-editors bundled with a bigger suite (Kontact/KMail's Contact Print/Theme Editor, Header Theme Editor, Sieve Editor, Import Wizard), crash-reporter applets (GNOME's and KDE's), and onboarding/meta-config tools that aren't really "apps" a user would deliberately launch (Welcome Center, KDebugSettings, Journald Browser, Menu Editor, Input Method Selector, SELinux Troubleshooter). Extend this set by hand as more low-value clutter turns up in a system scan — it's a judgment call, not a rule, so don't try to generalize it into a heuristic.

### Apple/Microsoft placeholder entries

`vendor_apps.json` also carries `mac-*` and `win-*` ids for common Apple and Microsoft apps that don't exist on every OS (Safari, Finder, Pages... / Notepad, Paint, Microsoft Word...). Most only have one key in their `bin` object (`{"macos": "Safari"}` or `{"windows": "notepad.exe"}`) — genuinely single-platform apps, not a gap. On Linux, `is_installed` returns `false` for these immediately since there's no `linux` key at all, so they stay correctly hidden there with zero cost. See "Cross-platform support" below for the Windows/macOS implementation itself, which is unverified on real hardware.

## System app scan — `tools/scan_system_apps.py`

The curated dataset only knows ~250 well-known apps, which undercounts what's actually installed on a real desktop. Every Linux desktop already has a complete, authoritative list of that: the XDG `.desktop` files each installed package drops into `/usr/share/applications` (plus `/usr/local/share/applications`, `~/.local/share/applications`, and the flatpak/snap equivalents). Each one already carries a `Name=`, a `Categories=` (the same freedesktop vocabulary our 10 categories map from — see `FREEDESKTOP_CATEGORY_MAP`), an `Exec=` (first token, with field codes like `%f`/`%U` stripped, becomes `bin`), and an `Icon=` that the *active icon theme* resolves to a real file already on disk. Reading this is strictly better than guessing: no classification heuristics needed, no network calls, and it's exactly what KDE/GNOME's own app menu shows.

- Icon resolution: an absolute `Icon=` path is used directly; a theme icon name is searched across `~/.local/share/icons`, `~/.icons`, `/usr/share/icons`, `/usr/local/share/icons` — trying the machine's actual active theme first (KDE via `kreadconfig6`/`kreadconfig5 --file kdeglobals --group Icons --key Theme`, e.g. `breeze-dark`; GNOME via `gsettings get org.gnome.desktop.interface icon-theme`, each skipped safely if its tool isn't installed), then `breeze`, `Adwaita`, `hicolor` — checking both real-world directory layouts seen in practice (hicolor-style `<size>/apps/<name>.<ext>` and breeze-style `apps/<size>/<name>.<ext>`), then `/usr/share/pixmaps/<name>.<ext>` as a last resort. Only the KDE path has actually been exercised (this machine); the GNOME check is written to degrade safely but is otherwise unverified.
- Every resolved icon is copied into `src/assets/icons/` — the **one shared icon folder**, same as every other source — named `<desktop-file-id><ext>`, so the lookup happens once per install and the running app just reads a local file like any other entry; re-running the scan skips files already copied.
- Merge priority in `build_catalog.py`: dataset → vendor_apps.json → **system_apps.json wins last**, keyed by `bin["linux"]`. A system-scanned Dolphin/Konsole/Kate/etc. replaces the dataset/vendor guess's Linux name+icon+category; anything with no prior entry for that bin is added as new. Critically, this is a **merge into the existing `bin` object, not a wholesale replacement** — a dataset entry's `windows`/`macos` guess is preserved and only the `linux` key gets overwritten with the system-scanned value (this was a real bug initially: Firefox and VS Code's Windows/macOS bins were getting silently dropped because the system-scanned Linux entry was replacing the whole object). On this development machine this took the catalog from 268 to 322 entries (54 new, ~18 upgraded with a real icon), then to 352 after Phase 1.3 curation.
- This machine's own `app-launcher.desktop` shortcut also shows up in the scan (self-referential) and is explicitly excluded (`EXCLUDED_IDS`, shared with the general curation list — see "Data sources" above).
- Known limitation, not yet handled: a `.desktop` file with `Terminal=true` (mostly TUI tools that still ship a menu entry, e.g. `btop`) gets scanned and given a real icon, but `launch_app` spawns the bin directly with no terminal attached — clicking it won't show anything useful. Not fixed yet since it wasn't the ask that prompted this scan; flagged in `ROADMAP.md`.

## Icon pipeline

Priority order, each tried in sequence per catalog entry, all resolved **once at authoring time** — the running app never touches the network:

1. **dashboard-icons** (`homarr-labs/dashboard-icons`, CC0-1.0, git-clonable): `https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/<slug>.png`. Primary source, ~1800 apps covered, purpose-built for exactly this (app-dashboard tiles).
2. **Iconify** (`@iconify/json` npm package, vendored locally, per-icon-set license — mostly MIT/Apache/CC0): fallback when dashboard-icons has no match. 200k+ icons across 150+ sets, fully offline once the package is present.
3. **UXWing** (free for commercial use, no attribution required, but no bulk API — hand-pick one icon at a time): available for one-off per-app icons if you want to improve on a specific miss, but not used for bulk fetching.
4. **Magnific AI** (user's existing subscription): manual last resort to generate/upscale a one-off icon for anything still missing after 1–3. Dropped into `src/assets/icons/` by hand.

**Actual priority in practice is now**: local system icon theme (via `scan_system_apps.py`, see below — exact match, zero network, wins on this machine for anything with a `.desktop` file) → dashboard-icons → Iconify → hand-picked UXWing/Magnific AI → generated fallback glyph. The list above (1–4) is what a *fresh clone on a different machine* falls back through before anyone runs the system scan there.

**Implementation note:** the 10 generic per-category fallback glyphs actually shipped as hand-authored SVGs (`tools/gen_category_glyphs.py` → `src/assets/icons/category/<Category>.svg`), plus an 11th dedicated `cli-tool.svg` glyph for entries flagged `"cli": true` — zero licensing questions, zero network dependency, trivially regenerable. First `sync_icons.py` pass against dashboard-icons got 108/270 app icons; most of the remaining misses are CLI tools, which now get the dedicated CLI glyph instead of a generic category fallback (see `is_cli()` in `build_catalog.py`: dataset subcategories `"CLI Utility"` and `"Compiler"` (e.g. `gcc` — no meaningful icon exists for a compiler), plus a small manual `CLI_ID_OVERRIDES` list for tools tagged otherwise, e.g. `btop`/`htop`/`fastfetch`/`neofetch`/`rsync`/`tmux`/`tree`/`curl` — these last four have no GUI and will never have a branded icon, so they get the base CLI glyph rather than a generic category one).

**Bug already hit once, worth remembering:** SVG text content is XML — a raw `<` or `>` in a label (the Development glyph's `</>` originally) makes the file invalid XML that silently fails to parse. The failure is easy to miss because it looks like a *missing* icon, not a *broken* one: the primary icon 404s (expected), `onerror` fires and points at the category glyph, that also fails to render, but the handler already cleared itself after the first failure — so instead of a second fallback you get the browser's raw "broken image" placeholder. Fixed by running every label through `xml.sax.saxutils.escape()` in `gen_category_glyphs.py`. If a fallback icon ever looks broken instead of just generic, check whether the SVG itself is valid XML before assuming it's a missing-file problem.

**KDE app icons**: dashboard-icons and Iconify have no coverage for KDE's own desktop apps (Konsole, Kate, Okular, Spectacle, KCalc, Gwenview, Elisa) — confirmed by direct lookup. `vendor_apps.json` sources these straight from KDE's own **breeze-icons** repo (`github.com/KDE/breeze-icons`, LGPL, `icons/apps/48/*.svg`) via a per-entry `icon` override, and `ICON_OVERRIDES` in `build_catalog.py` does the same for dataset-derived entries (Gwenview, Elisa) — the portability fallback for a machine where the system scan hasn't run yet. Note some breeze-icons paths are themselves symlink aliases (e.g. `kcalc.svg` → `accessories-calculator.svg`, `spectacle.svg` → `ksnapshot.svg`); `raw.githubusercontent.com` serves a symlink's *target path as plain text*, not the real file, so always check the fetched content actually starts with `<svg`/`<?xml` before trusting it. On this machine the system scan now supersedes all of these with the real local theme icon anyway.

Explicitly **not used for bulk/automated fetching**: SVGRepo — its icons are aggregated from many sources with mixed, icon-by-icon licensing and no site-wide grant, which is incompatible with an unattended sync script. Fine to use manually if a specific icon's license is checked first, but `sync_icons.py` should not scrape it.

`tools/sync_icons.py` implements steps 1–2 automatically and prints a "still missing" list for manual handling via 3–4.

## Rust backend — `src-tauri/src/lib.rs`

Two Tauri commands, intentionally minimal, both taking a `PlatformBin { linux: Option<String>, windows: Option<String>, macos: Option<String> }` (deserialized straight from the catalog entry's `bin` object — the frontend never needs to know which OS it's running on, it just forwards `entry.bin` as-is):

- `is_installed(bin: PlatformBin) -> bool` — `bin.for_current_os()` (matches on `std::env::consts::OS`) returns `None` → `false` immediately with no further check. Otherwise: Linux/Windows both resolve via `which::which(name)` (cross-platform, Windows-aware — checks `PATHEXT` so a bare `"git"` resolves `git.exe`); macOS checks for a `<name>.app` bundle under `/Applications`, `/System/Applications`, `$HOME/Applications` via plain `Path::exists()` (no `$PATH` for GUI apps there). Called once per catalog entry from the frontend at startup (not a system scan — a targeted lookup against a known, finite list of ids from `catalog.json`).
- `launch_app(bin: PlatformBin) -> Result<(), String>` — Linux/Windows: `std::process::Command::new(name).spawn()`; macOS: `Command::new("open").args(["-a", name]).spawn()` (the standard way to launch an app by name regardless of its exact path). Any error is returned as a string for the frontend to display, never a panic/crash.

## Cross-platform support (Windows/macOS) — implemented, unverified on real hardware

This machine is Fedora + KDE only; there is no Windows or macOS box to build or run on. The Rust logic above and the `bin` heuristics below were written carefully and compile cleanly, but **have never been executed on Windows or macOS** — treat them as a reviewed-but-untested first pass, not confirmed working.

- **`tools/build_catalog.py` bin heuristics for dataset entries** (desktop-pkgs.json already carries `windows_winget`/`macos_brew` ids, which are package identifiers, not executable/app names): if `windows_winget` is present, guess the Windows bin is the *same string* as the Linux bin (many CLI/dev tools share an identical binary name cross-platform; wrong for plenty of GUI apps — same "guess, hand-fix later" spirit as the existing Linux bin guess). If `macos_brew` is present, title-case the brew slug as a guess at the `.app` display name (`visual-studio-code` → `Visual Studio Code`; wrong for acronyms like `vlc` → `Vlc` instead of `VLC`). A small `BIN_OVERRIDES` dict hand-corrects the apps worth getting exactly right (currently Firefox, VS Code).
- **Known, documented gaps, not attempted**: Windows resolution is `$PATH`-only, so it misses apps only reachable via Start Menu shortcuts, the registry `App Paths` key, or UWP/Store packages (`shell:AppsFolder`). macOS resolution requires an exact, case-sensitive `<name>.app` in one of three fixed directories — no Spotlight/`mdfind` fuzzy matching.
- **Coverage**: only hand-curated vendor entries (Firefox, VS Code, Edge, PowerShell, OneDrive, the Apple/Microsoft placeholders) have a real, deliberately-chosen cross-OS `bin`. The bulk of the ~350-entry catalog only gets a low-confidence Windows/macOS guess when the dataset happened to list a `winget`/`brew` id for it, or nothing at all otherwise.
- **Verification actually performed**: the Linux path was rebuilt and rerun after this refactor to confirm it still works exactly as before (same apps show, same icons, same launch behavior) — that's the only platform this was actually tested on. `cargo build` succeeding is the only evidence the Windows/macOS branches are even syntactically sound.

## Frontend — `src/index.html`, `main.js`, `style.css`

Plain HTML/CSS/JS, no framework, no build step. Flow:

1. `fetch('./data/catalog.json')`.
2. For each entry where `hidden` is not `true`, call `invoke('is_installed', { bin })` (parallelized with `Promise.all`).
3. Keep only entries that resolved `true`; group by `category` in the fixed 10-category order; skip categories with zero entries.
4. Render one `<section class="category">` per non-empty category (a bordered, rounded card — see layout below), each containing an inner CSS grid of tiles: a 34px icon (28px at ≤520px; CLI entries always get `assets/icons/category/cli-tool.svg`, others try `icon`, `onerror` falls back to `assets/icons/category/<category>.svg`) + name. The category heading itself is prefixed with a small emoji per category (`CATEGORY_ICONS` in `main.js`: 💻🎓🎨🌐🎮🎬📄🔬⚙️🧰) so a category reads at a glance even before the label text.
5. Click on a tile → `invoke('launch_app', { bin })`; on promise rejection, show a small inline error banner instead of failing silently.
6. A `#search` text input, centered in the header, filters tiles by name (substring, case-insensitive) live via `input` events; a category card hides itself when every tile inside it is filtered out; a "no apps match" message shows when the query matches nothing.
7. **Layout**: `header` is a 3-column grid (`1fr minmax(220px,420px) 1fr`) so `#search` sits truly centered regardless of the title's width, collapsing to a stacked single column below 520px. `#categories` uses **CSS multi-column** (`column-count`, not `display: grid`) with a column count that scales with window width — 1 by default, 2 at ≥700px, 3 at ≥1050px, 4 at ≥1350px, 5 at ≥1650px — and `section.category { break-inside: avoid }`. This is deliberate, not the obvious choice: a regular grid gives every card in a row the height of its tallest row-mate, so with 10 categories that vary a lot in size (some have 2 apps, some have 15+) a lot of the page height is empty padding next to short cards. Multi-column instead flows each card into whichever column is currently shortest, balancing total height across columns — this is what actually fixed the "grows too tall, needs a scrollbar" complaint, verified by screenshot (352 apps, zero scrolling at a normal window size). Each category card's own inner tile grid (`auto-fill, minmax(64px, 1fr)`, tuned small enough that even a narrow card fits at least 3–4 icons per row) is independent of the outer column count. A hover lift (`transform` + `box-shadow`) plus `cursor: pointer` gives tile affordance, `prefers-color-scheme` handles light/dark — no theme system beyond that for v1.

## Desktop shortcut

A `.desktop` entry points `Exec` at the release binary directly (`src-tauri/target/release/app`, built via `cargo build --release` in `src-tauri/`) and `Icon` at `src-tauri/icons/icon.png` — no `cargo tauri build`/installer packaging involved yet (that's Phase 2). The same file is placed both on `~/Desktop/` (double-clickable shortcut, matching the convention already used by other local projects: `Type=Application`, absolute `Exec` path, `Terminal=false`) and in `~/.local/share/applications/` (so it shows up in the KDE application launcher/search, not just the desktop icon). Re-run `cargo build --release` and the shortcut picks up the new binary automatically — no shortcut file changes needed after a rebuild.

## Explicitly out of scope (do not build without being asked)

- Windows/macOS **testing, packaging, or bug-fixing** — the code exists (see "Cross-platform support" above) but this is still developed and verified on Linux only; don't assume a Windows/macOS report is accurate without a real machine to check it on.
- A Windows/macOS `scan_system_apps.py` equivalent (Start Menu/registry scanning, `mdfind`/Spotlight scanning) — not attempted; those platforms currently rely entirely on the dataset/vendor-entry heuristics.
- **Runtime** enumeration of installed software — the app itself still only ever does a targeted `is_installed` check against the fixed, pre-built catalog. `scan_system_apps.py` discovering apps is an offline maintenance step (like `build_catalog.py` or `sync_icons.py`), not something the running app does.
- An in-app settings/editor UI — editing is done by hand in `catalog.json`.
- Keyboard shortcuts (beyond native text-input behavior in the search box), tray icon, autostart.
- Any runtime network access (icon fetching, update checks, telemetry) — `scan_system_apps.py` itself makes none either (everything it reads is local).
