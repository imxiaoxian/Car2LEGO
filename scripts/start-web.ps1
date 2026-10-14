param([int]$Port = 8765, [string]$LDrawLibrary = "", [string]$Blender = "", [string]$BlenderAddons = "")
$ErrorActionPreference = "Stop"
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location $taskRoot
if (-not (Test-Path .venv/Scripts/python.exe)) { throw "Run scripts/setup.ps1 first." }
if ($LDrawLibrary) { $env:LDRAW_LIBRARY_PATH = $LDrawLibrary }
if ($Blender) { $env:LDRAW_MCP_BLENDER = $Blender }
if ($BlenderAddons) { $env:BLENDER_USER_SCRIPTS = $BlenderAddons }
Push-Location frontend
try {
    npm ci --no-fund --no-audit
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally { Pop-Location }
.venv/Scripts/python.exe -m car2lego3d web --port $Port
