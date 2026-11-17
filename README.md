# 同账代码运行说明

Python 3.12，Windows 64 位。规划、需求决策和验收记录位于工作区 `HW/HW3`。

- 初始化：`pwsh -File scripts/setup.ps1`
- 一键运行：`pwsh -File scripts/run.ps1`
- 检查：`pwsh -File scripts/check.ps1`
- 类型检查：`.venv/Scripts/python.exe -m mypy src/tongzhang --ignore-missing-imports`
- 构建：`pwsh -File scripts/build.ps1`
- 桌面 HTTP 烟测：`.venv/Scripts/python.exe scripts/ui_smoke.py`
- 可复现查询基准：`.venv/Scripts/python.exe scripts/benchmark.py`

构建结果 `dist/Tongzhang/Tongzhang.exe` 自动启动本机服务，第二个客户端复用服务。
演示账号 `manager`、`alice`、`bob`、`root`，密码均为 `Demo123!`。仅作为本机课程演示。
数据在 `%LOCALAPPDATA%/Tongzhang/demo.db`，日志在同目录。关闭客户端后服务保留，便于多个客户端使用；系统重启后由启动器再次启动。

业务源码位于 `src/tongzhang`，测试使用独立临时数据库，不改演示账目。`requirements-lock.txt` 锁定当前已验证依赖。
