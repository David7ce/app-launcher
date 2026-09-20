use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::Manager;

/// Per-OS launch identifier for a catalog entry. Any field can be absent —
/// absent means the app doesn't exist on that OS, so `is_installed` returns
/// false without checking anything, giving "only show installed" for free.
#[derive(serde::Deserialize)]
struct PlatformBin {
    linux: Option<String>,
    windows: Option<String>,
    macos: Option<String>,
}

impl PlatformBin {
    fn for_current_os(&self) -> Option<&str> {
        match std::env::consts::OS {
            "linux" => self.linux.as_deref(),
            "windows" => self.windows.as_deref(),
            "macos" => self.macos.as_deref(),
            _ => None,
        }
    }
}

/// macOS has no $PATH for GUI apps — check for a `<name>.app` bundle in the
/// usual install locations instead. Exact, case-sensitive match only; no
/// Spotlight/mdfind fuzzy lookup. Unverified: never run on real macOS.
fn macos_app_installed(name: &str) -> bool {
    let mut dirs = vec![
        "/Applications".to_string(),
        "/System/Applications".to_string(),
    ];
    if let Ok(home) = std::env::var("HOME") {
        dirs.push(format!("{home}/Applications"));
    }
    dirs.iter().any(|dir| Path::new(dir).join(format!("{name}.app")).exists())
}

/// Windows: resolve a bare executable name the way the `Run` dialog and
/// `start` do — via the registry's App Paths key. Most GUI installers
/// (Office, VLC, Inkscape) register themselves here and *not* on $PATH, so a
/// PATH-only search reports them as not installed and they never appear.
/// Both the 64-bit and 32-bit (WOW6432Node) views are checked, for the
/// current user and the whole machine. Returns the full executable path.
#[cfg(windows)]
fn windows_registry_lookup(name: &str) -> Option<PathBuf> {
    use winreg::enums::{HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, KEY_READ};
    use winreg::RegKey;

    const APP_PATHS: &str =
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths";
    const APP_PATHS_WOW: &str =
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths";

    // The key is named after the executable, so a bare "vlc" has to be tried
    // as "vlc.exe" — but a name that already carries the extension must not
    // become "vlc.exe.exe".
    let exe = if name.to_ascii_lowercase().ends_with(".exe") {
        name.to_string()
    } else {
        format!("{name}.exe")
    };

    for (hive, sub) in [
        (HKEY_CURRENT_USER, APP_PATHS),
        (HKEY_LOCAL_MACHINE, APP_PATHS),
        (HKEY_LOCAL_MACHINE, APP_PATHS_WOW),
    ] {
        let Ok(root) = RegKey::predef(hive).open_subkey_with_flags(sub, KEY_READ) else {
            continue;
        };
        let Ok(key) = root.open_subkey_with_flags(&exe, KEY_READ) else {
            continue;
        };
        // The default value is the full path. It is usually unquoted but
        // often contains spaces ("C:\Program Files\VideoLAN\VLC\vlc.exe"),
        // and occasionally carries a trailing argument. So: try the whole
        // string first, and only fall back to taking the leading token.
        // Splitting on whitespace up front would truncate every unquoted
        // path at the first space — "C:\Program" — and silently report an
        // installed app as missing.
        let Ok(raw) = key.get_value::<String, _>("") else {
            continue;
        };
        let raw = raw.trim();
        let unquoted = raw
            .strip_prefix('"')
            .and_then(|rest| rest.split('"').next())
            .unwrap_or(raw);

        let mut candidates = vec![unquoted];
        if let Some(first) = raw.split_whitespace().next() {
            if first != unquoted {
                candidates.push(first);
            }
        }
        if let Some(path) = candidates
            .into_iter()
            .map(PathBuf::from)
            .find(|p| p.is_file())
        {
            return Some(path);
        }
    }
    None
}

// Only Windows has an App Paths key; the callers below are not cfg-gated (they
// branch on `consts::OS` at runtime), so every other OS needs a stub to compile.
#[cfg(not(windows))]
fn windows_registry_lookup(_name: &str) -> Option<PathBuf> {
    None
}

/// Expand `%VAR%` references so the catalog can carry per-user paths such as
/// `%LOCALAPPDATA%\Programs\Foo\foo.exe` instead of one machine's
/// `C:\Users\<name>\...`. Unknown variables are left untouched.
fn expand_env(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut rest = s;
    while let Some(start) = rest.find('%') {
        out.push_str(&rest[..start]);
        let after = &rest[start + 1..];
        let Some(end) = after.find('%') else {
            out.push('%');
            rest = after;
            break;
        };
        let var = &after[..end];
        match std::env::var(var) {
            Ok(value) if !var.is_empty() => out.push_str(&value),
            _ => {
                out.push('%');
                out.push_str(var);
                out.push('%');
            }
        }
        rest = &after[end + 1..];
    }
    out.push_str(rest);
    out
}

/// Windows: turn a catalog `bin` into a real executable path. An absolute
/// path (what the system scan produces) just has to exist; a bare name is
/// searched on $PATH and then in the registry's App Paths key. `which` is
/// Windows-aware (checks PATHEXT, so a bare "git" resolves "git.exe").
fn windows_resolve(name: &str) -> Option<PathBuf> {
    let name = expand_env(name);
    if name.contains('\\') || name.contains('/') {
        let path = PathBuf::from(&name);
        return path.is_file().then_some(path);
    }
    which::which(&name).ok().or_else(|| windows_registry_lookup(&name))
}

// `async` makes Tauri run these on its thread pool: a plain command runs on the
// main thread, and the frontend fires one `is_installed` per catalog entry
// (~380) at startup, each a PATH search plus registry reads on Windows.
#[tauri::command(async)]
fn is_installed(bin: PlatformBin) -> bool {
    let Some(name) = bin.for_current_os() else {
        return false;
    };
    match std::env::consts::OS {
        "macos" => macos_app_installed(name),
        "windows" => windows_resolve(name).is_some(),
        // Linux: $PATH only, which is how desktop apps are launched there.
        _ => which::which(name).is_ok(),
    }
}

#[cfg(windows)]
mod local_icon {
    use super::{windows_resolve, PlatformBin};
    use base64::Engine;
    use std::fs;
    use std::os::windows::process::CommandExt;
    use std::path::{Path, PathBuf};
    use std::process::Command;
    use std::sync::OnceLock;
    use tauri::Manager;

    const SCRIPT: &str = include_str!("extract_icon.ps1");
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;

    /// Written once per run: parallel first-time extractions would otherwise
    /// rewrite the file while another PowerShell is reading it.
    fn script_path(dir: &Path) -> Option<&'static PathBuf> {
        static PATH: OnceLock<Option<PathBuf>> = OnceLock::new();
        PATH.get_or_init(|| {
            let path = dir.join("extract_icon.ps1");
            fs::write(&path, SCRIPT).ok().map(|_| path)
        })
        .as_ref()
    }

    /// Icon for a tile that has none shipped, pulled from the installed
    /// executable itself and cached under the app cache dir as a PNG. A
    /// failure leaves a `.none` marker so it isn't retried on every launch.
    pub fn data_url(app: &tauri::AppHandle, id: &str, bin: &PlatformBin) -> Option<String> {
        let exe = windows_resolve(bin.windows.as_deref()?)?;
        let dir = app.path().app_cache_dir().ok()?.join("icons");
        fs::create_dir_all(&dir).ok()?;
        let safe: String = id
            .chars()
            .map(|c| if c.is_ascii_alphanumeric() || c == '-' { c } else { '_' })
            .collect();
        let png = dir.join(format!("{safe}.png"));
        let none = dir.join(format!("{safe}.none"));
        if none.exists() {
            return None;
        }
        if !png.is_file() {
            let ok = script_path(&dir).is_some_and(|script| {
                Command::new("powershell")
                    .args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"])
                    .arg(script)
                    .arg("-Exe")
                    .arg(&exe)
                    .arg("-Out")
                    .arg(&png)
                    .creation_flags(CREATE_NO_WINDOW)
                    .status()
                    .is_ok_and(|s| s.success())
            });
            if !ok || !png.is_file() {
                let _ = fs::write(&none, "");
                return None;
            }
        }
        let bytes = fs::read(&png).ok()?;
        let b64 = base64::engine::general_purpose::STANDARD.encode(bytes);
        Some(format!("data:image/png;base64,{b64}"))
    }
}

/// Fallback icon for an installed app whose shipped icon is missing. Only
/// implemented for Windows (extracted from the exe); elsewhere `None` keeps
/// the category glyph. Returns a `data:` URL, which the CSP already allows.
#[tauri::command(async)]
fn get_icon(app: tauri::AppHandle, id: String, bin: PlatformBin) -> Option<String> {
    #[cfg(windows)]
    {
        local_icon::data_url(&app, &id, &bin)
    }
    #[cfg(not(windows))]
    {
        let _ = (app, id, bin);
        None
    }
}

/// A CLI tool spawned bare has no terminal attached, so it either exits
/// instantly or produces output nobody sees — "clicking it does nothing"
/// from the user's side. Open one of the common terminal emulators instead,
/// running the tool inside it and dropping to a shell afterwards (via
/// `bash -c "<bin>; ...; read"`) so the window doesn't vanish the instant a
/// quick command like `tree` finishes. Tried in a fixed order; the first
/// one actually installed wins.
fn linux_terminal_spawn(bin: &str) -> std::io::Result<std::process::Child> {
    const TERMINALS: &[(&str, &str)] = &[
        ("konsole", "-e"),
        ("gnome-terminal", "--"),
        ("xfce4-terminal", "-e"),
        ("alacritty", "-e"),
        ("kitty", "-e"),
    ];
    let hold_cmd = format!("{bin}; echo; read -n1 -s -r -p 'Press any key to close...'");
    for (terminal, flag) in TERMINALS {
        if which::which(terminal).is_ok() {
            return Command::new(terminal)
                .arg(flag)
                .args(["bash", "-c", &hold_cmd])
                .spawn();
        }
    }
    // xterm's `-hold` keeps the window open after the command exits, no
    // need for the bash/read wrapper — kept as the last resort since it's
    // the least likely to already be installed on a modern desktop.
    if which::which("xterm").is_ok() {
        return Command::new("xterm").args(["-hold", "-e", bin]).spawn();
    }
    Err(std::io::Error::new(
        std::io::ErrorKind::NotFound,
        "no terminal emulator found (tried konsole, gnome-terminal, xfce4-terminal, alacritty, kitty, xterm)",
    ))
}

#[tauri::command(async)]
fn launch_app(bin: PlatformBin, cli: bool) -> Result<(), String> {
    let Some(name) = bin.for_current_os() else {
        return Err("no launch command configured for this OS".to_string());
    };
    let result = match std::env::consts::OS {
        // The standard way to launch a macOS app by name regardless of its
        // exact path. Unverified: never run on real macOS. CLI tools aren't
        // given the terminal-wrapping treatment here — is_installed's
        // .app-bundle check means a bare CLI tool essentially never shows
        // as installed on macOS anyway, so this path is rarely reached.
        "macos" => Command::new("open").args(["-a", name]).spawn(),
        "linux" if cli => linux_terminal_spawn(name),
        // cmd /k runs the command and stays open at an interactive prompt
        // afterwards, same idea as the Linux bash/read wrapper. Unverified
        // on real Windows.
        "windows" if cli => Command::new("cmd").args(["/k", &expand_env(name)]).spawn(),
        "windows" => {
            // Resolve to a full path first: an app registered only in the
            // registry's App Paths key (Office, VLC, Inkscape) is invisible
            // to a bare `Command::new("vlc.exe")`, which would fail with
            // "not found" even though `is_installed` just said it exists.
            let target = windows_resolve(name).unwrap_or_else(|| PathBuf::from(expand_env(name)));
            Command::new(target).spawn()
        }
        _ => Command::new(name).spawn(),
    };
    result
        .map(|_| ())
        .map_err(|e| format!("failed to launch '{name}': {e}"))
}

// User edits (hide/rename/recategorize) can't be written back into
// catalog.json: that file ships inside the app's bundled resources, which
// are read-only once installed (a system package's /usr/share, or inside
// an AppImage). Instead they live in a small per-user overrides.json in
// the OS-standard app config dir, applied on top of catalog.json by the
// frontend at load time — catalog.json itself is never modified at runtime.
fn overrides_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_config_dir().map_err(|e| e.to_string())?;
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir.join("overrides.json"))
}

#[tauri::command]
fn load_overrides(app: tauri::AppHandle) -> Result<serde_json::Value, String> {
    let path = overrides_path(&app)?;
    if !path.exists() {
        return Ok(serde_json::json!({}));
    }
    let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    serde_json::from_str(&text).or_else(|_| {
        // Unparseable (hand-edited, truncated by a crash): the frontend falls
        // back to no overrides and its next save would overwrite this file,
        // silently destroying whatever was salvageable. Keep a copy first.
        let _ = fs::rename(&path, path.with_extension("json.bak"));
        Ok(serde_json::json!({}))
    })
}

#[tauri::command]
fn save_overrides(app: tauri::AppHandle, overrides: serde_json::Value) -> Result<(), String> {
    let path = overrides_path(&app)?;
    let text = serde_json::to_string_pretty(&overrides).map_err(|e| e.to_string())?;
    // Write-then-rename so a crash mid-write can't leave a truncated file.
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, text).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &path).map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            is_installed,
            get_icon,
            launch_app,
            load_overrides,
            save_overrides
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bin(linux: Option<&str>, windows: Option<&str>, macos: Option<&str>) -> PlatformBin {
        PlatformBin {
            linux: linux.map(String::from),
            windows: windows.map(String::from),
            macos: macos.map(String::from),
        }
    }

    #[test]
    fn for_current_os_picks_this_platforms_slot() {
        let b = bin(Some("l"), Some("w"), Some("m"));
        let expected = match std::env::consts::OS {
            "linux" => Some("l"),
            "windows" => Some("w"),
            "macos" => Some("m"),
            _ => None,
        };
        assert_eq!(b.for_current_os(), expected);
    }

    #[test]
    fn missing_slot_means_not_installed() {
        let only_other_os = match std::env::consts::OS {
            "linux" => bin(None, Some("w"), Some("m")),
            "windows" => bin(Some("l"), None, Some("m")),
            _ => bin(Some("l"), Some("w"), None),
        };
        assert!(only_other_os.for_current_os().is_none());
        assert!(!is_installed(only_other_os));
    }

    #[test]
    fn expand_env_substitutes_known_and_keeps_unknown() {
        std::env::set_var("APP_LAUNCHER_TEST_DIR", r"C:\Users\someone");
        assert_eq!(
            expand_env(r"%APP_LAUNCHER_TEST_DIR%\bin\x.exe"),
            r"C:\Users\someone\bin\x.exe"
        );
        assert_eq!(expand_env(r"%NO_SUCH_VAR_XYZ%\x"), r"%NO_SUCH_VAR_XYZ%\x");
        assert_eq!(expand_env("100%"), "100%");
        assert_eq!(expand_env("a%%b"), "a%%b");
        assert_eq!(expand_env("plain"), "plain");
    }

    #[cfg(windows)]
    #[test]
    fn windows_resolve_finds_a_system_exe_by_name_and_by_env_path() {
        assert!(windows_resolve("cmd.exe").is_some());
        assert!(windows_resolve(r"%SystemRoot%\System32\cmd.exe").is_some());
        assert!(windows_resolve("definitely-not-installed-xyz.exe").is_none());
    }
}
