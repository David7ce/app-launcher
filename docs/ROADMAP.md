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
- [ ] **Extract `.icns` icons.** macOS apps currently all fall back to the
      category glyph. Needs `.icns` → PNG conversion (an `sips`/`iconutil`
      step, or a pure-Python reader).
- [ ] **Verify CLI tools on macOS.** `launch_app` leaves macOS as a bare
      `open -a` with no terminal wrapping; this is believed unreachable because
      CLI tools aren't `.app` bundles, but that assumption has never been
      tested.

## Windows — remaining gaps

Windows runs, launches apps, and resolves beyond `$PATH` (v0.2.x).

- [ ] **Resolve Start Menu shortcuts and UWP/Store packages.** The registry's
      `App Paths` key is now consulted, which covers most classic GUI
      installers, but Start Menu `.lnk` targets and `shell:AppsFolder`
      packages are still missed. On this machine that is ~19 further apps
      (Discord, LibreOffice, Node.js, QGIS, KeePassXC, VirtualBox, ...).
- [ ] **Verify the `cmd /k` CLI-tool path** on real hardware. Written by
      analogy with the Linux terminal wrapping, never exercised.
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

`tools/test_tools.py` (22 cases: catalog merge, icon placement, scan helpers,
catalog invariants) and four `lib.rs` unit tests exist. Still untested:

- [ ] **Launch-command construction per OS** in `launch_app` (it spawns
      directly, so it needs to be split into a pure "build the command" step).
- [ ] **The frontend** (`main.js`) has no automated tests; the editor bug fixed
      after v0.2.0 was found by driving it manually with a mocked Tauri bridge.

## Icons — coverage

- [ ] **150 of 383 catalog entries have no icon file** (17 are CLI tools that
      use the CLI glyph by design, so 135 real gaps) and fall back to the
      category glyph. Most are uninstalled or obscure apps, but the count is
      worth reducing.
- [ ] **Local icon fallback on Linux and macOS.** On Windows an installed app
      with no shipped icon now gets one extracted from its exe at runtime
      (`get_icon`). Linux (`.desktop` `Icon=` theme lookup) and macOS (`.icns`
      conversion) still just show the category glyph.

## Catalog data quality

- [ ] **Scan name cleaning still leaks noise**: `WinMerge x64 (Current user,
      64-bit)`, `Tesseract-OCR - open source OCR engine`. Non-apps also slip
      through the scan (`Inno Setup`, `OpenAL`) — extend
      `NON_APP_NAME_PATTERNS`/`EXCLUDED_IDS`.
- [ ] **AdGuard is no longer picked up by the scan**: its `DisplayIcon` is a
      cached installer and no matching exe sits beside it or in
      `InstallLocation`. Needs a Start Menu / App Paths lookup (same gap as the
      Windows resolution item above).

## Repo hygiene

- [ ] **Confirm the new `ci.yml` is green on Linux and macOS.** It was added
      after `windows_registry_lookup` was found to be `#[cfg(windows)]` yet
      called unguarded — a compile break on Linux/macOS since 59fca7e that a
      Windows-only machine could not reproduce. A `cfg(not(windows))` stub now
      fixes it, but that has only been reasoned about, not compiled, off
      Windows.
- [ ] **Third-party icon attribution.** Icons come from dashboard-icons, Iconify
      and KDE breeze-icons (LGPL); brand logos remain their owners'
      trademarks. `LICENSE` covers the code only — add a short notice to the
      README.
