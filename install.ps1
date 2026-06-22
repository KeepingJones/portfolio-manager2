# install.ps1
# This script downloads and installs Portfolio Manager to a new PC.

$ErrorActionPreference = "Stop"

$REPO_URL = "https://github.com/KeepingJones/portfolio-manager2.git"
$ZIP_URL = "https://github.com/KeepingJones/portfolio-manager2/archive/refs/heads/master.zip"

Write-Host "========================================="
Write-Host " Portfolio Manager - Installation Script "
Write-Host "========================================="
Write-Host ""

# 1. Determine Installation Directory
$defaultInstallDir = Join-Path $HOME "portfolio-manager"
$installDir = Read-Host "Enter installation path (Press Enter for default: $defaultInstallDir)"
if ([string]::IsNullOrWhiteSpace($installDir)) {
    $installDir = $defaultInstallDir
}

if (Test-Path $installDir) {
    Write-Host "Directory '$installDir' already exists. We will try to install into it." -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    Write-Host "Created directory: $installDir"
}

# 2. Check for Git & Download
$gitCommand = Get-Command "git" -ErrorAction SilentlyContinue

if ($null -ne $gitCommand) {
    Write-Host "Git found. Cloning repository..."
    # Check if directory is empty
    $items = Get-ChildItem -Path $installDir -Force
    if ($items.Count -gt 0) {
        Write-Host "Directory is not empty. Assuming already cloned or performing git pull..." -ForegroundColor Yellow
        Set-Location $installDir
        if (Test-Path ".git") {
            git pull
        } else {
            Write-Host "Directory is not empty and is not a git repo. Aborting clone to prevent data loss." -ForegroundColor Red
            Exit
        }
    } else {
        git clone $REPO_URL $installDir
        Set-Location $installDir
    }
} else {
    Write-Host "Git not found. Downloading repository as a ZIP archive..."
    $zipPath = Join-Path $env:TEMP "portfolio-manager.zip"
    Invoke-WebRequest -Uri $ZIP_URL -OutFile $zipPath
    
    Write-Host "Extracting archive..."
    Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
    
    # Move contents of the extracted folder to the install directory
    $extractedFolder = Join-Path $env:TEMP "portfolio-manager2-master"
    Copy-Item -Path "$extractedFolder\*" -Destination $installDir -Recurse -Force
    
    # Cleanup
    Remove-Item -Path $zipPath -Force
    Remove-Item -Path $extractedFolder -Recurse -Force
    
    Set-Location $installDir
}

# 3. Check for Python
$pythonCommand = Get-Command "python" -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    Write-Host "ERROR: Python is not installed or not in your PATH!" -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://www.python.org/downloads/ and try again." -ForegroundColor Red
    Exit
}

# 4. Run the internal setup script (sets up venv, ollama, etc.)
Write-Host ""
Write-Host "Running project setup script..."
if (Test-Path ".\setup.ps1") {
    # Bypass execution policy for the setup script if needed
    PowerShell.exe -ExecutionPolicy Bypass -File .\setup.ps1
} else {
    Write-Host "setup.ps1 not found in the downloaded files." -ForegroundColor Red
}

# 5. Create Desktop Shortcut (Optional)
Write-Host ""
$createShortcut = Read-Host "Create a desktop shortcut for Portfolio Manager? (Y/N)"
if ($createShortcut -match "^[yY]") {
    $WshShell = New-Object -comObject WScript.Shell
    $ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Portfolio Manager.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = Join-Path $installDir "start.bat"
    $Shortcut.WorkingDirectory = $installDir
    $Shortcut.Description = "Launch Portfolio Manager"
    $Shortcut.Save()
    Write-Host "Desktop shortcut created at: $ShortcutPath" -ForegroundColor Green
}

Write-Host "========================================="
Write-Host " Installation Complete! " -ForegroundColor Green
Write-Host " Portfolio Manager is installed at: $installDir"
Write-Host " You can launch it using the Desktop Shortcut or by running start.bat in that directory."
Write-Host "========================================="
pause
