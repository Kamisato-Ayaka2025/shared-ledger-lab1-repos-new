$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& .venv/Scripts/python.exe -m ruff check src tests scripts
if ($LASTEXITCODE) { throw '规范检查失败' }
& .venv/Scripts/python.exe -m ruff format --check src tests scripts
if ($LASTEXITCODE) { throw '格式检查失败' }
& .venv/Scripts/python.exe -m pytest -q
if ($LASTEXITCODE) { throw '测试失败' }
& .venv/Scripts/python.exe scripts/count_lines.py
