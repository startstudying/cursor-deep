param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

& $Python -m pip install -r requirements.txt pyinstaller
& $Python -m PyInstaller `
  --noconfirm `
  --clean `
  --name cursor-deep-plus-desktop `
  --onefile `
  --windowed `
  --collect-submodules webview `
  --add-data "app/desktop/index.html;app/desktop" `
  desktop_app.py

Write-Host "Build finished. EXE output:" -ForegroundColor Green
Write-Host "dist/cursor-deep-plus-desktop.exe"
