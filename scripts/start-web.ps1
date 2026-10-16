param([int]$Port = 8778, [int]$ApiPort = 8777, [string]$LDrawLibrary = "", [string]$Blender = "", [string]$BlenderAddons = "")
$ErrorActionPreference = "Stop"
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location $taskRoot
if (-not (Test-Path .venv/Scripts/python.exe)) { throw "Run scripts/setup.ps1 first." }
if ($LDrawLibrary) { $env:LDRAW_LIBRARY_PATH = $LDrawLibrary }
if ($Blender) { $env:LDRAW_MCP_BLENDER = $Blender }
if ($BlenderAddons) { $env:BLENDER_USER_SCRIPTS = $BlenderAddons }
$env:CAR2LEGO_API_ORIGIN = "http://127.0.0.1:$ApiPort"
$env:CAR2LEGO_FRONTEND_PORT = "$Port"
Push-Location frontend
try {
    npm ci --no-fund --no-audit
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally { Pop-Location }
$api = Start-Process -FilePath "$taskRoot/.venv/Scripts/python.exe" -ArgumentList @('-u','-m','car2lego3d','desktop-api','--port',"$ApiPort") -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru
try {
    Set-Location "$taskRoot/frontend"
    npm run start -- --hostname 127.0.0.1 --port $Port
} finally {
    if (-not $api.HasExited) { taskkill /PID $api.Id /T /F }
}
