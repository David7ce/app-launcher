# Implementation plan — Linux v1

This is the plan approved before implementation started. Kept verbatim as the reference for resuming work.

## Context

The user wants a simple home-screen-style dashboard that shows installed desktop apps as icon+title tiles, grouped into fixed categories, click-to-launch. Deliberately kept minimal for v1:

- **Linux only**, tested on the user's Fedora machine. Windows/macOS are out of scope for now (no code for them).
- **No system scanner.** We do not enumerate "everything installed" and try to auto-classify it — that was explicitly rejected as unnecessary complexity. Instead: a small, hand-curated catalog of known apps (seeded from a public package-id dataset + hand-added KDE/GNOME/Microsoft/Apple apps), each with a pre-assigned category. At startup the app does one cheap, targeted check per catalog entry — "does this specific binary exist on PATH?" — a lookup against a known list, not a scan.
- **Categories** (fixed, KDE/freedesktop-style, 10 total): Development, Education, Graphics, Internet, Games, Multimedia, Office, Science, System, Utilities.
- **Icons downloaded and vendored at authoring time**, not fetched at runtime — the shipped app needs no network access. Sources in priority order: dashboard-icons (CC0, bulk-clonable) → Iconify (`@iconify/json`, per-set open licenses, offline package) → a small hand-picked set of 10 generic category glyphs (UXWing, permissive, picked manually one at a time) → Magnific AI (user's subscription) as a manual last resort to generate/upscale one-off icons.
- **Editing category/hide/rename** happens by hand-editing one JSON file — no in-app settings UI, no override-merging logic at runtime.
- **Stack**: Tauri (Rust backend + plain static HTML/CSS/JS frontend, no JS framework, no npm build step for the app itself — only Rust/Cargo needed to build and run it). Maintenance scripts (catalog merge, icon sync) are one-off Python scripts, run manually, never part of the shipped app.

This was a greenfield project when planned — no existing code to reconcile with.

## File layout

```
app-launcher/
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── src/main.rs          # 2 commands: is_installed, launch_app
├── src/                      # static frontend, served as-is, no bundler
│   ├── index.html
│   ├── style.css
│   ├── main.js
│   ├── data/
│   │   └── catalog.json      # hand-maintained source of truth (see SPEC.md for schema)
│   └── assets/icons/
│       ├── <slug>.png        # per-app icons vendored from dashboard-icons/Iconify
│       └── category/*.png    # 10 generic category fallback glyphs
├── tools/                    # one-off maintenance scripts, not run by the app
│   ├── build_catalog.py      # merges sources/* -> src/data/catalog.json (run manually/occasionally)
│   ├── sync_icons.py         # downloads missing icons into src/assets/icons/
│   └── sources/
│       ├── desktop-pkgs.json     # vendored snapshot of the dataset the user provided
│       ├── vendor_apps.json      # hand-written KDE/GNOME/Microsoft/Apple entries
│       └── category_map.json     # dataset category/subcategory -> our 10 categories
└── README.md
```

## Build steps

1. **Scaffold Tauri app** (`src-tauri/` + `src/`) using the plain/vanilla template — no frontend framework, no `beforeDevCommand`/`beforeBuildCommand`, `distDir` pointing straight at `src/`.
2. **Rust backend** (`src-tauri/src/main.rs`):
   - `is_installed(bin: String) -> bool` — resolve `bin` on PATH using the `which` crate (small, no subprocess spawn). Called once per catalog entry from JS at startup.
   - `launch_app(bin: String) -> Result<(), String>` — `std::process::Command::new(bin).spawn()`, mapping any error to a string the frontend can show instead of crashing.
3. **Seed the catalog** (one-time authoring pass, via `tools/build_catalog.py`):
   - Read the vendored `desktop-pkgs.json` (~250 entries with `name`/`category`/`subcategory`/per-package-manager ids). For Linux, prefer `linux_debian_apt`/`linux_arch_pacman`/`flatpak` ids as the basis for `bin` (usually same as package name; flag mismatches for manual fixup).
   - Map each entry's dataset `category`/`subcategory` to one of our 10 categories via `tools/sources/category_map.json` (built once by listing the dataset's unique category values and assigning each).
   - Merge in `tools/sources/vendor_apps.json`: hand-written entries for KDE (Dolphin, Konsole, Kate, Okular, Spectacle, KCalc), GNOME (Files/Nautilus, Console/Terminal, Text Editor, Calculator, Loupe), and any Microsoft/Apple apps that actually ship a Linux binary (e.g. VS Code, Edge) — Apple has essentially none on Linux, included only for completeness/future cross-platform reuse.
   - Write the merged, deduplicated result to `src/data/catalog.json`. After this point the user maintains that file directly by hand.
4. **Icon vendoring** (`tools/sync_icons.py`, run manually, hits network only at authoring time):
   - For each catalog `icon` slug, try `https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/<slug>.png`; on miss, try resolving via a locally-installed `@iconify/json` icon set; save whichever hits to `src/assets/icons/<slug>.png`.
   - Print a list of entries with no match — those get a manually-picked UXWing icon or a Magnific AI-generated one dropped in by hand.
   - Separately, hand-source 10 generic glyphs (one per category) into `src/assets/icons/category/` as the universal fallback.
5. **Frontend** (`src/index.html`, `main.js`, `style.css`):
   - On load: `fetch('./data/catalog.json')`, then for each non-hidden entry call `invoke('is_installed', {bin})` (parallel via `Promise.all`).
   - Group the installed subset by `category` in the fixed 10-category order (skip empty categories); render one `<section>` per category with a CSS grid of tiles (icon `<img>` + title).
   - Click on a tile → `invoke('launch_app', {bin})`; on rejected promise, show a small inline error message instead of failing silently.
   - Minimal CSS: responsive grid, `prefers-color-scheme` for light/dark, no theme system beyond that.

## Verification

- `cargo tauri dev` on the Fedora machine.
- Confirm: only apps whose `bin` actually resolves on PATH are shown; they land in the correct category sections in the fixed order; icons render, and deleting/renaming one icon file confirms the category-fallback `onerror` path works.
- Click a real installed app (e.g. Firefox) and confirm it actually launches as a separate process.
- Temporarily set a `bin` to a nonexistent command and confirm `launch_app` surfaces an inline error rather than crashing the app.
- Hand-edit `src/data/catalog.json` (change a category, set `hidden: true`) and confirm a restart reflects the change with no other file changes needed.

## Where to resume

See [`ROADMAP.md`](ROADMAP.md) "Status" section for exactly what's installed/done vs. pending. Next concrete action is `cargo install tauri-cli --locked`, then step 1 above.
