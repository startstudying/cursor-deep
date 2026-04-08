param(
    [string]$CompilerPath = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($CompilerPath)) {
    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )

    $CompilerPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $CompilerPath) {
    throw "Inno Setup compiler ISCC.exe was not found. Please install Inno Setup 6 first."
}

& $CompilerPath "installer.iss"
Write-Host "Installer build finished:" -ForegroundColor Green
Write-Host "installer-dist/cursor-deep-plus-desktop-setup.exe"
