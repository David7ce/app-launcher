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
- [ ] **Fix `cargo tauri build` when run locally on Windows/macOS.**
      `tauri.conf.json` pins `bundle.targets` to `["appimage", "rpm"]`, which
      are Linux-only — so a plain local build on Windows or macOS has no valid
      target. CI is unaffected because it passes `--bundles` explicitly, but a
      local build appears to complete without producing an installer. Needs a
      per-platform default (or documentation telling people to pass
      `--bundles`).
- [ ] **Cut a real version-tagged release and confirm the artifacts.** v0.2.0's
      tag was pushed and all five CI jobs went green, but the resulting
      packages have not been downloaded and tried, and the GitHub Release is
      still a **draft** awaiting manual publishing.
- [ ] **Flathub-compliant Flatpak.** The current manifest builds with network
      access allowed, which is fine for direct `.flatpak` distribution but
      would be rejected by Flathub. Needs an offline/sandboxed rebuild via
      `cargo-sources.json` (`flatpak-cargo-generator.py`).

## Tests — the Rust app has none

The predecessor Python project had 46 `unittest` cases; this one has zero.
The riskiest untested logic is the catalog build (name/category joining, scan
merging, icon placement) and the per-OS resolution in `lib.rs`.

- [ ] **Add tests for `build_catalog.py`**: `normalize_name` joining, the
      Windows basename/name merge, `place_scan_icons` pruning, `EXCLUDED_IDS`.
- [ ] **Add tests for `lib.rs`**: `PlatformBin::for_current_os`, and the
      launch-command construction per OS.

## Icons — coverage

- [ ] **162 of 383 catalog entries have no icon file** and fall back to the
      category glyph. Most are uninstalled or obscure apps, but the count is
      worth reducing.
