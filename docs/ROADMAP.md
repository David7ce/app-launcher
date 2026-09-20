# Roadmap

**Pending work only.** For what has already shipped, see
[`RELEASES.md`](RELEASES.md); for the full commit history, `git log`.

Everything that could be finished from the Windows development machine has been. What is left
either needs hardware or an OS that isn't available here, or is a larger piece of work that hasn't
been started.

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

### Packaging — nothing has been installed from a real package

CI proves every installer *builds*; none has been installed and launched.

- [ ] **Install and run each artifact** on a real system: the Windows NSIS installer, the macOS
      `.dmg`, the Linux `.tar.gz` and the Flatpak. CI proves they build; the v0.3.0 `.deb` was
      inspected (contents and dependencies) but nothing has been installed and launched.

### Linux

- [ ] **Run the icon fallback on a real desktop.** `get_icon` resolves a missing icon from the
      `.desktop` file's `Icon=` through the theme directories (hicolor and breeze layouts, pixmaps,
      Flatpak exports). It is unit-tested against fixture directories and compiled by CI, but has
      not met a real icon theme, and it ignores the user's *active* theme (the scan asks KDE/GNOME
      for it).

## Could be done next

- [ ] **Flathub-compliant Flatpak.** The manifest builds with network access allowed, fine for a
      direct `.flatpak` but rejected by Flathub. It needs an offline, sandboxed build via
      `cargo-sources.json` (`flatpak-cargo-generator.py`). Only worth doing to submit to Flathub.
- [ ] **Frontend tests.** `main.js` has none. The pills, the column layout, the editor and the
      override migration were verified by driving the real app (`tools/dev/drive_app.js`) and earlier
      with a mocked Tauri bridge, but nothing re-runs that in CI.
- [ ] **More Windows apps by name.** Apps found only in the Start Menu are listed by hand in
      `tools/data/vendor_apps.json`. Deliberately not added: Windows admin snap-ins (Event
      Viewer, Services, Task Scheduler, Computer Management, ODBC, ...), WSL distro launchers
      (Ubuntu, archlinux) and individual LibreOffice / Blackmagic / Inno Setup shortcuts.
- [ ] **Icon coverage.** 181 of 408 catalog entries have no shipped icon (25 of them CLI tools,
      which use the CLI glyph by design). Most are apps that weren't installed on the machine the
      icons were collected from. On Windows the runtime fallback fills the gaps for anything that
      *is* installed; on Linux and macOS that fallback is unverified (see above), so those tiles
      may show the category glyph.
