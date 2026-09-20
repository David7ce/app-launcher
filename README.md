# app-launcher

A simple, categorized home dashboard for launching installed desktop apps — icon + title tiles grouped into fixed categories, no keystroke search, no command palette.

Built with Tauri (Rust backend, plain HTML/CSS/JS frontend, no npm framework). Linux and Windows are both verified by running the app; macOS code paths exist and build in CI but are otherwise untested on real hardware.

## Features

- Scans this machine's installed apps (curated dataset + local `.desktop`/registry/`.app`-bundle scan) and shows only what's actually installed, grouped into 10 categories.
- Click a tile to launch; CLI tools launch inside a terminal.
- Live search/filter, responsive multi-column layout.
- In-app editor: hide, rename, or recategorize any tile (stored per-user, doesn't touch the shipped catalog).

## Installing

Download the latest release for your platform from the [Releases page](https://github.com/David7ce/app-launcher/releases):

- **Linux**: `.rpm` (Fedora/openSUSE), `.deb` (Debian/Ubuntu), `.AppImage` (portable, any distro), Arch `.pkg.tar.zst`, or Flatpak `.flatpak`.
- **Windows**: `.msi` or NSIS installer.
- **macOS**: `.dmg`.

## Building from source

Requires Rust, Cargo, and [`tauri-cli`](https://tauri.app):

```sh
cd src-tauri
cargo tauri dev      # run in dev mode
cargo tauri build    # produce installers for this platform (see tauri.conf.json for targets)
```

The catalog (`src/data/catalog.json`) and icons (`src/assets/icons/`) are pre-generated and checked in — see `tools/` if you need to regenerate them.

Tests:

```sh
python -m unittest discover -s tools -p "test_*.py"   # catalog build + scan helpers
cd src-tauri && cargo test                            # Rust unit tests
```

## Docs

- [`docs/RELEASES.md`](docs/RELEASES.md) — what has shipped, per release.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — pending work only.
- [`docs/SPEC.md`](docs/SPEC.md) — technical spec: categories, catalog schema, Rust commands, icon pipeline.

## Third-party assets and licenses

The code is MIT-licensed ([`LICENSE`](LICENSE)). The icons in `src/assets/icons/` are not part of
that grant — they are other people's artwork, used only to identify the app they belong to:

| Source | Used for | License |
|---|---|---|
| [dashboard-icons](https://github.com/homarr-labs/dashboard-icons) | most app icons | Apache-2.0 |
| [Simple Icons](https://github.com/simple-icons/simple-icons) (via Iconify) | brand marks | CC0-1.0 for the collection |
| [KDE breeze-icons](https://github.com/KDE/breeze-icons) | KDE application icons | LGPL-2.1 |
| Extracted from installed apps | icons taken from an app's own executable or package at build time | the app's own license |
| Hand-drawn category and CLI glyphs (`category/`) | the fallback tiles | MIT, like the code |

All product names, logos and trademarks belong to their respective owners; their presence here
implies no affiliation or endorsement. If you are a rights holder and want an icon removed, open
an issue.

## Platform status

| Platform | Status |
|---|---|
| Linux | Verified — full run, launch, icons, packaging |
| Windows | **Verified** — app runs, 68 installed apps detected with real icons, click-to-launch works |
| macOS | Code complete, CI-built only — never run on real hardware |

Run `tools/scan_system_apps_windows.py` on Windows to pick up what's actually
installed on that machine (it reads the registry's Uninstall keys and pulls
each app's own icon out of its `.exe`), then `tools/build_catalog.py`.
