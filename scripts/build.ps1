$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& .venv/Scripts/python.exe -m PyInstaller --noconfirm --clean Tongzhang.spec
if ($LASTEXITCODE) { throw '构建失败' }
