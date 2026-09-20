# Roadmap

**Pending work only.** For what has already shipped, see
[`RELEASES.md`](RELEASES.md); for the full commit history, `git log`.

---

## macOS — never run on real hardware

The largest remaining gap. Every macOS code path is unverified.

- [ ] **Run the app on a Mac at all.** `is_installed` and `launch_app` have
      only ever been compiled in CI, never executed.
- [ ] **Run `tools/scan_system_apps_macos.py` on real hardware.** It has only
      passed a synthetic-fixture self-test (`--self-test`), which proves the
      plist-reading logic works but says nothing about real `/Applications`
      contents. Its output has never been merged into the catalog.
- [ ] **Resolve apps by more than an exact bundle name.** `is_installed` looks
      for a case-sensitive `<name>.app` in exactly three directories. That
      misses anything installed elsewhere, and the catalog's guessed names are
      wrong for acronyms (`Vlc` for `VLC`). Needs `mdfind`/Spotlight or a
      bundle-id lookup.
- [ ] **Verify the `.icns` icon fallback on a Mac.** `get_icon` converts a
      bundle's `CFBundleIconFile` with `plutil` + `sips` at runtime; the path
      logic is compiled and unit-tested, but neither tool has ever run. Apps
      that ship only an asset catalog (`CFBundleIconName`) have no `.icns` and
      keep the glyph, and the *scan* still doesn't stage icons.
- [ ] **Verify CLI tools on macOS.** `launch_app` leaves macOS as a bare
      `open -a` with no terminal wrapping; this is believed unreachable because
      CLI tools aren't `.app` bundles, but that assumption has never been
      tested.

## Windows — remaining gaps

Windows runs, launches apps, and resolves beyond `$PATH` (v0.2.x).

- [ ] **Start Menu apps are added by hand.** Real apps found only in the Start
      Menu are listed in `vendor_apps.json` (36 so far); anything else has to be
      added the same way. Deliberately not added: Windows admin snap-ins
      (Event Viewer, Services, Task Scheduler, Computer Management, ODBC, ...),
      WSL distro launchers (Ubuntu, archlinux) and the individual LibreOffice /
      Blackmagic / Inno Setup shortcuts — say if you want any of them.
- [ ] **Convert `.ico`-only icons properly.** Icons come from the `.exe`'s
      embedded resources, but a DisplayIcon pointing at a standalone `.ico`
      is still only copied, not converted.

## Packaging — nothing has been installed from a real package

CI proves every installer *builds*. None has been installed and launched.

- [ ] **Install and run each artifact on a real system**: `.deb`, `.rpm`,
      Arch `.pkg.tar.zst`, Flatpak, `.msi`/NSIS, `.dmg`. The Linux RPM was
      built and inspected (`rpm -qip`/`-qlp`) but never `rpm -i`'d.
- [ ] **Cut a real version-tagged release and confirm the artifacts.** v0.2.0's
      tag was pushed and all five CI jobs went green, but the resulting
      packages have not been downloaded and tried, and the GitHub Release is
      still a **draft** awaiting manual publishing.
- [ ] **Flathub-compliant Flatpak.** The current manifest builds with network
      access allowed, which is fine for direct `.flatpak` distribution but
      would be rejected by Flathub. Needs an offline/sandboxed rebuild via
      `cargo-sources.json` (`flatpak-cargo-generator.py`).

## Tests — thin

`tools/test_tools.py` (30 cases: catalog merge, icon placement, scan helpers,
catalog invariants) and 10 Rust unit tests (name matching, env expansion,
`.desktop`/theme icon lookup) exist. Still untested:

- [ ] **Launch-command construction per OS** in `launch_app` (it spawns
      directly, so it needs to be split into a pure "build the command" step).
- [ ] **The frontend** (`main.js`) has no automated tests; the editor bug fixed
      after v0.2.0 was found by driving it manually with a mocked Tauri bridge.

## Icons — coverage

- [ ] **150 of 377 catalog entries have no icon file** (15 are CLI tools that
      use the CLI glyph by design, so 135 real gaps) and fall back to the
      category glyph. Most are uninstalled or obscure apps, but the count is
      worth reducing.
- [ ] **Run the Linux icon fallback on a real desktop.** `get_icon` resolves
      a missing icon from the `.desktop` file's `Icon=` through the theme
      directories (both hicolor and breeze layouts, plus pixmaps and Flatpak
      exports). It is unit-tested against fixture directories and compiled by
      CI, but has not been run against a real icon theme, and ignores the
      user's *active* theme (the scan asks KDE/GNOME for it).

## Catalog data quality

- [ ] **Scan-derived ids follow the cleaned name**, so cleaning a name better
      (`win-winmerge-x64-current-user-64-bit` → `win-winmerge`) orphans any
      per-user override saved against the old id. Harmless while there are few
      users; worth pinning ids before a wider release.

## Repo hygiene

- [ ] **Third-party icon attribution.** Icons come from dashboard-icons, Iconify
      and KDE breeze-icons (LGPL); brand logos remain their owners'
      trademarks. `LICENSE` covers the code only — add a short notice to the
      README.
