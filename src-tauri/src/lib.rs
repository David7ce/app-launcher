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

#[tauri::command]
fn is_installed(bin: PlatformBin) -> bool {
    let Some(name) = bin.for_current_os() else {
        return false;
    };
    match std::env::consts::OS {
        "macos" => macos_app_installed(name),
        // Linux and Windows both resolve via $PATH; the `which` crate is
        // cross-platform and Windows-aware (checks PATHEXT, so a bare
        // "git" correctly resolves "git.exe").
        _ => which::which(name).is_ok(),
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

#[tauri::command]
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
        "windows" if cli => Command::new("cmd").args(["/k", name]).spawn(),
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
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_overrides(app: tauri::AppHandle, overrides: serde_json::Value) -> Result<(), String> {
    let path = overrides_path(&app)?;
    let text = serde_json::to_string_pretty(&overrides).map_err(|e| e.to_string())?;
    fs::write(&path, text).map_err(|e| e.to_string())
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
            launch_app,
            load_overrides,
            save_overrides
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
