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

## Phase 1.1 — Polish backlog (requested after first look, not yet implemented)

User feedback after trying v1, captured here to act on next:

- [ ] **Use screen space better.** Tune the tile grid (flexbox or CSS grid — pick whichever is simplest to get right, no need to use both) so it fills the window width more effectively than the current fixed `minmax(88px, 1fr)` auto-fill grid.
- [ ] **Cursor feedback on hover.** Tiles are `<button>` elements but don't set `cursor: pointer` — add it, and double check the existing `:hover`/`:focus-visible` background swap actually reads as an affordance.
- [ ] **KDE icon coverage.** Only `dolphin` (the KDE file manager, correctly resolved) got a real icon from dashboard-icons; `konsole`, `kate`, `okular`, `spectacle`, `kcalc` all fall back to the generic Utilities/Office/Development glyph. Worth a targeted manual pass (alternate dashboard-icons slugs, Iconify, or a couple of UXWing/Magnific AI icons) for just these five.
- [ ] **Generic icon for CLI tools.** Many dataset entries are terminal/CLI utilities (`bat`, `btop`, `eza`, `dust`, `dua-cli`, etc.) that will never have a branded dashboard-icons entry. Consider a dedicated "CLI tool" glyph (distinct from the plain category fallback) so they're visually distinguishable from GUI apps missing an icon by accident.
- [ ] **Search/filter bar.** Filter the visible tiles by name as you type.
- [ ] **Responsive layout.** Verify/adjust at narrow and wide window widths — ties into the flexbox/grid rework above.
- [ ] Title bar already exists (`<h1>App Launcher</h1>`) — revisit once the search bar is added, since both live in the header area.

## Phase 2 — Later, not started

Ideas parked for after the Phase 1.1 polish pass — do not build until explicitly requested:

- Windows and macOS support (same catalog schema, add `bin`/launch-command per OS, add a presence-check + launch implementation per OS in Rust).
- Optional in-app minimal editor for hide/rename/recategorize, replacing hand-editing JSON, if that turns out to be annoying in practice.
- Packaging/installers (`cargo tauri build`) once the app is stable enough to want a distributable binary.

## Decisions already made (do not re-litigate without new information)

See [`SPEC.md`](SPEC.md) for full rationale. Short version: Tauri + plain HTML/CSS/JS, no scanner (targeted PATH lookups against a known catalog instead), 10 freedesktop-style categories, icons vendored offline from dashboard-icons/Iconify with manual fallbacks, single hand-edited `catalog.json` as source of truth.
