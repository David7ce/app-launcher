use std::path::Path;
use std::process::Command;

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

#[tauri::command]
fn launch_app(bin: PlatformBin) -> Result<(), String> {
    let Some(name) = bin.for_current_os() else {
        return Err("no launch command configured for this OS".to_string());
    };
    let result = match std::env::consts::OS {
        // The standard way to launch a macOS app by name regardless of its
        // exact path. Unverified: never run on real macOS.
        "macos" => Command::new("open").args(["-a", name]).spawn(),
        _ => Command::new(name).spawn(),
    };
    result
        .map(|_| ())
        .map_err(|e| format!("failed to launch '{name}': {e}"))
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
        .invoke_handler(tauri::generate_handler![is_installed, launch_app])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
