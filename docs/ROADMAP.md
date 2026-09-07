# Roadmap

## Status as of 2026-09-07

**v1 MVP is built and running.** `cargo tauri dev` opens the dashboard, showing installed apps grouped into the 10 categories, click-to-launch works. User confirmed on their own machine: "not bad for first release."

- ✅ Rust/Cargo, Python 3, Fedora webview deps, `tauri-cli` all installed.
- ✅ Tauri scaffold (`src-tauri/`, `src/`, static frontend, no npm/JS framework).
- ✅ Rust commands `is_installed`/`launch_app` (`src-tauri/src/lib.rs`).
- ✅ `src/data/catalog.json` generated (268 entries) via `tools/build_catalog.py` from `desktop-pkgs.json` + hand-written `vendor_apps.json`, mapped through `category_map.json` into the 10 fixed categories.
- ✅ Icons: `tools/sync_icons.py` vendored 108/270 app icons from dashboard-icons; the rest fall back to 10 hand-authored SVG category glyphs (`tools/gen_category_glyphs.py`) — a simplification from the original UXWing-sourcing plan, see `SPEC.md`.
- ✅ Frontend: `src/index.html` + `main.js` + `style.css`, fetch → is_installed filter → group by category → render → click to launch.
- ✅ Fixed a real bug found during first run: Visual Studio Code appeared twice (dataset entry `visual-studio-code` + a redundant hand-written `vscode` vendor entry, both binding `code`). Removed the redundant vendor entry and added a general bin-collision dedupe pass to `build_catalog.py` so any future duplicate-bin situation (e.g. `jellyfin-client`/`jellyfin-server` both guessed as bin `jellyfin`) is caught automatically instead of shipping two tiles that launch the same thing.

## Phase 1.1 — Polish backlog (done)

User feedback after trying v1, all items now implemented:

- [x] **Use screen space better.** Tile grid uses `auto-fill, minmax(108px, 1fr)` with a `max-width: 1600px` centered `<main>`, tighter gap — fills window width better than the original `minmax(88px, 1fr)`.
- [x] **Cursor feedback on hover.** `cursor: pointer` was already present on `.tile`; added a hover lift (`translateY` + `box-shadow`) and an `:active` press state so the affordance actually reads.
- [x] **KDE icon coverage.** dashboard-icons/Iconify confirmed to have zero coverage for Konsole/Kate/Okular/Spectacle/KCalc (checked directly). Sourced all five from KDE's own `breeze-icons` GitHub repo instead (LGPL, authoritative) via a per-entry `icon` override in `vendor_apps.json`. Watch out: two of the breeze-icons paths (`kcalc.svg`, `spectacle.svg`) are symlink aliases, and `raw.githubusercontent.com` serves a symlink's target path as plain text rather than the real SVG — had to follow the alias by hand (`accessories-calculator.svg`, `ksnapshot.svg`).
- [x] **Generic icon for CLI tools.** Added a `cli` boolean field to the catalog schema (`is_cli()` in `build_catalog.py`: dataset subcategory `"CLI Utility"` + a manual override list for tools tagged otherwise) and a dedicated terminal-prompt SVG glyph (`assets/icons/category/cli-tool.svg`) shown instead of the plain category fallback.
- [x] **Search/filter bar.** `#search` input in the header, live substring filter over tile names, hides empty category sections, shows a "no apps match" message.
- [x] **Responsive layout.** Added a `≤520px` media query (smaller tiles/icons, full-width search, tighter padding).

## Desktop shortcut (done)

`.desktop` entries created on `~/Desktop/AppLauncher.desktop` and `~/.local/share/applications/app-launcher.desktop`, `Exec` pointing at the `cargo build --release` binary (`src-tauri/target/release/app`). Validated with `desktop-file-validate` (no warnings) and smoke-tested by launching directly. See `SPEC.md` "Desktop shortcut" for details. Rebuilding the release binary doesn't require touching the shortcut files.

## Phase 1.2 — System scan, layout, and icon completeness (done)

User feedback: too many locally-installed apps were missing (the curated dataset only knows ~250 apps), and asked for icons for a few specific CLI tools/KDE apps plus a better multi-column layout.

- [x] **System app scan.** New `tools/scan_system_apps.py` reads this machine's actual `.desktop` files (XDG application dirs) instead of only the curated dataset — real `Name=`/`Categories=`/`Exec=`/`Icon=`, zero guessing, zero network. Icons resolved via the active icon theme (`breeze-dark` here) are copied into the shared `src/assets/icons/` folder so lookups happen once, not on every rebuild. `build_catalog.py` now merges this in with system entries winning bin collisions. Result on this machine: 268 → 322 catalog entries (54 new, ~18 upgraded from a guessed/downloaded icon to the real local one — Dolphin, Konsole, Kate, Okular, Spectacle, KCalc, Gwenview, Elisa all now show their actual system icon).
- [x] **Base/generic icon for `rsync`, `tmux`, `tree`, `curl`.** Added to `CLI_ID_OVERRIDES` in `build_catalog.py` — these have no GUI and will never have a branded icon, so they show the CLI glyph rather than a generic category fallback or a broken one.
- [x] **Icons for Gwenview and Elisa.** Sourced from breeze-icons as the portability fallback (`ICON_OVERRIDES` in `build_catalog.py`); now superseded by the real system-scanned icon on this machine anyway.
- [x] **Multi-column category layout.** `#categories` is a CSS grid whose column count scales with window width (1/2/3/4/5 at 0/700/1050/1350/1650px), each category rendered as a bordered, rounded card (`section.category`) instead of a full-width stacked block.
- [x] **Centered search bar.** `header` is now a 3-column grid (`1fr minmax(220px,420px) 1fr`) so `#search` sits centered regardless of the title's width.

Known gap surfaced by the scan, not yet fixed: a `.desktop` file with `Terminal=true` (TUI tools that still ship a menu entry, e.g. `btop`) gets a real icon and shows up normally, but `launch_app` spawns the bin directly with nothing to attach a terminal to — clicking it won't visibly do anything useful. Needs `launch_app` (or a new catalog field) to know when to wrap `Exec` in a terminal emulator. Not fixed yet — flagging for next time.

## Phase 2 — Later, not started

Ideas parked for after this polish pass — do not build until explicitly requested:

- Windows and macOS support (same catalog schema, add `bin`/launch-command per OS, add a presence-check + launch implementation per OS in Rust).
- Optional in-app minimal editor for hide/rename/recategorize, replacing hand-editing JSON, if that turns out to be annoying in practice.
- Full installer packaging (`cargo tauri build` → `.rpm`/`.deb`/AppImage) — the desktop shortcut currently points straight at the debug/release binary, not a packaged bundle.
- Broader icon coverage pass (Iconify integration proper, or Magnific AI for specific remaining gaps) if the current dashboard-icons + breeze-icons + CLI-glyph coverage still feels thin in practice.

## Decisions already made (do not re-litigate without new information)

See [`SPEC.md`](SPEC.md) for full rationale. Short version: Tauri + plain HTML/CSS/JS, 10 freedesktop-style categories, single hand-edited `catalog.json` as source of truth, no runtime scanning (the app only ever does a targeted `is_installed` PATH check against the pre-built catalog). The catalog itself is now built from three merged sources: the curated dataset, hand-written vendor entries, and — as of Phase 1.2 — an offline scan of this machine's own `.desktop` files, which also wins as the primary icon source (system theme → dashboard-icons/Iconify → manual fallbacks, all still resolved offline ahead of time, never at runtime).
