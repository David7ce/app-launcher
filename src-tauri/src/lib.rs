mod icons;

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;
use tauri::Manager;

#[cfg(windows)]
pub(crate) const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// Per-OS launch identifier for a catalog entry. Any field can be absent —
/// absent means the app doesn't exist on that OS, so `is_installed` returns
/// false without checking anything, giving "only show installed" for free.
/// On Windows an *empty* string means "exists on Windows, exe unknown": it is
/// then found by display name in the Start Menu.
#[derive(serde::Deserialize)]
pub(crate) struct PlatformBin {
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

/// macOS has no $PATH for GUI apps — look for a `<name>.app` bundle in the
/// usual install locations instead. Exact, case-sensitive match only; no
/// Spotlight/mdfind fuzzy lookup. Unverified: never run on real macOS.
pub(crate) fn macos_bundle_path(name: &str) -> Option<PathBuf> {
    let mut dirs = vec![PathBuf::from("/Applications"), PathBuf::from("/System/Applications")];
    if let Some(home) = std::env::var_os("HOME") {
        dirs.push(Path::new(&home).join("Applications"));
    }
    dirs.into_iter()
        .map(|dir| dir.join(format!("{name}.app")))
        .find(|bundle| bundle.exists())
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
pub(crate) fn windows_resolve(name: &str) -> Option<PathBuf> {
    let name = expand_env(name);
    if name.is_empty() || name.starts_with("start:") {
        return None; // "exe unknown" / "look in the Start Menu" — see PlatformBin
    }
    if name.contains('\\') || name.contains('/') {
        let path = PathBuf::from(&name);
        return path.is_file().then_some(path);
    }
    which::which(&name).ok().or_else(|| windows_registry_lookup(&name))
}

/// The Start Menu name to look for, for a `bin.windows` slot that has no exe.
/// The slot can spell it out as `start:<Start Menu name>` — needed when it
/// differs from the catalog name (the catalog says "Affinity Studio", the Start
/// Menu just "Affinity") — and otherwise the catalog display name is used.
pub(crate) fn start_menu_name<'a>(target: &'a str, name: Option<&'a str>) -> Option<&'a str> {
    target.strip_prefix("start:").or(name)
}

/// Comparison key for matching a catalog display name against a Start Menu
/// one: drops `(...)` groups, architecture/vendor filler and trailing version
/// numbers, then keeps lowercase alphanumerics. `"QGIS Desktop 4.2.0"`,
/// `"Oracle VirtualBox"` and `"Microsoft Excel"` meet `"QGIS"`, `"VirtualBox"`
/// and `"Excel"`. A `+` counts ("Notepad++" is not "Notepad").
fn norm_app_name(name: &str) -> String {
    let name = name.replace('+', "plus");
    let name = name.as_str();
    const NOISE: &[&str] = &[
        "x64", "x86", "64bit", "32bit", "64-bit", "32-bit", "microsoft", "oracle", "the", "desktop",
        "windows",
    ];
    let mut flat = String::new();
    let mut depth = 0u32;
    for c in name.chars() {
        match c {
            '(' => depth += 1,
            ')' => depth = depth.saturating_sub(1),
            _ if depth == 0 => flat.push(c),
            _ => {}
        }
    }
    let lowered = flat.to_lowercase();
    let mut tokens: Vec<&str> = lowered.split_whitespace().filter(|t| !NOISE.contains(t)).collect();
    let is_version = |t: &str| {
        let t = t.strip_prefix('v').unwrap_or(t);
        t.chars().any(|c| c.is_ascii_digit()) && t.chars().all(|c| c.is_ascii_digit() || c == '.')
    };
    // Never strip the last remaining token: a name that *is* a number ("2048").
    while tokens.len() > 1 && tokens.last().is_some_and(|t| is_version(t)) {
        tokens.pop();
    }
    tokens.concat().chars().filter(char::is_ascii_alphanumeric).collect()
}

/// `(normalized name, AppID)` for every Start Menu entry, classic shortcuts and
/// UWP/Store packages alike. `Get-StartApps` is a PowerShell cmdlet and takes a
/// second or two, so it runs at most once, on first use.
#[cfg(windows)]
fn read_start_apps() -> Vec<(String, String)> {
    use std::os::windows::process::CommandExt;

    let script = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; \
                  ConvertTo-Json -InputObject @(Get-StartApps | Select-Object Name,AppID) -Compress";
    let Ok(out) = Command::new("powershell")
        .args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script])
        .creation_flags(CREATE_NO_WINDOW)
        .output()
    else {
        return Vec::new();
    };
    let text = String::from_utf8_lossy(&out.stdout);
    let Ok(serde_json::Value::Array(items)) = serde_json::from_str(text.trim_start_matches('\u{feff}')) else {
        return Vec::new();
    };
    items
        .iter()
        .filter_map(|item| {
            let name = item.get("Name")?.as_str()?;
            let id = item.get("AppID")?.as_str()?;
            Some((norm_app_name(name), id.to_string()))
        })
        .collect()
}

#[cfg(not(windows))]
fn read_start_apps() -> Vec<(String, String)> {
    Vec::new()
}

/// AppID of the Start Menu entry named like `name`, if any. Matching is on the
/// normalized name, exactly — never a prefix — so unrelated apps that merely
/// start with the same word are not picked up.
pub(crate) fn windows_start_app(name: &str) -> Option<&'static str> {
    static APPS: OnceLock<Vec<(String, String)>> = OnceLock::new();
    let key = norm_app_name(name);
    if key.is_empty() {
        return None;
    }
    APPS.get_or_init(read_start_apps)
        .iter()
        .find(|(n, _)| *n == key)
        .map(|(_, id)| id.as_str())
}

/// A classic Start Menu AppID is either an absolute path or
/// `{KnownFolderGUID}\relative\path.exe`; turn the latter into an environment
/// path (`%ProgramW6432%\...`). UWP ids (`Vendor.App_hash!App`) have no exe.
fn expand_start_app_id(app_id: &str) -> String {
    const KNOWN_FOLDERS: &[(&str, &str)] = &[
        ("{6D809377-6AF0-444B-8957-A3773F02200E}", "%ProgramW6432%"),
        ("{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}", "%ProgramFiles(x86)%"),
        ("{905E63B6-C1BF-494E-B29C-65B732D3D21A}", "%ProgramFiles%"),
        ("{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}", "%LOCALAPPDATA%"),
    ];
    let upper = app_id.to_ascii_uppercase();
    for (guid, var) in KNOWN_FOLDERS {
        if upper.starts_with(guid) {
            return format!("{var}{}", &app_id[guid.len()..]);
        }
    }
    app_id.to_string()
}

pub(crate) fn start_app_exe(app_id: &str) -> Option<PathBuf> {
    let path = PathBuf::from(expand_env(&expand_start_app_id(app_id)));
    (path.is_absolute() && path.is_file()).then_some(path)
}

// `async` makes Tauri run these on its thread pool: a plain command runs on the
// main thread, and the frontend fires one `is_installed` per catalog entry
// (~380) at startup, each a PATH search plus registry reads on Windows.
//
// `name` is the catalog display name. It is only used on Windows, as a last
// resort for entries with a Windows slot whose exe can't be found — apps that
// live in neither $PATH nor App Paths (Discord, LibreOffice, Store apps).
#[tauri::command(async)]
fn is_installed(bin: PlatformBin, name: Option<String>) -> bool {
    let Some(target) = bin.for_current_os() else {
        return false;
    };
    match std::env::consts::OS {
        "macos" => macos_bundle_path(target).is_some(),
        "windows" => {
            windows_resolve(target).is_some()
                || start_menu_name(target, name.as_deref())
                    .and_then(windows_start_app)
                    .is_some()
        }
        // Linux: $PATH only, which is how desktop apps are launched there.
        _ => which::which(target).is_ok(),
    }
}

/// Fallback icon for an installed app whose shipped icon is missing, as a
/// `data:` URL (which the CSP allows), or `None` to keep the category glyph.
#[tauri::command(async)]
fn get_icon(app: tauri::AppHandle, id: String, bin: PlatformBin, name: Option<String>) -> Option<String> {
    icons::fallback(&app, &id, &bin, name.as_deref())
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

/// Windows counterpart of `linux_terminal_spawn`: run a console program in its
/// own window and leave it open at a prompt afterwards (`cmd /k`), so
/// `git`/`bun`/`pandoc` — which print usage and exit — stay readable.
///
/// The program is resolved to a full path first, since `cmd` doesn't consult
/// App Paths and Node.js is only reachable through the Start Menu.
///
/// It goes through `start`, not a direct `cmd /k` child: a direct child inherits
/// this process's standard handles, which for a GUI app (or one started with
/// redirected output) are null, so `cmd /k` reads EOF from stdin and closes the
/// instant the program exits — the window never stays open. `start` opens the
/// new console with real console handles. The outer `cmd` is hidden and exits.
#[cfg(windows)]
fn windows_cli_spawn(target: &str, name: Option<&str>) -> std::io::Result<std::process::Child> {
    use std::os::windows::process::CommandExt;

    let exe = windows_resolve(target)
        .or_else(|| start_menu_name(target, name).and_then(windows_start_app).and_then(start_app_exe))
        .unwrap_or_else(|| PathBuf::from(expand_env(target)));
    if exe.as_os_str().is_empty() || target.starts_with("start:") && !exe.is_absolute() {
        return Err(std::io::Error::new(std::io::ErrorKind::NotFound, "program not found"));
    }
    // `start`'s first quoted argument is a window title, hence the empty "".
    let mut command = Command::new("cmd");
    command.args(["/c", "start", ""]);
    if !is_interactive_shell(&exe) {
        command.args(["cmd", "/k"]);
    }
    command.arg(exe).creation_flags(CREATE_NO_WINDOW).spawn()
}

/// A program that is itself an interactive prompt. It gets a window of its own;
/// wrapping it in `cmd /k` would leave a shell running inside a shell, and
/// closing it would drop you into a stray `cmd` prompt.
// Only `windows_cli_spawn` calls it, but it is plain path logic that the tests
// exercise on every OS, so it is compiled everywhere.
#[cfg_attr(not(windows), allow(dead_code))]
fn is_interactive_shell(exe: &Path) -> bool {
    let name = exe.file_name().and_then(|n| n.to_str()).map(str::to_ascii_lowercase);
    matches!(
        name.as_deref(),
        Some("pwsh.exe" | "powershell.exe" | "cmd.exe" | "wsl.exe" | "bash.exe")
    )
}

// Only reached when `consts::OS` is "windows"; exists so other OSes compile.
#[cfg(not(windows))]
fn windows_cli_spawn(_target: &str, _name: Option<&str>) -> std::io::Result<std::process::Child> {
    Err(std::io::Error::new(std::io::ErrorKind::Unsupported, "not Windows"))
}

#[tauri::command(async)]
fn launch_app(bin: PlatformBin, cli: bool, name: Option<String>) -> Result<(), String> {
    let Some(target) = bin.for_current_os() else {
        return Err("no launch command configured for this OS".to_string());
    };
    // What to call the app in an error message; an empty Windows slot has no
    // command of its own.
    let label = if target.is_empty() || target.starts_with("start:") {
        name.as_deref().unwrap_or("app")
    } else {
        target
    };
    let result = match std::env::consts::OS {
        // The standard way to launch a macOS app by name regardless of its
        // exact path. Unverified: never run on real macOS. CLI tools aren't
        // given the terminal-wrapping treatment here — is_installed's
        // .app-bundle check means a bare CLI tool essentially never shows
        // as installed on macOS anyway, so this path is rarely reached.
        "macos" => Command::new("open").args(["-a", target]).spawn(),
        "linux" if cli => linux_terminal_spawn(target),
        "windows" if cli => windows_cli_spawn(target, name.as_deref()),
        "windows" => {
            // Resolve to a full path first: an app registered only in the
            // registry's App Paths key (Office, VLC, Inkscape) is invisible
            // to a bare `Command::new("vlc.exe")`, which would fail with
            // "not found" even though `is_installed` just said it exists.
            if let Some(exe) = windows_resolve(target) {
                Command::new(exe).spawn()
            } else if let Some(id) = start_menu_name(target, name.as_deref()).and_then(windows_start_app) {
                // Start Menu entry (classic shortcut or UWP/Store package):
                // the shell knows how to start either from its AppID.
                Command::new("explorer").arg(format!("shell:AppsFolder\\{id}")).spawn()
            } else {
                Command::new(expand_env(target)).spawn()
            }
        }
        _ => Command::new(target).spawn(),
    };
    result
        .map(|_| ())
        .map_err(|e| format!("failed to launch '{label}': {e}"))
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
        // Even a matching Start Menu name must not resurrect an app that the
        // catalog says doesn't exist on this OS (KDE Dolphin vs the emulator).
        assert!(!is_installed(only_other_os, Some("Calculator".into())));
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

    #[test]
    fn norm_app_name_meets_catalog_and_start_menu_spellings() {
        for (catalog, start) in [
            ("Microsoft Excel", "Excel"),
            ("QGIS", "QGIS Desktop 4.2.0"),
            ("VirtualBox", "Oracle VirtualBox"),
            ("GIMP", "GIMP 3.2.6"),
            ("Node.js", "Node.js"),
            ("MPC-HC", "MPC-HC x64"),
            ("Lucas Chess", "Lucas Chess (R)"),
            ("Visual Studio", "Visual Studio 2022"),
            ("Windows Terminal", "Terminal"),
        ] {
            assert_eq!(norm_app_name(catalog), norm_app_name(start), "{catalog} / {start}");
        }
        // Exact match only: siblings and prefixes stay distinct.
        assert_ne!(norm_app_name("Calculator"), norm_app_name("Calculator Suite"));
        assert_ne!(norm_app_name("Unity"), norm_app_name("Unity Hub"));
        // A name that is a number survives.
        assert_eq!(norm_app_name("2048"), "2048");
        assert_eq!(norm_app_name("(x64)"), "");
    }

    #[test]
    fn a_plus_keeps_names_apart_and_start_slots_can_name_the_start_entry() {
        assert_ne!(norm_app_name("Notepad++"), norm_app_name("Notepad"));
        assert_eq!(norm_app_name("Notepad++"), norm_app_name("Notepad++ (64-bit x64)"));
        // "start:<name>" overrides the catalog name; anything else uses it.
        assert_eq!(start_menu_name("start:Affinity", Some("Affinity Studio")), Some("Affinity"));
        assert_eq!(start_menu_name("", Some("Camera")), Some("Camera"));
        assert_eq!(start_menu_name("foo.exe", None), None);
        // A start: slot is never mistaken for an executable.
        assert!(windows_resolve("start:Affinity").is_none());
    }

    #[test]
    fn interactive_shells_are_recognised_but_tools_are_not() {
        // Bare names only: `Path` splits on `\` only on Windows, and this test
        // runs on every OS in CI.
        for shell in ["pwsh.exe", "wsl.exe", "PowerShell.EXE", "cmd.exe"] {
            assert!(is_interactive_shell(Path::new(shell)), "{shell}");
        }
        for tool in ["git.exe", "pandoc.exe", "python.exe"] {
            assert!(!is_interactive_shell(Path::new(tool)), "{tool}");
        }
    }

    #[test]
    fn start_menu_app_ids_expand_known_folders() {
        assert_eq!(
            expand_start_app_id(r"{6D809377-6AF0-444B-8957-A3773F02200E}\Inkscape\bin\inkscape.exe"),
            r"%ProgramW6432%\Inkscape\bin\inkscape.exe"
        );
        assert_eq!(
            expand_start_app_id(r"{7c5a40ef-a0fb-4bfc-874a-c0f2e0b9fa8e}\Foo\foo.exe"),
            r"%ProgramFiles(x86)%\Foo\foo.exe"
        );
        // Already a path, or a UWP id: left alone.
        assert_eq!(expand_start_app_id(r"C:\Apps\x.exe"), r"C:\Apps\x.exe");
        assert_eq!(
            expand_start_app_id("Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"),
            "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"
        );
        assert!(start_app_exe("Microsoft.WindowsCalculator_8wekyb3d8bbwe!App").is_none());
    }

    #[test]
    fn macos_bundle_lookup_needs_an_exact_bundle_name() {
        assert!(macos_bundle_path("Definitely Not An App 12345").is_none());
    }

    #[cfg(windows)]
    #[test]
    fn windows_resolve_finds_a_system_exe_by_name_and_by_env_path() {
        assert!(windows_resolve("cmd.exe").is_some());
        assert!(windows_resolve(r"%SystemRoot%\System32\cmd.exe").is_some());
        assert!(windows_resolve("definitely-not-installed-xyz.exe").is_none());
        // The empty "exe unknown" slot never resolves on its own.
        assert!(windows_resolve("").is_none());
    }
}
