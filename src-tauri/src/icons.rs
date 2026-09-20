//! Fallback icons for installed apps whose icon is not shipped with the app.
//!
//! Shipped icons (`src/assets/icons/`) stay the primary source: they are
//! deterministic and identical everywhere. This only fills the gaps, from the
//! installed app itself, and returns a `data:` URL (which the CSP allows):
//!
//! - Windows: extract the exe's own icon with PowerShell, cached as a PNG.
//! - Linux: find the `.desktop` file whose `Exec=` launches the binary and
//!   resolve its `Icon=` through the icon theme directories.
//! - macOS: convert the bundle's `.icns` to PNG with the built-in `sips`,
//!   cached. Unverified — never run on real macOS.
//!
//! Everything except the actual PowerShell/`sips` invocations is plain path
//! logic compiled on every OS, so it is unit-tested wherever the tests run.

use crate::{
    macos_bundle_path, start_app_exe, start_menu_name, windows_resolve, windows_start_app, PlatformBin,
};
use base64::Engine;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::Manager;

/// Bigger than any sensible app icon; refuse rather than ship a huge data URL.
const MAX_ICON_BYTES: u64 = 1_500_000;

/// Where extracted icons are cached, under the app cache dir. Bump the version
/// whenever an extractor's *output* changes (v2: the Start Menu extractor used to
/// return images upside down), or icons cached by the old code would stay wrong.
const CACHE_DIR: &str = "icons-v2";

const RETRY_FAILED_AFTER: std::time::Duration = std::time::Duration::from_secs(7 * 24 * 60 * 60);

fn data_url(mime: &str, bytes: &[u8]) -> String {
    let b64 = base64::engine::general_purpose::STANDARD.encode(bytes);
    format!("data:{mime};base64,{b64}")
}

/// `data:` URL for a PNG or SVG file; anything else (`.xpm`, ...) is skipped.
fn file_data_url(path: &Path) -> Option<String> {
    let mime = match path.extension()?.to_str()?.to_ascii_lowercase().as_str() {
        "png" => "image/png",
        "svg" => "image/svg+xml",
        _ => return None,
    };
    if fs::metadata(path).ok()?.len() > MAX_ICON_BYTES {
        return None;
    }
    Some(data_url(mime, &fs::read(path).ok()?))
}

/// PNG cached under the app cache dir, produced once by `generate(dir, png)`.
/// A failure leaves a `<id>.none` marker so it isn't retried on every launch.
fn cached_png(
    app: &tauri::AppHandle,
    id: &str,
    generate: impl FnOnce(&Path, &Path) -> bool,
) -> Option<Vec<u8>> {
    let dir = app.path().app_cache_dir().ok()?.join(CACHE_DIR);
    fs::create_dir_all(&dir).ok()?;
    let safe: String = id
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() || c == '-' { c } else { '_' })
        .collect();
    let png = dir.join(format!("{safe}.png"));
    let none = dir.join(format!("{safe}.none"));
    // A failure is remembered so it isn't retried on every launch, but only
    // for a week: it may have been transient, or something a newer version
    // of the app can now handle.
    let recently_failed = none
        .metadata()
        .and_then(|m| m.modified())
        .is_ok_and(|t| t.elapsed().is_ok_and(|age| age < RETRY_FAILED_AFTER));
    if recently_failed {
        return None;
    }
    if !png.is_file() && !(generate(&dir, &png) && png.is_file()) {
        let _ = fs::write(&none, "");
        return None;
    }
    fs::read(&png).ok()
}

/// Entry point: the icon for an installed app, or `None` to keep the category
/// glyph. `name` is the catalog display name, used on Windows to find apps
/// that only exist in the Start Menu.
pub fn fallback(
    app: &tauri::AppHandle,
    id: &str,
    bin: &PlatformBin,
    name: Option<&str>,
) -> Option<String> {
    match std::env::consts::OS {
        "windows" => windows(app, id, bin, name),
        "linux" => linux(bin.linux.as_deref()?),
        "macos" => macos(app, id, bin.macos.as_deref()?),
        _ => None,
    }
}

// ---------------------------------------------------------------- Windows

fn windows(app: &tauri::AppHandle, id: &str, bin: &PlatformBin, name: Option<&str>) -> Option<String> {
    // Found by exe path, or only through the Start Menu.
    // A `WindowsApps` exe is an app-execution alias for a packaged app (wt.exe,
    // python.exe): a 0-byte reparse point with no icon resource of its own, so
    // it goes through the package route below instead.
    let exe = bin
        .windows
        .as_deref()
        .and_then(windows_resolve)
        .filter(|p| !p.to_string_lossy().contains("\\WindowsApps\\"));
    let target = bin.windows.as_deref().unwrap_or("");
    let start_id = || start_menu_name(target, name).and_then(windows_start_app);
    let bytes = match exe.or_else(|| start_id().and_then(start_app_exe)) {
        Some(exe) => cached_png(app, id, |dir, png| extract_exe_icon(&exe, dir, png))?,
        // No exe behind it. A packaged (MSIX/UWP/Store) app has an AppID of
        // `<family>!<app>` and its logo in the package manifest; failing that
        // (or for a classic app registered by bare AppID, or a system tool)
        // the shell can still render the Start tile.
        None => {
            let app_id = start_id()?;
            cached_png(app, id, |dir, png| {
                (app_id.contains('!') && extract_appx_icon(app_id, dir, png))
                    || extract_start_icon(app_id, dir, png)
            })?
        }
    };
    Some(data_url("image/png", &bytes))
}

#[cfg(windows)]
fn extract_exe_icon(exe: &Path, dir: &Path, png: &Path) -> bool {
    use std::sync::OnceLock;
    static SCRIPT: OnceLock<Option<PathBuf>> = OnceLock::new();
    run_script(&SCRIPT, dir, "extract_icon.ps1", include_str!("../scripts/extract_icon.ps1"), &[
        "-Exe".as_ref(),
        exe.as_os_str(),
        "-Out".as_ref(),
        png.as_os_str(),
    ])
}

#[cfg(windows)]
fn extract_appx_icon(app_id: &str, dir: &Path, png: &Path) -> bool {
    use std::sync::OnceLock;
    static SCRIPT: OnceLock<Option<PathBuf>> = OnceLock::new();
    run_script(&SCRIPT, dir, "extract_appx_icon.ps1", include_str!("../scripts/extract_appx_icon.ps1"), &[
        "-AppId".as_ref(),
        app_id.as_ref(),
        "-Out".as_ref(),
        png.as_os_str(),
    ])
}

#[cfg(windows)]
fn extract_start_icon(app_id: &str, dir: &Path, png: &Path) -> bool {
    use std::sync::OnceLock;
    static SCRIPT: OnceLock<Option<PathBuf>> = OnceLock::new();
    run_script(&SCRIPT, dir, "extract_start_icon.ps1", include_str!("../scripts/extract_start_icon.ps1"), &[
        "-AppId".as_ref(),
        app_id.as_ref(),
        "-Out".as_ref(),
        png.as_os_str(),
    ])
}

/// Run one of the bundled PowerShell scripts with a hidden window. The script
/// is written into the cache dir once per run (`cell`): parallel first-time
/// extractions would otherwise rewrite it while another PowerShell reads it.
#[cfg(windows)]
fn run_script(
    cell: &'static std::sync::OnceLock<Option<PathBuf>>,
    dir: &Path,
    file: &str,
    body: &str,
    args: &[&std::ffi::OsStr],
) -> bool {
    use std::os::windows::process::CommandExt;
    let Some(script) = cell.get_or_init(|| {
        let path = dir.join(file);
        fs::write(&path, body).ok().map(|_| path)
    }) else {
        return false;
    };
    Command::new("powershell")
        .args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"])
        .arg(script)
        .args(args)
        .creation_flags(crate::CREATE_NO_WINDOW)
        .status()
        .is_ok_and(|s| s.success())
}

#[cfg(not(windows))]
fn extract_exe_icon(_exe: &Path, _dir: &Path, _png: &Path) -> bool {
    false
}

#[cfg(not(windows))]
fn extract_appx_icon(_app_id: &str, _dir: &Path, _png: &Path) -> bool {
    false
}

#[cfg(not(windows))]
fn extract_start_icon(_app_id: &str, _dir: &Path, _png: &Path) -> bool {
    false
}

// ------------------------------------------------------------------ Linux

fn home() -> Option<PathBuf> {
    std::env::var_os("HOME").map(PathBuf::from)
}

/// `$XDG_DATA_HOME` and `$XDG_DATA_DIRS` (with their spec defaults), plus the
/// Flatpak export directories, which are not always listed in the latter.
fn xdg_data_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    match std::env::var_os("XDG_DATA_HOME").filter(|v| !v.is_empty()) {
        Some(v) => dirs.push(PathBuf::from(v)),
        None => dirs.extend(home().map(|h| h.join(".local/share"))),
    }
    let system = std::env::var("XDG_DATA_DIRS")
        .ok()
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| "/usr/local/share:/usr/share".to_string());
    dirs.extend(system.split(':').filter(|d| !d.is_empty()).map(PathBuf::from));
    dirs.push(PathBuf::from("/var/lib/flatpak/exports/share"));
    dirs.extend(home().map(|h| h.join(".local/share/flatpak/exports/share")));
    dirs
}

/// The `Icon=` value of the `.desktop` file whose `Exec=` launches `bin`
/// (matched on the executable's file name). Only the `[Desktop Entry]` group
/// is read, so an `Exec=` under a `[Desktop Action ...]` can't be mistaken for
/// the main one.
pub fn desktop_icon_name(desktop_dirs: &[PathBuf], bin: &str) -> Option<String> {
    let want = Path::new(bin).file_name()?.to_str()?;
    for dir in desktop_dirs {
        let Ok(entries) = fs::read_dir(dir) else { continue };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("desktop") {
                continue;
            }
            let Ok(text) = fs::read_to_string(&path) else { continue };
            let (mut exec, mut icon, mut in_main) = (None, None, false);
            for line in text.lines().map(str::trim) {
                if line.starts_with('[') {
                    in_main = line == "[Desktop Entry]";
                } else if in_main {
                    if let Some(v) = line.strip_prefix("Exec=") {
                        exec.get_or_insert(v);
                    } else if let Some(v) = line.strip_prefix("Icon=") {
                        icon.get_or_insert(v);
                    }
                }
            }
            let (Some(exec), Some(icon)) = (exec, icon) else { continue };
            // First real token: skip an `env VAR=x` prefix and quotes.
            let launcher = exec
                .split_whitespace()
                .find(|t| *t != "env" && !t.contains('='))
                .map(|t| t.trim_matches('"'));
            let exec_name = launcher.and_then(|t| Path::new(t).file_name()?.to_str());
            if exec_name == Some(want) && !icon.is_empty() {
                return Some(icon.to_string());
            }
        }
    }
    None
}

/// Resolve an `Icon=` value to a file. An absolute path is used as is; a
/// theme icon name is looked up under each icon directory, in both layouts seen
/// in the wild (hicolor-style `<theme>/<size>/apps/` and breeze-style
/// `<theme>/apps/<size>/`), largest first, falling back to `pixmaps`.
pub fn resolve_theme_icon(name: &str, icon_dirs: &[PathBuf], pixmaps: &Path) -> Option<PathBuf> {
    let direct = Path::new(name);
    if direct.is_absolute() {
        return direct.is_file().then(|| direct.to_path_buf());
    }
    const SIZES: &[&str] = &[
        "scalable", "512x512", "512", "256x256", "256", "128x128", "128", "96x96", "96",
        "64x64", "64", "48x48", "48",
    ];
    const PREFERRED: &[&str] = &["hicolor", "breeze", "breeze-dark", "Adwaita"];
    for base in icon_dirs {
        let mut themes: Vec<String> = PREFERRED.iter().map(|t| t.to_string()).collect();
        if let Ok(entries) = fs::read_dir(base) {
            let mut others: Vec<String> = entries
                .flatten()
                .filter_map(|e| e.file_name().into_string().ok())
                .filter(|t| !PREFERRED.contains(&t.as_str()))
                .collect();
            others.sort();
            themes.extend(others);
        }
        for theme in themes {
            for size in SIZES {
                for ext in ["png", "svg"] {
                    let file = format!("{name}.{ext}");
                    for candidate in [
                        base.join(&theme).join(size).join("apps").join(&file),
                        base.join(&theme).join("apps").join(size).join(&file),
                    ] {
                        if candidate.is_file() {
                            return Some(candidate);
                        }
                    }
                }
            }
        }
    }
    ["png", "svg"]
        .iter()
        .map(|ext| pixmaps.join(format!("{name}.{ext}")))
        .find(|p| p.is_file())
}

fn linux(bin: &str) -> Option<String> {
    let desktop_dirs: Vec<PathBuf> = xdg_data_dirs().iter().map(|d| d.join("applications")).collect();
    let mut icon_dirs: Vec<PathBuf> = home().into_iter().flat_map(|h| [h.join(".local/share/icons"), h.join(".icons")]).collect();
    icon_dirs.extend(xdg_data_dirs().iter().map(|d| d.join("icons")));
    let icon = desktop_icon_name(&desktop_dirs, bin)?;
    file_data_url(&resolve_theme_icon(&icon, &icon_dirs, Path::new("/usr/share/pixmaps"))?)
}


// ------------------------------------------------------------------ macOS

/// The bundle's `CFBundleIconFile` as a path under `Contents/Resources`.
/// Apps that ship only an asset catalog (`CFBundleIconName`) have no `.icns`.
fn macos_icns(bundle: &Path) -> Option<PathBuf> {
    let out = Command::new("plutil")
        .args(["-convert", "json", "-o", "-"])
        .arg(bundle.join("Contents/Info.plist"))
        .output()
        .ok()?;
    let plist: serde_json::Value = serde_json::from_slice(&out.stdout).ok()?;
    let mut file = plist.get("CFBundleIconFile")?.as_str()?.to_string();
    if Path::new(&file).extension().is_none() {
        file.push_str(".icns");
    }
    let path = bundle.join("Contents/Resources").join(file);
    path.is_file().then_some(path)
}

fn macos(app: &tauri::AppHandle, id: &str, name: &str) -> Option<String> {
    let bundle = macos_bundle_path(name)?;
    let bytes = cached_png(app, id, |_dir, png| {
        macos_icns(&bundle).is_some_and(|icns| {
            Command::new("sips")
                .args(["-s", "format", "png", "-Z", "256"])
                .arg(icns)
                .arg("--out")
                .arg(png)
                .status()
                .is_ok_and(|s| s.success())
        })
    })?;
    Some(data_url("image/png", &bytes))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A scratch directory unique to this test run, removed on drop.
    struct Scratch(PathBuf);
    impl Scratch {
        fn new(tag: &str) -> Self {
            let dir = std::env::temp_dir().join(format!("app-launcher-{}-{tag}", std::process::id()));
            let _ = fs::remove_dir_all(&dir);
            fs::create_dir_all(&dir).unwrap();
            Scratch(dir)
        }
        fn write(&self, rel: &str, body: &str) -> PathBuf {
            let path = self.0.join(rel);
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(&path, body).unwrap();
            path
        }
    }
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn desktop_icon_is_found_by_exec_basename_and_ignores_actions() {
        let s = Scratch::new("desktop");
        s.write(
            "applications/org.kde.okular.desktop",
            "[Desktop Entry]\nName=Okular\nExec=/usr/bin/okular %U\nIcon=okular\n\n\
             [Desktop Action New]\nExec=/usr/bin/other\nIcon=wrong\n",
        );
        s.write(
            "applications/wrapped.desktop",
            "[Desktop Entry]\nExec=env FOO=1 \"/opt/x/tool\" --flag\nIcon=tool-icon\n",
        );
        let dirs = [s.0.join("applications"), s.0.join("missing")];
        assert_eq!(desktop_icon_name(&dirs, "okular").as_deref(), Some("okular"));
        assert_eq!(desktop_icon_name(&dirs, "/usr/bin/okular").as_deref(), Some("okular"));
        assert_eq!(desktop_icon_name(&dirs, "tool").as_deref(), Some("tool-icon"));
        assert_eq!(desktop_icon_name(&dirs, "other"), None); // only in a Desktop Action
        assert_eq!(desktop_icon_name(&dirs, "nothing"), None);
    }

    #[test]
    fn theme_icon_handles_both_layouts_absolute_paths_and_pixmaps() {
        let s = Scratch::new("theme");
        s.write("icons/hicolor/48x48/apps/small.png", "x");
        s.write("icons/hicolor/256x256/apps/small.png", "x");
        s.write("icons/breeze/apps/64/kate.svg", "<svg/>");
        s.write("pixmaps/legacy.png", "x");
        let abs = s.write("abs/icon.png", "x");
        let icons = [s.0.join("icons")];
        let pixmaps = s.0.join("pixmaps");

        let found = resolve_theme_icon("small", &icons, &pixmaps).unwrap();
        assert!(found.ends_with("256x256/apps/small.png") || found.ends_with("256x256\\apps\\small.png"));
        assert!(resolve_theme_icon("kate", &icons, &pixmaps).unwrap().to_string_lossy().contains("kate.svg"));
        assert!(resolve_theme_icon("legacy", &icons, &pixmaps).is_some());
        assert_eq!(resolve_theme_icon(abs.to_str().unwrap(), &icons, &pixmaps), Some(abs));
        assert!(resolve_theme_icon("nope", &icons, &pixmaps).is_none());
    }

    #[test]
    fn file_data_url_picks_mime_from_extension_and_skips_unknown_types() {
        let s = Scratch::new("mime");
        let svg = s.write("a.svg", "<svg/>");
        let xpm = s.write("a.xpm", "x");
        assert!(file_data_url(&svg).unwrap().starts_with("data:image/svg+xml;base64,"));
        assert!(file_data_url(&s.write("a.png", "x")).unwrap().starts_with("data:image/png;base64,"));
        assert!(file_data_url(&xpm).is_none());
    }
}
