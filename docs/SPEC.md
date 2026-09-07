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
  "bin": "firefox",
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
| `bin` | Executable name checked on `$PATH` and used to launch |
| `icon` | Filename under `src/assets/icons/` (PNG or SVG); if missing at runtime, frontend falls back to `assets/icons/category/<category>.svg` |
| `hidden` | Manual override to hide an entry without deleting it |
| `cli` | Terminal-only tool (no real GUI icon will ever exist for it) — frontend shows the dedicated `assets/icons/category/cli-tool.svg` glyph instead of trying `icon`/category fallback, so it reads as "no icon expected" rather than "icon missing by accident" |

## Data sources for seeding the catalog

- `tools/sources/desktop-pkgs.json` — vendored snapshot of the user-supplied dataset (originally `https://raw.githubusercontent.com/interneto/tui-toolbox-installer/refs/heads/main/interneto_install/data/desktop-pkgs.json`). ~250 apps, each with `name`, `category`, `subcategory`, and package identifiers across 11 package managers (apt, pacman, AUR, dnf, emerge, flatpak, snap, brew, winget, nix, freebsd pkg). For Linux `bin` values, prefer the apt/pacman/flatpak id (usually equals the package name; a handful will need manual correction where the binary name differs from the package name).
- `tools/sources/vendor_apps.json` — hand-written entries not covered by the dataset above: KDE apps (Dolphin, Konsole, Kate, Okular, Spectacle, KCalc), GNOME apps (Files/Nautilus, Console, Text Editor, Calculator, Loupe), Microsoft/Apple apps that ship a real Linux binary (Edge, PowerShell) — Apple has essentially none on Linux; included mainly so the catalog format has real examples of `vendor` diversity for a possible future "by company" grouping. An entry can set an explicit `"icon"` (e.g. `"konsole.svg"`) to override the default `<id>.png` guess — used for the KDE apps, see the icon pipeline note below.
- `tools/sources/category_map.json` — one-time mapping table from the dataset's own `category`/`subcategory` strings to our 10 labels. Built by dumping the dataset's unique category values once and assigning each by hand.

`tools/build_catalog.py` merges these three into `src/data/catalog.json`. It is run manually/occasionally (e.g. when re-syncing against a newer desktop-pkgs.json) — not part of the running app, and re-running it should not silently blow away hand-edits the user has made directly to `catalog.json` (diff before overwriting, or merge by `id`).

## Icon pipeline

Priority order, each tried in sequence per catalog entry, all resolved **once at authoring time** — the running app never touches the network:

1. **dashboard-icons** (`homarr-labs/dashboard-icons`, CC0-1.0, git-clonable): `https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/<slug>.png`. Primary source, ~1800 apps covered, purpose-built for exactly this (app-dashboard tiles).
2. **Iconify** (`@iconify/json` npm package, vendored locally, per-icon-set license — mostly MIT/Apache/CC0): fallback when dashboard-icons has no match. 200k+ icons across 150+ sets, fully offline once the package is present.
3. **UXWing** (free for commercial use, no attribution required, but no bulk API — hand-pick one icon at a time): available for one-off per-app icons if you want to improve on a specific miss, but not used for bulk fetching.
4. **Magnific AI** (user's existing subscription): manual last resort to generate/upscale a one-off icon for anything still missing after 1–3. Dropped into `src/assets/icons/` by hand.

**Implementation note:** the 10 generic per-category fallback glyphs actually shipped as hand-authored SVGs (`tools/gen_category_glyphs.py` → `src/assets/icons/category/<Category>.svg`), plus an 11th dedicated `cli-tool.svg` glyph for entries flagged `"cli": true` — zero licensing questions, zero network dependency, trivially regenerable. First `sync_icons.py` pass against dashboard-icons got 108/270 app icons; most of the remaining misses are CLI tools, which now get the dedicated CLI glyph instead of a generic category fallback (see `is_cli()` in `build_catalog.py`: dataset subcategory `"CLI Utility"`, plus a small manual `CLI_ID_OVERRIDES` list for tools tagged otherwise, e.g. `btop`/`htop`/`fastfetch`/`neofetch`).

**KDE app icons**: dashboard-icons and Iconify have no coverage for KDE's own desktop apps (Konsole, Kate, Okular, Spectacle, KCalc) — confirmed by direct lookup. These five are instead sourced straight from KDE's own **breeze-icons** repo (`github.com/KDE/breeze-icons`, LGPL, `icons/apps/48/*.svg`) via `vendor_apps.json`'s `icon` override — the authoritative source for KDE's own app icons. Note some breeze-icons paths are themselves symlink aliases (e.g. `kcalc.svg` → `accessories-calculator.svg`, `spectacle.svg` → `ksnapshot.svg`); `raw.githubusercontent.com` serves a symlink's *target path as plain text*, not the real file, so always check the fetched content actually starts with `<svg`/`<?xml` before trusting it.

Explicitly **not used for bulk/automated fetching**: SVGRepo — its icons are aggregated from many sources with mixed, icon-by-icon licensing and no site-wide grant, which is incompatible with an unattended sync script. Fine to use manually if a specific icon's license is checked first, but `sync_icons.py` should not scrape it.

`tools/sync_icons.py` implements steps 1–2 automatically and prints a "still missing" list for manual handling via 3–4.

## Rust backend — `src-tauri/src/main.rs`

Two Tauri commands, intentionally minimal:

- `is_installed(bin: String) -> bool` — resolves `bin` against `$PATH` using the `which` crate. Called once per catalog entry from the frontend at startup (not a system scan — a targeted lookup against a known, finite list of ids from `catalog.json`).
- `launch_app(bin: String) -> Result<(), String>` — `std::process::Command::new(bin).spawn()`; any error is returned as a string for the frontend to display, never a panic/crash.

## Frontend — `src/index.html`, `main.js`, `style.css`

Plain HTML/CSS/JS, no framework, no build step. Flow:

1. `fetch('./data/catalog.json')`.
2. For each entry where `hidden` is not `true`, call `invoke('is_installed', { bin })` (parallelized with `Promise.all`).
3. Keep only entries that resolved `true`; group by `category` in the fixed 10-category order; skip categories with zero entries.
4. Render one `<section>` per non-empty category, each a CSS grid of tiles: icon (CLI entries always get `assets/icons/category/cli-tool.svg`; others try `icon`, `onerror` falls back to `assets/icons/category/<category>.svg`) + name.
5. Click on a tile → `invoke('launch_app', { bin })`; on promise rejection, show a small inline error banner instead of failing silently.
6. A `#search` text input in the header filters tiles by name (substring, case-insensitive) live via `input` events; a category section hides itself when every tile inside it is filtered out; a "no apps match" message shows when the query matches nothing.
7. Styling: CSS grid (`auto-fill, minmax(108px, 1fr)`) for the tile layout, a hover lift (`transform` + `box-shadow`) plus `cursor: pointer` for affordance, a narrow-width media query (≤520px) for smaller tiles/tighter padding, `prefers-color-scheme` for light/dark — no theme system beyond that for v1.

## Desktop shortcut

A `.desktop` entry points `Exec` at the release binary directly (`src-tauri/target/release/app`, built via `cargo build --release` in `src-tauri/`) and `Icon` at `src-tauri/icons/icon.png` — no `cargo tauri build`/installer packaging involved yet (that's Phase 2). The same file is placed both on `~/Desktop/` (double-clickable shortcut, matching the convention already used by other local projects: `Type=Application`, absolute `Exec` path, `Terminal=false`) and in `~/.local/share/applications/` (so it shows up in the KDE application launcher/search, not just the desktop icon). Re-run `cargo build --release` and the shortcut picks up the new binary automatically — no shortcut file changes needed after a rebuild.

## Explicitly out of scope for v1 (do not build without being asked)

- Any OS other than Linux.
- Enumerating/auto-discovering installed software beyond the fixed catalog's targeted `is_installed` checks.
- An in-app settings/editor UI — editing is done by hand in `catalog.json`.
- Keyboard shortcuts (beyond native text-input behavior in the search box), tray icon, autostart.
- Any runtime network access (icon fetching, update checks, telemetry).
