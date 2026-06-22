# setup.ps1
# This script sets up the local environment and dependencies for Portfolio Manager.

$ErrorActionPreference = "Stop"

Write-Host "========================================="
Write-Host " Portfolio Manager - Setup Script        "
Write-Host "========================================="
Write-Host ""

# 1. Setup Python Virtual Environment
Write-Host "1. Setting up Python environment..."
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment (venv)..."
    python -m venv venv
} else {
    Write-Host "Virtual environment already exists."
}

Write-Host "Installing dependencies..."
.\venv\Scripts\python -m pip install -q --upgrade pip
.\venv\Scripts\pip install -q -r backend\requirements.txt
Write-Host "Python dependencies installed.`n"

# 2. Setup .env file
Write-Host "2. Checking for .env configuration..."
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example. Please update any necessary API keys inside.`n"
    }
} else {
    Write-Host ".env already exists.`n"
}

# 3. Setup Ollama
Write-Host "3. Checking for Ollama (Local AI)..."
$ollamaCommand = Get-Command "ollama" -ErrorAction SilentlyContinue

if ($null -eq $ollamaCommand) {
    Write-Host "Ollama is not installed or not in PATH." -ForegroundColor Yellow
    Write-Host "To use the AI Insights feature, please install Ollama from https://ollama.com/"
    Write-Host "After installing, open a new terminal and run: ollama pull phi3.5"
} else {
    Write-Host "Ollama found. Pulling the phi3.5 model..."
    try {
        # Check if ollama server is running by attempting to list models
        $listOutput = ollama list 2>&1
        if ($LASTEXITCODE -ne 0 -or $listOutput -match "could not connect") {
            Write-Host "Ollama is installed but the service does not appear to be running." -ForegroundColor Yellow
            Write-Host "Please start Ollama from your Start Menu, then run: ollama pull phi3.5"
        } else {
            ollama pull phi3.5
            Write-Host "Successfully pulled phi3.5.`n"
        }
    } catch {
        Write-Host "Failed to pull phi3.5 automatically. Please run 'ollama pull phi3.5' manually." -ForegroundColor Yellow
    }
}

Write-Host "`n========================================="
Write-Host " Setup Complete! " -ForegroundColor Green
Write-Host " You can now start the app by running: .\start.bat"
Write-Host "========================================="
