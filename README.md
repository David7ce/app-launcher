# app-launcher

A simple, categorized home dashboard for launching installed desktop apps — icon + title tiles grouped into fixed categories, no keystroke search, no command palette.

Built with Tauri (Rust backend, plain HTML/CSS/JS frontend, no npm framework). Linux is the fully verified platform; Windows and macOS code paths exist and build in CI but are otherwise untested on real hardware.

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

## Docs

- [`docs/ROADMAP.md`](docs/ROADMAP.md) — phases, current status, what's next.
- [`docs/PLAN.md`](docs/PLAN.md) — the original implementation plan (context, file layout, build steps, verification).
- [`docs/SPEC.md`](docs/SPEC.md) — technical spec: categories, catalog schema, Rust commands, icon pipeline.
