# Releases

What has actually shipped, newest first. For work not yet done, see
[`ROADMAP.md`](ROADMAP.md).

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

**Known gap:** Windows resolution is still `$PATH`-only, so Start Menu
shortcuts, the registry `App Paths` key and UWP/Store packages are missed. See
`ROADMAP.md`.

**Artifacts** (all built and published by CI, on a re-run — see below):
`.deb`, `.rpm`, `.AppImage`, Arch `.pkg.tar.zst`, Flatpak, `.msi`, NSIS
`.exe`, and `.dmg`/`.app` for macOS.

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
