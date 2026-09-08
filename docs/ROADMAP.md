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

## Phase 1.3 — Curation, placeholders, layout fix (done)

More feedback after using v1.2: all 23 named KDE apps turned out already present (verified, no action needed there). Also asked for Apple/Microsoft placeholder entries, catalog curation (drop near-duplicates and low-value clutter), smaller icons + category-title symbols, and a real fix for the "grows too tall, needs scrolling" layout problem.

- [x] **Apple/Microsoft placeholder entries.** Added ~28 Apple and ~18 Microsoft apps to `vendor_apps.json` (`mac-*`/`win-*` ids) for future Windows/macOS support. Deliberately inert on Linux: `bin` holds the macOS/Windows name, which can never resolve via `which` here, so "only show installed" hides all of them for free — verified none accidentally resolve. Two are real, working Linux apps (`teams-for-linux`, an `onedrive` CLI client, flagged `cli: true`).
- [x] **Catalog curation.** New `EXCLUDED_IDS` set in `build_catalog.py`, applied to entries from any source: removed redundant KDE Connect variants (kept one), KWrite (Kate covers it), Kontact/KMail sub-editors that are clutter rather than real apps (Contact Print/Theme Editor, KMail Header Theme Editor, Sieve Editor, Import Wizard), two crash-reporter applets (GNOME's and KDE's), and onboarding/meta-config tools that aren't really "apps" (Welcome Center, KDebugSettings, Journald Browser, Menu Editor, Input Method Selector, SELinux Troubleshooter). Catalog went 322 → 369 (after adding the placeholders above) → 352 (after removing 17 low-value/duplicate entries) — see `build_catalog.py` for the full, commented list.
- [x] **Smaller icons, category symbols.** Tile icons 48px → 34px (28px at ≤520px); each category heading now shows an emoji (💻 Development, 🎓 Education, 🎨 Graphics, 🌐 Internet, 🎮 Games, 🎬 Multimedia, 📄 Office, 🔬 Science, ⚙️ System, 🧰 Utilities) via `CATEGORY_ICONS` in `main.js`.
- [x] **Fixed real bug: broken "Development" category glyph.** Its SVG had an unescaped `</>` label — literal `<` in SVG text content is invalid XML, so the file silently failed to parse/render. Any entry whose *primary* icon was also missing (e.g. GCC) showed the browser's raw "broken image" icon instead of the category fallback, because the one-shot `onerror` handler had already fired once and was cleared. Fixed by XML-escaping labels in `gen_category_glyphs.py`; also reclassified GCC (and the "Compiler" subcategory generally) as `cli: true` since a compiler has no real icon to speak of.
- [x] **Layout: fits one screen, no scrollbar.** Root cause of the "grows too tall" complaint: plain CSS Grid gives every card in a row the height of the tallest one, wasting space next to short row-mates. Switched `#categories` from `display: grid` to CSS multi-column (`column-count`, same 1/2/3/4/5 breakpoints), with `section.category { break-inside: avoid }` — columns balance independently instead of row-locking, which visibly fixed it (verified via screenshot: 352 apps across 10 categories, zero scrolling at a normal window size). Also tightened the inner tile grid to `minmax(64px, 1fr)` so each category card fits at least 3–4 icons per row even when narrow.

## Phase 2.1 — Windows/macOS support kickoff (code done, hardware-unverified)

User asked to start Phase 2, prioritizing cross-platform support first (over the in-app editor, installer packaging, and broader icon coverage, which are still parked below). This machine has no Windows or macOS box, so this is explicitly a **reviewed-but-untested first pass** — see `SPEC.md` "Cross-platform support" for the full unverified-gaps list.

- [x] **Catalog schema**: `bin` changed from a single Linux string to a per-OS object (`{"linux": ..., "windows": ..., "macos": ...}`), any key optional. Migrated automatically by regenerating `catalog.json` — no hand-editing needed.
- [x] **Rust backend** (`src-tauri/src/lib.rs`): both commands now take a `PlatformBin` struct and dispatch on `std::env::consts::OS`. Linux/Windows resolve via the `which` crate (already cross-platform/PATHEXT-aware); macOS checks for a `<name>.app` bundle in the three standard install locations and launches via `open -a`.
- [x] **`build_catalog.py` heuristics**: dataset entries with a `windows_winget` id get a guessed Windows bin (same string as Linux — works for CLI/dev tools, wrong for many GUI apps); entries with `macos_brew` get a title-cased guess at the macOS `.app` name. A `BIN_OVERRIDES` dict hand-corrects Firefox and VS Code since I'm confident about their real cross-platform names. `vendor_apps.json`'s ~65 KDE/GNOME/Apple/Microsoft entries all restructured to the new per-OS `bin` shape; Edge/PowerShell/OneDrive got real hand-verified triples.
- [x] **Fixed a real bug found while implementing this**: the system-scan merge step was replacing an entry's whole `bin` object instead of merging into it, silently dropping Firefox's and VS Code's Windows/macOS guesses the moment their Linux `.desktop` file was also found on this machine. Fixed to merge just the `linux` key in.
- [x] **Broader Linux distro/DE coverage**: `scan_system_apps.py`'s icon-theme detection was KDE-only (`kreadconfig`); added a GNOME check (`gsettings get org.gnome.desktop.interface icon-theme`) alongside it, both skipped safely if their tool isn't present. Only the KDE path has actually been exercised — GNOME/XFCE/etc. are unverified but written to degrade safely.
- **Verified**: rebuilt and re-ran on this Fedora/KDE machine after the refactor — same apps show, same icons, same launch behavior as before. That's the only platform actually tested.
- **Not verified, flagged plainly**: any Windows or macOS behavior at all (no hardware to test on); GNOME/other-DE icon theme detection; flatpak/snap app scanning (in the scan list, zero installed here to exercise it).

## Phase 2.2 — Installer packaging (done, Linux-verified)

Next item in the Phase 2 backlog, and the only remaining one fully testable on this machine.

- [x] **`cargo tauri build`** configured with `bundle.targets: ["appimage", "rpm"]` (not `"all"` — `.deb` needs Debian's `dpkg-deb`, not native to Fedora), `bundle.category: "Utility"`, `bundle.shortDescription` set.
- [x] **Renamed the Cargo package** `app` → `app-launcher` so the installed binary is `/usr/bin/app-launcher`, not the dangerously generic `/usr/bin/app` the default scaffold would have shipped in a real system package.
- [x] **Real bug hit and fixed**: `cargo tauri build` failed on the AppImage target (`failed to run linuxdeploy`) — root cause only visible with `--verbose`: linuxdeploy's bundled `strip` is too old to parse the `.relr.dyn` section this machine's very-new Fedora toolchain emits, so it failed to strip *any* library and gave up. Fixed with `NO_STRIP=1 cargo tauri build` (skips the strip step entirely).
- [x] **Filled in real package metadata** in `Cargo.toml` (description, author, MIT license, repository URL) — was still the scaffold's placeholder `"A Tauri App"`/`authors = ["you"]`/empty license.
- [x] **Verified**: both `app-launcher_0.1.0_amd64.AppImage` (~111MB) and `app-launcher-0.1.0-1.x86_64.rpm` (~6.7MB) build successfully; ran the AppImage directly and screenshotted the working UI; inspected the RPM's metadata and file list (`rpm -qip`/`rpm -qlp`).
- [x] Updated both `.desktop` shortcuts (`~/Desktop/AppLauncher.desktop`, `~/.local/share/applications/app-launcher.desktop`) to point at the renamed `target/release/app-launcher` binary.
- **Not done**: actually installing the RPM system-wide (`sudo rpm -i ...`) — needs `sudo`, not run this session. First real install-and-launch-from-menu is still an open verification step for whenever that's wanted.

## Phase 2.3 — In-app editor for hide/rename/recategorize (done)

`catalog.json` is bundled/read-only once installed, so edits go into a small per-user `overrides.json` (OS-standard app config dir) instead, applied on top at render time — see `SPEC.md` "In-app editor" for the full design.

- [x] Rust: `load_overrides`/`save_overrides` commands, reading/writing `overrides.json` in `app.path().app_config_dir()`.
- [x] Frontend: `#edit-toggle` header button; per-tile hover toolbar (hide ✕, edit ✎ → inline rename/recategorize form with save ✓/cancel ✕/reset ↺); a "Hidden apps" panel with Unhide buttons so hiding isn't a one-way trap.
- [x] UX follow-up requested immediately after: edit-form buttons switched from text labels to icons-only (✓/✕/↺) to save space; Escape now cancels an open form, or exits edit mode entirely if none is open.
- **Not verified**: click-through interaction testing — no input-automation tool (`xdotool`/`ydotool`) is available in this environment, so the click handlers, form swap, and persistence round-trip are verified by code review and by confirming the app config directory gets created on startup (proving the Rust path-resolution half works), not by actually clicking through the UI.

## Phase 2.4 — Broader icon coverage (done)

- [x] Added a second automated tier to `sync_icons.py`: Iconify's `simple-icons` set (CC0 brand marks) via the public render endpoint, tried under a couple of slug variants, for anything dashboard-icons misses. Skips `cli: true` entries and Apple/Microsoft placeholders (no `linux` bin) since they can never display an icon here anyway.
- [x] **Real bug found and fixed**: jsDelivr was rate-limiting concurrent requests with a `403` indistinguishable from a genuine 404 miss — an early pass wrongly marked `vlc`, `obs-studio`, `wine`, `teamviewer`, `kdenlive` and others as absent from dashboard-icons. Fixed with retry+backoff on non-404 failures and lower concurrency (16 → 6 workers).
- [x] **Second real bug found and fixed**: `build_catalog.py` always wrote `<id>.png` into `catalog.json`'s `icon` field regardless of what `sync_icons.py` actually vendored, so entries that got an Iconify `.svg` (e.g. `gnome-terminal`) silently fell back to the category glyph even though a real icon existed on disk. Fixed with a `default_icon()` helper that checks which extension actually exists before writing the field.
- **Result**: 176/291 Linux-relevant, non-CLI catalog entries now have a real vendored icon (up from 108/270 at the end of Phase 1.1), plus everything the Phase 1.2 system scan resolves directly from the local icon theme on top of that.

## Phase 2.2 — Installer packaging (done, Linux-verified)

Next item in the Phase 2 backlog, and the only remaining one fully testable on this machine.

- [x] **`cargo tauri build`** configured with `bundle.targets: ["appimage", "rpm"]` (not `"all"` — `.deb` needs Debian's `dpkg-deb`, not native to Fedora), `bundle.category: "Utility"`, `bundle.shortDescription` set.
- [x] **Renamed the Cargo package** `app` → `app-launcher` so the installed binary is `/usr/bin/app-launcher`, not the dangerously generic `/usr/bin/app` the default scaffold would have shipped in a real system package.
- [x] **Real bug hit and fixed**: `cargo tauri build` failed on the AppImage target (`failed to run linuxdeploy`) — root cause only visible with `--verbose`: linuxdeploy's bundled `strip` is too old to parse the `.relr.dyn` section this machine's very-new Fedora toolchain emits, so it failed to strip *any* library and gave up. Fixed with `NO_STRIP=1 cargo tauri build` (skips the strip step entirely).
- [x] **Filled in real package metadata** in `Cargo.toml` (description, author, MIT license, repository URL) — was still the scaffold's placeholder `"A Tauri App"`/`authors = ["you"]`/empty license.
- [x] **Verified**: both `app-launcher_0.1.0_amd64.AppImage` (~111MB) and `app-launcher-0.1.0-1.x86_64.rpm` (~6.7MB) build successfully; ran the AppImage directly and screenshotted the working UI; inspected the RPM's metadata and file list (`rpm -qip`/`rpm -qlp`).
- [x] Updated both `.desktop` shortcuts (`~/Desktop/AppLauncher.desktop`, `~/.local/share/applications/app-launcher.desktop`) to point at the renamed `target/release/app-launcher` binary.
- **Not done locally**: actually installing the RPM system-wide (`sudo rpm -i ...`) — needs `sudo`, not run this session.

## Phase 2.6 — CI: build and publish installers for every platform (done)

User asked to publish real binary installers for Windows, macOS, and Linux (`.deb`/`.rpm`/pacman) via a GitHub Actions workflow, then added AppImage (already covered) and Flatpak. Full design in `SPEC.md` "CI: build and publish installers".

- [x] `.github/workflows/release.yml`: 5 independent jobs — `tauri-bundles` (matrix ubuntu/windows/macos via `tauri-action`), `arch-package` (PKGBUILD via `makepkg` in an Arch container), `flatpak-bundle` (`flatpak-builder` action). Triggers on version tags or manual `workflow_dispatch` (draft prerelease, so it's testable without cutting a real release).
- [x] `packaging/arch/PKGBUILD` (git-sourced from `master`, `pkgver()` derived from git history) and `packaging/flatpak/dev.d7.app-launcher.json` (org.gnome.Platform//47 + rust-stable SDK extension, built with network access allowed — not Flathub-compliant, deliberately, see SPEC.md).
- [x] **Two real runs, watched live via `gh run view`**: first run — 4/5 jobs succeeded (Linux, Windows, macOS, Arch); Flatpak failed (`gnome-46`'s bundled Cargo too old for a dependency needing edition2024 — GNOME 46 is also EOL). Fixed by bumping to `gnome-47` (checked the tag actually exists via Docker Hub's API first). Second run — **all 5 jobs succeeded**.
- **Significant side effect**: this is the first time the Windows/macOS Rust code from Phase 2.1 has actually been compiled on real Windows/macOS runners — both succeeded, which is real (if partial — build-only, not runtime) verification that code was previously only "reviewed, never tested."
- **Not done**: installing/running any of the built packages on a real system; submitting the Flatpak to Flathub (would need a compliant offline/sandboxed rebuild, a separate undertaking).

## Phase 2.5 — Windows/macOS system-scan equivalents (code done, unverified)

Last item in the original Phase 2 backlog. Analogous to `scan_system_apps.py`, one per OS — see `SPEC.md` "Windows/macOS system scans" for the full design and caveats.

- [x] **`tools/scan_system_apps_macos.py`**: reads `Contents/Info.plist` from each `.app` bundle via `plistlib` (pure Python stdlib) for name/bin/category (`LSApplicationCategoryType` mapped to our 10 categories, same idea as freedesktop `Categories=`). **Partially verified**: `--self-test` builds a synthetic bundle in a temp dir and asserts the parsing logic reads it correctly — passed. That's real evidence the plist-reading code is correct, not evidence about real-world `/Applications` contents. Icon extraction not implemented (`.icns` → web-displayable needs macOS-only tools this machine doesn't have) — falls back to the category glyph.
- [x] **`tools/scan_system_apps_windows.py`**: enumerates the registry's `Uninstall` keys via `winreg` for name/bin (best-effort extraction from `DisplayIcon`, since Uninstall entries aren't meant for launching). **Cannot be verified at all** — `winreg` doesn't exist on Linux, so unlike the macOS script there's no fixture-based self-test possible; reviewed carefully, `winreg` imported lazily so the file at least loads without crashing here, but genuinely untested code. No category concept exists in the registry, so everything defaults to Utilities.
- [x] **`build_catalog.py` generalized**: extracted the Linux-specific merge logic into a shared `merge_system_scan(by_bin, entries, os_key)` used for all three scans. Confirmed via `git diff --stat` that re-running `build_catalog.py` after this refactor produces a byte-identical `catalog.json` — the generalization didn't change Linux behavior.

## Phase 2 backlog: fully worked through

Everything originally listed in Phase 2 (Windows/macOS support, installer packaging, in-app editor, broader icon coverage, CI publishing, Windows/macOS system scans) is now implemented, in every case as honestly as the available hardware allows — Linux fully verified by running the app; Windows/macOS verified only as far as "compiles and bundles in CI," with runtime behavior, real registry/plist quirks, and actual package installation all still open. Remaining ideas, not currently planned unless asked:

- Actually installing/testing the `.rpm`/`.deb`/Arch package/Flatpak on a real system, and cutting a real version-tagged release (current testing has only used manual `workflow_dispatch` dev builds).
- Running `scan_system_apps_windows.py`/`scan_system_apps_macos.py` on real hardware and merging the results in — right now neither has ever produced real output.
- A Flathub-compliant Flatpak rebuild (offline/sandboxed via `cargo-sources.json`) if actually submitting to Flathub is ever wanted.
- Windows icon extraction from an `.exe`'s embedded resources, and macOS `.icns` → web-displayable conversion — both skipped as out of reach without the respective OS's own tools.

## Decisions already made (do not re-litigate without new information)

See [`SPEC.md`](SPEC.md) for full rationale. Short version: Tauri + plain HTML/CSS/JS, 10 freedesktop-style categories, single hand-edited `catalog.json` as source of truth, no runtime scanning (the app only ever does a targeted `is_installed` PATH/bundle check against the pre-built catalog). The catalog itself is now built from three merged sources: the curated dataset, hand-written vendor entries, and — as of Phase 1.2 — an offline scan of this machine's own `.desktop` files, which also wins as the primary icon source (system theme → dashboard-icons/Iconify → manual fallbacks, all still resolved offline ahead of time, never at runtime). A final `EXCLUDED_IDS` filter (Phase 1.3) drops known low-value/duplicate entries regardless of source. `#categories` uses CSS multi-column (not grid) specifically so category cards balance across columns instead of row-locking to the tallest one. As of Phase 2.1, `bin` is a per-OS object and the Rust backend dispatches per-OS launch logic — Linux is the only platform this has been *run* on, though CI (Phase 2.6) has *compiled and bundled* it on real Windows/macOS runners. As of Phase 2.2, the Cargo package is named `app-launcher` (not `app`) and `cargo tauri build` needs `NO_STRIP=1` on this machine. As of Phase 2.3, user edits (hide/rename/recategorize) live in a separate per-user `overrides.json`, not in `catalog.json` itself — the shipped file stays read-only-safe for a packaged install. As of Phase 2.6, `.github/workflows/release.yml` builds and publishes installers for every platform (Windows/macOS/Linux/Arch/Flatpak) on a tag push or manual dispatch.
