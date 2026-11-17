# 同账代码运行说明

Python 3.12，Windows 64 位。规划、需求决策和验收记录位于工作区 `HW/HW3`。

- 初始化：`pwsh -File scripts/setup.ps1`
- 一键运行：`pwsh -File scripts/run.ps1`
- 检查：`pwsh -File scripts/check.ps1`
- 类型检查：`.venv/Scripts/python.exe -m mypy src/tongzhang --ignore-missing-imports`
- 构建：`pwsh -File scripts/build.ps1`
- 桌面 HTTP 烟测与截图：`.venv/Scripts/python.exe scripts/ui_smoke.py`
- 未打包 Qt 流程回归：`.venv/Scripts/python.exe scripts/run_local_journey.py`
- 可复现查询基准：`.venv/Scripts/python.exe scripts/benchmark.py`

构建结果 `dist/Tongzhang/Tongzhang.exe` 自动启动本机服务，第二个客户端复用服务。
演示账号 `manager`、`alice`、`bob`、`root`，密码均为 `Demo123!`。仅作为本机课程演示。
数据在 `%LOCALAPPDATA%/Tongzhang/demo.db`，日志在同目录。关闭客户端后服务保留，便于多个客户端使用；系统重启后由启动器再次启动。

测试用 `TONGZHANG_PORT` 环境变量可以把服务、客户端和验收脚本整体换到其他端口，
从而与正在运行的演示实例隔离；默认仍为 8765，日常启动无需设置。

业务源码位于 `src/tongzhang`，测试使用独立临时数据库，不改演示账目。`requirements-lock.txt` 锁定当前已验证依赖。

## 打包后的完整交互回归

运行 `.venv/Scripts/python.exe scripts/run_packaged_e2e.py`。要求 8765 端口空闲；脚本会拒绝连接任何已运行的服务，以免改动现有数据。它从 `dist/Tongzhang/Tongzhang.exe` 启动客户端和服务端，在 `HW/HW3/检查/EXE完整验收-*` 中创建独立数据目录。

回归使用 Qt 输入驱动实际登录、建账、邀请、录入、审核、预算与结算表单，经真实 HTTP 保存数据；不直接调用业务服务。测试结束重启服务和客户端，核对持久化，再保存截图、逐步结果与 EXE SHA-256。测试专用入口为 `--e2e-ui` 和 `--e2e-resume`，由脚本管理，不用于日常启动。
