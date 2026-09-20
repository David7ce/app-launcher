# Flatpak

`dev.d7.app-launcher.json` builds the app **offline**: every Rust crate is listed, with its checksum, in
`cargo-sources.json` (generated from `src-tauri/Cargo.lock`), which is what Flathub requires.

## When `Cargo.lock` changes

Regenerate the list, or the Flatpak build fails (`cargo --offline` can't find the new crate):

```sh
pip install aiohttp PyYAML tomlkit
curl -O https://raw.githubusercontent.com/flatpak/flatpak-builder-tools/f03a673abe6ce189cea1c2857e2b44af2dd79d1f/cargo/flatpak-cargo-generator.py
python flatpak-cargo-generator.py ../../src-tauri/Cargo.lock -o cargo-sources.json
```

CI checks that the committed file still matches `Cargo.lock`.

## Build it locally

```sh
flatpak-builder --user --install --force-clean build dev.d7.app-launcher.json
```
