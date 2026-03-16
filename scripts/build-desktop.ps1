# scripts/build-desktop.ps1
# Build the Qavrn desktop app (Tauri + React frontend).
#
# Prerequisites:
#   - Rust (https://rustup.rs)  -- install then: rustup update stable
#   - Node.js 18+               -- for the React frontend
#   - Tauri CLI v2              -- cargo install tauri-cli --version "^2"
#
# Usage:
#   .\scripts\build-desktop.ps1
#
# The installer / bundle is placed in:
#   src-tauri/target/release/bundle/

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host ""
Write-Host "-- Building Qavrn Desktop ------------------------------------" -ForegroundColor Cyan

# 1. Install / update npm dependencies
Write-Host ""
Write-Host "Step 1/2  Installing frontend dependencies & building React app..." -ForegroundColor Yellow
Push-Location (Join-Path $root "frontend")
  npm install
  npm run build
Pop-Location
Write-Host "Frontend built -> frontend/dist/" -ForegroundColor Green

# 2. Build the Tauri app
Write-Host ""
Write-Host "Step 2/2  Building Tauri desktop bundle..." -ForegroundColor Yellow
cargo tauri build

Write-Host ""
Write-Host "Done!  Installer written to: src-tauri/target/release/bundle/" -ForegroundColor Green
