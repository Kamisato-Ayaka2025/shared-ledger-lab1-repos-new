$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& .venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name Tongzhang --paths src --collect-submodules uvicorn --hidden-import tongzhang.api --hidden-import tongzhang.desktop scripts/launch.py
if ($LASTEXITCODE) { throw '构建失败' }
