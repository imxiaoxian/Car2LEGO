param([string]$Python = "3.11")
$ErrorActionPreference = "Stop"
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location $taskRoot
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Command failed: $LASTEXITCODE" } }
if (-not (Test-Path .venv/Scripts/python.exe)) {
    uv venv --python $Python .venv
    Check-Exit
}
uv pip install --python .venv/Scripts/python.exe torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124 --quiet
Check-Exit
uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt --quiet
Check-Exit
uv pip install --python .venv/Scripts/python.exe -e . --no-deps --quiet
Check-Exit
uv pip install --python .venv/Scripts/python.exe -e ".[gpt,blender]" --quiet
Check-Exit
.venv/Scripts/python.exe -m car2lego3d setup
Check-Exit
.venv/Scripts/python.exe -m car2lego3d doctor
Check-Exit
