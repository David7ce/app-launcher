# app-launcher

A simple, categorized home dashboard for launching installed desktop apps — icon + title tiles grouped into fixed categories, with no command palette.

Built with Tauri (Rust backend, plain HTML/CSS/JS frontend, no npm framework). Linux and Windows are both verified by running the app; macOS code paths exist and build in CI but are otherwise untested on real hardware.

## Features

- Shows only the apps actually installed on the machine, grouped into 10 categories. The catalog is built from a curated dataset plus a scan of each OS's own records (`.desktop` files, the Windows registry and Start Menu, `.app` bundles).
- Click a tile to launch it; command-line tools open in a terminal.
- **All / GUI / CLI** filter pills and live search.
- In-app editor: hide, rename or recategorize any tile (stored per user, never touches the shipped catalog).

## Installing

Download from the [Releases page](https://github.com/David7ce/app-launcher/releases):

| Platform                   | File                                                                                                   |
|----------------------------|--------------------------------------------------------------------------------------------------------|
| Windows                    | `app-launcher_<version>_x64-setup.exe` (NSIS installer)                                                |
| macOS (Apple silicon only) | `app-launcher_<version>_aarch64.dmg`                                                                   |
| Linux                      | `app-launcher-<version>-linux-x86_64.tar.gz` (needs GTK 3 and WebKitGTK 4.1) or `app-launcher.flatpak` |

## Building from source

Requires Rust and [`tauri-cli`](https://tauri.app):

```sh
cd src-tauri
cargo tauri dev                    # run in dev mode
cargo tauri build --bundles nsis   # Windows installer (use `dmg` on macOS)
cargo build --release --features custom-protocol   # plain binary, as the Linux tarball uses
```

The catalog (`src/data/catalog.json`) and icons (`src/assets/icons/`) are generated and checked in; `tools/` regenerates them.

```sh
python -m unittest discover -s tools/tests     # catalog build + scan helpers
cd src-tauri && cargo test                     # Rust unit tests
```

## Repository layout

```
src/            the frontend (index.html, main.js, style.css), the catalog and the icons
src-tauri/      the Rust backend and Tauri config; scripts/ holds PowerShell helpers embedded in the binary
tools/          catalog and icon maintenance; never run by the app
  build_catalog.py   merges data/ into src/data/catalog.json
  data/              curated inputs, and the per-OS scan results
  scan/              scan the machine for installed apps (linux.py, windows.py, macos.py)
  icons/             fetch, extract and generate icon files
  tests/             the Python tests
  dev/               drive_app.js: run JS in the real, running window
packaging/      Flatpak manifest and the Linux tarball's files
docs/           RELEASES.md, ROADMAP.md, SPEC.md
```

## Docs

- [`docs/RELEASES.md`](docs/RELEASES.md) — what has shipped, per release.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — pending work only.
- [`docs/SPEC.md`](docs/SPEC.md) — technical spec: categories, catalog schema, Rust commands, icon pipeline.

## Third-party assets and licenses

The code is MIT-licensed ([`LICENSE`](LICENSE)). The icons in `src/assets/icons/` are not part of
that grant — they are other people's artwork, used only to identify the app they belong to:

| Source                                                                     | Used for                                                          | License                    |
|----------------------------------------------------------------------------|-------------------------------------------------------------------|----------------------------|
| [dashboard-icons](https://github.com/homarr-labs/dashboard-icons)          | most app icons                                                    | Apache-2.0                 |
| [Simple Icons](https://github.com/simple-icons/simple-icons) (via Iconify) | brand marks                                                       | CC0-1.0 for the collection |
| [KDE breeze-icons](https://github.com/KDE/breeze-icons)                    | KDE application icons                                             | LGPL-2.1                   |
| Extracted from installed apps                                              | icons taken from an app's own executable or package at build time | the app's own license      |
| Hand-drawn category and CLI glyphs (`category/`)                           | the fallback tiles                                                | MIT, like the code         |

All product names, logos and trademarks belong to their respective owners; their presence here
implies no affiliation or endorsement. If you are a rights holder and want an icon removed, open
an issue.

## Platform status

| Platform | Status                                                                                     |
|----------|--------------------------------------------------------------------------------------------|
| Linux    | Verified — full run, launch, icons, packaging                                              |
| Windows  | **Verified** — app runs, 68 installed apps detected with real icons, click-to-launch works |
| macOS    | Code complete, CI-built only — never run on real hardware                                  |

Run `tools/scan_system_apps_windows.py` on Windows to pick up what's actually
installed on that machine (it reads the registry's Uninstall keys and pulls
each app's own icon out of its `.exe`), then `tools/build_catalog.py`.
