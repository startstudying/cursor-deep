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
  --icon "assets/app.ico" `
  --collect-submodules webview `
  --add-data "app/desktop/index.html;app/desktop" `
  --add-data "assets/app.ico;assets" `
  desktop_app.py

Write-Host "Build finished. EXE output:" -ForegroundColor Green
Write-Host "dist/cursor-deep-plus-desktop.exe"
