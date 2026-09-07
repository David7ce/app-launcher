use std::process::Command;

#[tauri::command]
fn is_installed(bin: String) -> bool {
    which::which(&bin).is_ok()
}

#[tauri::command]
fn launch_app(bin: String) -> Result<(), String> {
    Command::new(&bin)
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("failed to launch '{bin}': {e}"))
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
