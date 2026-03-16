# scripts/dev-desktop.ps1
# Run Qavrn in desktop development mode (hot-reload React + Tauri dev window).
#
# Prerequisites:
#   - Rust (https://rustup.rs)
#   - Node.js 18+
#   - Tauri CLI v2: cargo install tauri-cli --version "^2"
#   - Python 3.11+ with backend dependencies installed
#     (run: pip install -r backend/requirements.txt)
#   - Ollama running: ollama serve
#
# What this script does:
#   1. Starts the Python backend in API-only mode (port 8000)
#   2. Runs `cargo tauri dev` which:
#      - Starts the Vite dev server on port 5173
#      - Opens the Tauri dev window pointed at localhost:5173
#
# Press Ctrl+C to stop everything.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host ""
Write-Host "-- Qavrn Desktop Dev Mode ------------------------------------" -ForegroundColor Cyan

# 1. Start the Python backend in --api-only mode
Write-Host ""
Write-Host "Starting Python backend on http://localhost:8000 ..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($r)
    Set-Location $r
    python start.py --api-only --reload
} -ArgumentList $root

Write-Host "Backend started (job ID: $($backendJob.Id))" -ForegroundColor Green

# Give the backend a moment to start before opening Tauri
Start-Sleep -Seconds 2

# 2. Start Tauri dev (Vite + Tauri window)
Write-Host ""
Write-Host "Starting Tauri dev window..." -ForegroundColor Yellow
Write-Host "(The window will load from the Vite dev server at http://localhost:5173)" -ForegroundColor DarkGray
Write-Host ""

try {
    cargo tauri dev
} finally {
    # Clean up the backend job when Tauri dev is stopped
    Write-Host ""
    Write-Host "Stopping backend..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob -ErrorAction SilentlyContinue
    Write-Host "Done." -ForegroundColor Green
}
