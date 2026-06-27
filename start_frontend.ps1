# ATS Resume Scorer — Frontend startup script
# Run this from the repo root: .\start_frontend.ps1
#
# It uses the project venv so the correct packages are used.
# The Streamlit app starts on http://localhost:8501

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

Write-Host "=== ATS Resume Scorer — Frontend ===" -ForegroundColor Cyan
Write-Host "Starting Streamlit app on http://localhost:8501 ..." -ForegroundColor Green
Write-Host "Make sure the backend is running on http://localhost:8000 first."
Write-Host "Press Ctrl+C to stop.`n"

& "$repo\venv\Scripts\python.exe" -m streamlit run frontend/streamlit_app.py `
    --server.port 8501 `
    --server.address 0.0.0.0
