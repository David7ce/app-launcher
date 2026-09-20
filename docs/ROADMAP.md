# Roadmap

**Pending work only.** For what has already shipped, see
[`RELEASES.md`](RELEASES.md); for the full commit history, `git log`.

Everything that could be finished from the Windows development machine has been. What is left needs
hardware or an OS that isn't available here.

---

## Needs real hardware or a real system

### macOS — never run on real hardware

Every macOS code path is unverified: it is compiled and linted by CI, nothing more.

- [ ] **Run the app on a Mac at all.** `is_installed`, `launch_app` and `get_icon` have only ever
      been compiled, never executed.
- [ ] **Run `tools/scan/macos.py` on real hardware.** It has only passed a
      synthetic-fixture self-test (`--self-test`), which proves the plist-reading logic but says
      nothing about real `/Applications` contents. Its output has never been merged into the
      catalog, and it doesn't stage icons.
- [ ] **Resolve apps by more than an exact bundle name.** `is_installed` looks for a
      case-sensitive `<name>.app` in three directories, which misses anything installed elsewhere
      and gets acronyms wrong (`Vlc` for `VLC`). Needs `mdfind`/Spotlight or a bundle-id lookup.
- [ ] **Verify the `.icns` icon fallback.** It converts `CFBundleIconFile` with `plutil` + `sips`;
      neither has ever run. Apps that ship only an asset catalog (`CFBundleIconName`) have no
      `.icns` and keep the glyph.
- [ ] **Verify CLI tools.** `launch_app` leaves macOS as a bare `open -a` with no terminal
      wrapping, on the untested assumption that CLI tools never show up there (they aren't `.app`
      bundles).

### Packaging — the Windows installer only has been run

CI proves every installer *builds*. Nothing has been installed and launched except the Windows installer
(see `RELEASES.md`).

- [ ] **Install and run the macOS `.dmg`, the Linux `.tar.gz` and the Flatpak** on a real system.

### Linux

- [ ] **Run the icon fallback on a real desktop.** `get_icon` resolves a missing icon from the
      `.desktop` file's `Icon=` through the theme directories (hicolor and breeze layouts, pixmaps,
      Flatpak exports). It is unit-tested against fixture directories and compiled by CI, but has
      not met a real icon theme, and it ignores the user's *active* theme (the scan asks KDE/GNOME
      for it).
- [ ] **Check what the Flatpak can see.** A launcher lists the apps it finds on `$PATH` and in `.desktop`
      files, and inside the Flatpak sandbox that is the sandbox's, not the host's. It probably needs extra
      permissions or `flatpak-spawn --host` to show anything useful. Untested.

## Ongoing, not blocked

Nothing else is queued that can be checked from here. Two things stay manual by design:

- **New Windows apps** found only in the Start Menu are added by hand to `tools/data/vendor_apps.json`
  (then `tools/icons/backfill.py` ships their icons).
- **Icon coverage**: 136 of 440 entries have no shipped icon, almost all Linux-only or macOS-only apps that
  aren't installed on the machine the icons are collected from. On Windows the runtime fallback fills the
  gaps for anything installed; on Linux and macOS that fallback is unverified (see above).
