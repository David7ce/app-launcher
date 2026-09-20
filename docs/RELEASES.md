# Releases

What has actually shipped, newest first. For work not yet done, see
[`ROADMAP.md`](ROADMAP.md).

---

## v0.4.0 — 2026-09-20

A leaner release pipeline, a tidier repository, shorter icon names, and every roadmap item that can
be finished from a Windows machine.

### Release

- **Four artifacts instead of twelve**: a Windows NSIS installer, an Apple-silicon macOS `.dmg`, a Linux
  `.tar.gz` and a Flatpak. Dropped: the `.msi`, Intel macOS, `.deb`, `.rpm`, AppImage and the Arch package
  (and its `-debug` twin).
- **The workflow creates the draft release once, up front**, with notes pulled from `docs/RELEASES.md`, so
  the build jobs only upload to it. A tag with no notes section fails loudly instead of publishing an empty
  release. Cutting a release is: write the section here, bump the version, tag.
- **A smaller, faster Windows build**: NSIS only (no WiX), a size-optimised release profile
  (`opt-level = "s"`, `strip`, `panic = "abort"`), an `rlib`-only library and no logging plugin. Measured
  with a warm cache, the Windows job went from 238s to 131s and the Linux job from 179s to 82s; the
  installers shrank about 10% (Windows 7.5 → 6.8 MB, macOS 8.7 → 7.8 MB).
- **The Flatpak builds offline**, as Flathub requires: every crate is listed with its checksum in
  `packaging/flatpak/cargo-sources.json`, and CI checks the file still matches `Cargo.lock`.

### Catalog

- **Icon files are named after the app**: `word.png`, not `win-word.png`. The `win-` prefix is gone from
  all 73 ids that had it, and each entry keeps its old id in `aka`, so a rename or hide you saved under the
  old id follows the app.
- **32 more Windows apps**, previously held back: the LibreOffice apps (Writer, Calc, Impress, Draw, Base,
  Math), the Windows admin tools (Event Viewer, Services, Task Scheduler, Computer Management, Resource and
  Performance Monitor, System Information and Configuration, Disk Cleanup, ...), the WSL distros, GRASS and
  SAGA GIS, CMake, Character Map, Magnifier, Narrator and the on-screen keyboard.
- **75 more icons ship with the app.** The build now extracts them from the Start Menu (the app's exe, the
  package's manifest, or the shell's own tile), so a fresh install shows them without extracting anything:
  246 of 321 Windows entries ship an icon, and only 136 of 440 entries lack one (was 181 of 408).

### Fixes

- **Linux and macOS would have lost the CLI fallback icon.** `main.js` pointed at `CLI-tool.png` while the
  file is `cli-tool.png`: harmless on Windows, a 404 on a case-sensitive filesystem. It had not been
  released; the new frontend tests caught it, and a test now checks that every asset path in the frontend
  matches a real file name exactly.

### Tests

- **The frontend has tests now**: 11 run the real `index.html` and `main.js` under jsdom with a stubbed
  Tauri bridge — the pills, the column dealing, search, the editor, hiding, the id migration, launching and
  the icon fallback — in their own CI job. With 37 Python and 14 Rust tests, all of it runs on every push.

### Repository

- **Clearer layout.** `tools/` is now `data/` (inputs), `scan/` (`linux.py`, `windows.py`, `macos.py`),
  `icons/` (`sync.py`, `backfill.py`, `make_glyphs.py`, `glyphs/`), `tests/` and `dev/`; the PowerShell helpers
  moved from `src-tauri/src/` to `src-tauri/scripts/`. See the layout in the README.
- **Removed what nothing used**: the 27 archived icon SVGs (the fallback-glyph sources are kept), the
  generated `missing_icons.txt`, the unused Windows-Store logos, the Android config, `tauri.linux.conf.json`,
  the mobile entry point, `tauri-plugin-log`, and the Arch packaging.

**Known limits:** macOS has never run on real hardware, and the Linux tarball and Flatpak have not been
installed on a real system. See [`ROADMAP.md`](ROADMAP.md).

---

## v0.3.0 — 2026-09-20

Windows goes from "runs" to "finds nearly everything you have installed", the interface is
reworked so the whole launcher fits one screen, and CI now guards every push.

### Interface

- **All / GUI / CLI filter pills**, with counts, replace the collapsible CLI section. CLI Tools is
  the first card, followed by the categories, in one flow. Search and the pills combine.
- **Everything fits one screen.** Cards are dealt into the shortest column instead of CSS
  multi-column, which left the right third of the window empty because tall cards can't split. On
  a 1920×1057 window all 143 tiles are visible with no scrolling; 6, 4, 2 or 1 columns as the
  window narrows.
- **A strict tile grid**: every tile is the same fixed 80×80 box, icons a fixed 30px, labels
  clamped to two lines (full name in the tooltip).
- **CLI tools show their own logo** when one exists (27 of 50), not only the generic glyph.
- **The editor's Save and Reset now update the tile immediately** (they showed stale data until
  Edit was toggled), and the hover toolbar is reachable from the keyboard.
- **Renamed apps keep your edits.** An entry lists its old ids (`aka`), and saved renames, hides and
  recategorisations are moved to the new id.

### Windows

- **Start Menu and Store apps are found.** A catalog entry whose exe isn't on `$PATH` or in App
  Paths is looked up by name in the Start Menu (classic shortcuts and UWP packages) and launched
  through `shell:AppsFolder`. About 24 more apps appeared, and 36 Start Menu apps were added
  (Camera, Photos, Affinity ×3, AdGuard, Wintoys, Raindrop, Minecraft Launcher, Adobe Acrobat,
  WSL, ...). `bin.windows` can be `start:<Start Menu name>` when the names differ.
- **CLI tools open properly.** About 30 terminal tools (git, bun, pandoc, nmap, python, node,
  PowerShell, Command Prompt, WSL, ...) flashed a console and vanished. They now open in a window
  that stays open. Root cause: a child process inherits the app's null stdin, so `cmd /k` read EOF
  and exited; launching through `cmd /c start` fixes it.
- **Launch targets are no longer the uninstaller.** The scan trusted `DisplayIcon`, which usually
  points at `unins000.exe`, so Steam, Ollama, CapCut, Npcap and Tesseract would have launched their
  uninstaller. Also fixed: the quoted `"path",0` form (qBittorrent was missing), and per-user paths
  are stored as `%LOCALAPPDATA%`/`%USERPROFILE%` instead of one machine's profile.
- **Icons for anything without a shipped one**, taken from the installed exe, the package's
  manifest, or the shell's own Start tile, cached under the app cache dir. An upside-down bug in
  the shell-tile extractor was fixed and the cache versioned. Standalone `.ico` files are now really
  converted to PNG.
- **Fixed:** 32 entries silently dropped as "duplicates" (they shared an empty launch key);
  Notepad++ overwriting Notepad (`+` is now part of a name); the wrong Dolphin (it was the Dolphin
  web-browser logo) and Calculator icons; `python3.exe` resolving to the Store stub; the Microsoft
  Office *suite* installer appearing as an app.

### Linux and macOS

- **Icon fallback**: Linux resolves the `.desktop` file's `Icon=` through the theme directories;
  macOS converts the bundle's `.icns` with `sips`. Unit-tested and compiled by CI, but not yet run
  on real desktops.
- **Fixed a build break**: Linux and macOS had not compiled since the App Paths change (a
  Windows-only function was called without a stub). CI now builds all three on every push.

### Catalog

- Cleaner names (`WinMerge x64 (Current user, 64-bit)` → `WinMerge`, no `(Preview)`, no taglines)
  and hand corrections kept in reviewable tables: Kiwix → Education, GPX/cycling analysers →
  Science, WinMerge → Utilities, `kubectl`/`WordPress`/`KStars`/`ONLYOFFICE` spelled properly.
  UltraStar's three tiles are one; Hermes Agent added as a CLI tool.

### Project

- **CI on every push and pull request**: `clippy -D warnings` and `cargo test` on Linux, Windows
  and macOS, plus the Python tests; superseded runs are cancelled and docs-only changes skipped.
  It caught four cross-platform bugs during this release.
- **Dependencies**: GitHub Actions moved to their Node 24 majors (`checkout` v7, `setup-python`
  v7, `action-gh-release` v3, `tauri-action` v1); Rust crates updated (tauri 2.11.6).
- **Tests**: 33 Python and 14 Rust. **LICENSE** (MIT) and a third-party icon attribution table
  added; a real CSP replaces `csp: null`; the overrides file is written atomically; a local
  `cargo tauri build` works on Windows and macOS.

**Known limits:** macOS has never run on real hardware, and the CI-built installers have not been
installed on real systems. See [`ROADMAP.md`](ROADMAP.md).

---

## v0.2.0 — 2026-09-20

**Windows support verified on real hardware.** Until this release the Windows
code path had only ever been *compiled* (in CI) — nothing had run it. Running
it on a real Windows machine surfaced four bugs, all invisible from Linux:

- **Windows launch targets were package ids, not executables.** The catalog
  guessed the Windows binary was the same string as the Linux one, but that is
  usually a *package* id (`dbeaver-ce`, `golang`,
  `intellij-idea-community-edition`) — 208 of 224 entries. None can resolve on
  `$PATH`, so most Windows tiles silently never appeared at all. The guess is
  now only made for a plausible bare executable name.
- **The system scan produced duplicates instead of upgrading entries.** It
  emits full paths (`C:\Program Files\7-Zip\7zFM.exe`) because that is what the
  registry stores, but the merge was keyed on the Linux binary — so every
  scanned app became a brand-new GUID-named entry rather than updating the real
  one.
- **Categories collapsed into "Utilities".** The merge matched on the
  executable basename, which found **0** matches (curated entries rarely carry
  a Windows binary), dumping 52 of 68 apps — GIMP, Steam, Spotify, OBS,
  Telegram, Android Studio — into Utilities. Matching on the normalized display
  name instead joins 63 of 68 and lets the curated category win. Utilities went
  from 116 entries to 75.
- **No icons existed on Windows.** Every tile was a generic placeholder. Icons
  are now extracted from each executable's own embedded resources at 256×256 —
  deliberately not the usual `ExtractAssociatedIcon`, which only ever returns a
  blurry 32×32. **65 of 68 installed apps** now show their real icon.

Also in this release:

- Registry noise (runtimes, redistributables, drivers, update packages) is
  filtered out of the scan.
- Display names are cleaned of the version/architecture/locale noise the
  registry appends — `"7-Zip 26.03 (x64)"` becomes `7-Zip`.
- Scanned apps get readable slug ids instead of GUIDs, and a category inferred
  by keyword instead of always "Utilities".
- **Icon files are normalized.** Every file in `src/assets/icons/` is now named
  after the catalog id that references it, with no orphans and no duplicate
  content. Previously the scan named files after the *registry* display name,
  so `win-microsoft-visual-studio-code-user.png` was referenced by the entry
  `visual-studio-code` — nothing linked them but the JSON — and every app the
  catalog later dropped left an orphan behind (62 files, 1.4 MB). `build_catalog.py`
  now prunes anything unreferenced.

**Artifacts** (all built and published by CI): `.deb`, `.rpm`, `.AppImage`,
Arch `.pkg.tar.zst`, Flatpak, `.msi`, NSIS `.exe`, and `.dmg`/`.app` for
macOS.

**Known gap (fixed in v0.3.0):** Windows resolution was `$PATH`-only, so Start Menu
shortcuts, the registry `App Paths` key and UWP/Store packages were missed.

> The first v0.2.0 CI run failed the Arch job: the version bump in
> `Cargo.toml` was committed but `Cargo.lock` was regenerated only afterwards,
> so the tagged commit had a stale lock file. The PKGBUILD builds with
> `--locked`, which refuses to update it, so the build aborted. The tag was
> moved forward to the commit with the consistent lock file and all five jobs
> went green. **Lesson: after a version bump, run a build before tagging** so
> `Cargo.lock` is committed alongside `Cargo.toml`.

---

## v0.1.1 — 2026-09-11

Icon rendering fixes:

- Stripped baked-in white backgrounds from app icons, and fixed blurry
  SVG-rasterized icons (rasterize at 128×128 with `-background none`).
- Pointed PlayTorrioMov's launch target at its Flatpak export.

---

## v0.1.0 — 2026-09-08

First release. A categorized launcher dashboard for Linux, fully built out:

- **Core**: Tauri (Rust backend, plain HTML/CSS/JS frontend, no framework, no
  npm build step). Click a tile to launch; CLI tools open inside a terminal.
- **Catalog**: 10 fixed freedesktop-style categories, built offline by merging
  a curated package dataset, hand-written vendor entries, and a scan of the
  machine's own `.desktop` files. The app itself never scans at runtime — it
  does one targeted "is this installed?" check per catalog entry at startup.
- **Search/filter**, responsive multi-column layout that fits one screen without
  scrolling, light/dark via `prefers-color-scheme`.
- **In-app editor**: hide, rename, or recategorize any tile. Edits are stored in
  a per-user `overrides.json`, never written back into the shipped catalog.
- **Dedicated CLI Tools section**, collapsible, with a toggle persisted in
  `localStorage`.
- **Icons**: vendored offline from dashboard-icons, Iconify and KDE's
  breeze-icons, normalized to PNG, with generated category fallback glyphs and a
  dedicated CLI glyph.
- **Windows/macOS code paths** implemented and compiled in CI, but never run on
  real hardware (that gap closed in v0.2.0 for Windows).
- **Packaging and CI**: GitHub Actions builds and publishes installers for
  every platform — `.deb`/`.rpm`/`.AppImage`/Arch `.pkg.tar.zst`/Flatpak on
  Linux, `.msi`/NSIS on Windows, `.dmg`/`.app` on macOS.
- Desktop shortcuts for Linux (`~/Desktop` and the applications menu).
