#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpListener;
use std::sync::mpsc;
use std::sync::Mutex;

use tauri::{AppHandle, Manager, RunEvent, WindowEvent};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

struct BackendProcess {
    child: Mutex<Option<CommandChild>>,
    url: Mutex<Option<String>>,
}

fn available_local_port() -> Result<u16, String> {
    let listener = TcpListener::bind(("127.0.0.1", 0))
        .map_err(|error| format!("failed to reserve backend port: {error}"))?;
    let port = listener
        .local_addr()
        .map_err(|error| format!("failed to read backend port: {error}"))?
        .port();
    drop(listener);
    Ok(port)
}

fn stop_backend(app: &AppHandle) {
    if let Some(child) = app
        .state::<BackendProcess>()
        .child
        .lock()
        .expect("backend state lock poisoned")
        .take()
    {
        let _ = child.kill();
    }
}

#[tauri::command]
fn backend_url(app: AppHandle) -> Result<String, String> {
    app.state::<BackendProcess>()
        .url
        .lock()
        .expect("backend state lock poisoned")
        .clone()
        .ok_or_else(|| "Backend has not started yet.".to_string())
}

#[tauri::command]
async fn pick_folder(app: AppHandle) -> Result<Option<String>, String> {
    let (sender, receiver) = mpsc::channel();
    app.dialog().file().pick_folder(move |folder| {
        let _ = sender.send(folder);
    });
    let folder = receiver
        .recv()
        .map_err(|error| format!("Folder picker did not return a selection: {error}"))?;
    folder
        .map(|path| {
            path.into_path()
                .map(|path| path.to_string_lossy().to_string())
                .map_err(|error| format!("Could not read selected folder path: {error}"))
        })
        .transpose()
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcess {
            child: Mutex::new(None),
            url: Mutex::new(None),
        })
        .setup(|app| {
            let port = available_local_port()?;
            let url = format!("http://127.0.0.1:{port}");
            let sidecar = app
                .shell()
                .sidecar("local-face-backend")
                .map_err(|error| format!("failed to prepare backend sidecar: {error}"))?
                .env("LOCAL_FACE_PACKAGED", "1")
                .env("LOCAL_FACE_HOST", "127.0.0.1")
                .env("LOCAL_FACE_PORT", port.to_string());
            let (_receiver, child) = sidecar
                .spawn()
                .map_err(|error| format!("failed to start backend sidecar: {error}"))?;
            let backend = app.state::<BackendProcess>();
            backend
                .child
                .lock()
                .expect("backend state lock poisoned")
                .replace(child);
            backend
                .url
                .lock()
                .expect("backend state lock poisoned")
                .replace(url);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { .. } = event {
                stop_backend(&window.app_handle());
            }
        })
        .invoke_handler(tauri::generate_handler![backend_url, pick_folder])
        .build(tauri::generate_context!())
        .expect("error while building Local Face Photos");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            stop_backend(app_handle);
        }
    });
}
