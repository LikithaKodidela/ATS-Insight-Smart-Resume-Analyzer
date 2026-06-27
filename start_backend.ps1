# ATS Resume Scorer — Backend startup script
# Run this from the repo root: .\start_backend.ps1
#
# It uses the project venv so the correct packages and spaCy model are used.
# The server starts on http://localhost:8000
# Swagger UI: http://localhost:8000/docs
#
# NOTE: --reload is intentionally omitted for stability.
# Use it only during active development: add `--reload` to the uvicorn line below.

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

Write-Host "=== ATS Resume Scorer — Backend ===" -ForegroundColor Cyan
Write-Host "Starting FastAPI server on http://localhost:8000 ..." -ForegroundColor Green
Write-Host "Swagger UI: http://localhost:8000/docs"
Write-Host "Press Ctrl+C to stop.`n"

& "$repo\venv\Scripts\python.exe" -m uvicorn backend.main:app `
    --host 0.0.0.0 `
    --port 8000
