use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

// ---------------------------------------------------------------------------
// State wrapper
// ---------------------------------------------------------------------------

struct BackendProcess(Arc<Mutex<Option<Child>>>);

// ---------------------------------------------------------------------------
// Tauri commands
// ---------------------------------------------------------------------------

#[tauri::command]
fn get_backend_url() -> String {
    "http://localhost:8000".to_string()
}

// ---------------------------------------------------------------------------
// Backend lifecycle helpers
// ---------------------------------------------------------------------------

fn find_project_root() -> PathBuf {
    let mut dir = std::env::current_exe()
        .unwrap_or_else(|_| PathBuf::from("."))
        .parent()
        .unwrap_or(Path::new("."))
        .to_path_buf();

    for _ in 0..10 {
        if dir.join("start.py").exists() {
            return dir;
        }
        match dir.parent() {
            Some(p) => dir = p.to_path_buf(),
            None => break,
        }
    }

    std::env::current_exe()
        .unwrap_or_else(|_| PathBuf::from("."))
        .parent()
        .unwrap_or(Path::new("."))
        .to_path_buf()
}

fn find_python(root: &Path) -> String {
    let candidates = [
        root.join(".venv").join("Scripts").join("python.exe"),
        root.join(".venv").join("bin").join("python"),
        root.join("venv").join("Scripts").join("python.exe"),
        root.join("venv").join("bin").join("python"),
    ];
    for candidate in &candidates {
        if candidate.exists() {
            return candidate.to_string_lossy().to_string();
        }
    }
    if cfg!(windows) {
        "python".to_string()
    } else {
        "python3".to_string()
    }
}

fn spawn_backend(root: &Path) -> Option<Child> {
    let python = find_python(root);
    let start_py = root.join("start.py");

    println!("[qavrn] Spawning backend: {} {:?} --api-only", python, start_py);

    match Command::new(&python)
        .arg(start_py.to_str().unwrap_or("start.py"))
        .arg("--api-only")
        .current_dir(root)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
    {
        Ok(child) => {
            println!("[qavrn] Backend process started (pid {})", child.id());
            Some(child)
        }
        Err(e) => {
            eprintln!("[qavrn] Failed to start backend: {}", e);
            None
        }
    }
}

fn wait_for_backend(timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if TcpStream::connect("127.0.0.1:8000").is_ok() {
            println!("[qavrn] Backend is ready.");
            return true;
        }
        std::thread::sleep(Duration::from_millis(250));
    }
    eprintln!("[qavrn] Timed out waiting for backend to start.");
    false
}

// ---------------------------------------------------------------------------
// Public entry point called by main.rs
// ---------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let root = find_project_root();
    println!("[qavrn] Project root: {:?}", root);

    let child = spawn_backend(&root);
    let process_arc = Arc::new(Mutex::new(child));

    let poll_arc = process_arc.clone();
    std::thread::spawn(move || {
        let ready = wait_for_backend(Duration::from_secs(60));
        if !ready {
            if let Ok(mut guard) = poll_arc.lock() {
                if let Some(ref mut child) = *guard {
                    if let Ok(Some(status)) = child.try_wait() {
                        eprintln!("[qavrn] Backend exited early with: {}", status);
                    }
                }
            }
        }
    });

    let cleanup_arc = process_arc.clone();

    tauri::Builder::default()
        .manage(BackendProcess(process_arc))
        .invoke_handler(tauri::generate_handler![get_backend_url])
        .build(tauri::generate_context!())
        .expect("error building Tauri application")
        .run(move |_app, event| {
            if let tauri::RunEvent::Exit = event {
                let mut guard = cleanup_arc.lock().unwrap();
                if let Some(mut child) = guard.take() {
                    println!("[qavrn] Killing backend process...");
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        });
}
