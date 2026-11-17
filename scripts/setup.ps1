$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
py -3.12 -m venv .venv
if ($LASTEXITCODE) { throw '创建环境失败' }
& .venv/Scripts/python.exe -m pip install -r requirements-lock.txt
if ($LASTEXITCODE) { throw '依赖安装失败' }
& .venv/Scripts/python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE) { throw '安装项目失败' }
