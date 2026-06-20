# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 本项目的 AI 协作规则真源是 `AGENTS.md`，本文件为架构速览与开发命令补充。遇到规则冲突时以 `AGENTS.md` 为准。

## 项目定位

A股/港股/美股自选股智能分析系统。主流程：**抓取数据 → 技术分析/新闻检索 → LLM 分析 → 生成报告 → 通知推送**。

## 架构概览

```
apps/dsa-web/          React/TypeScript Web 前端 (Vite)
apps/dsa-desktop/      Electron 桌面端
api/                   FastAPI 后端 (v1 RESTful)
  api/v1/endpoints/    路由处理函数
  api/v1/schemas/      Pydantic 请求/响应模型
src/                   核心业务逻辑
  src/services/        业务服务层 (PortfolioService, AnalysisService, ...)
  src/repositories/    数据访问层 (PortfolioRepository, ...)
  src/storage.py       SQLAlchemy ORM 模型 + DatabaseManager 单例
  src/config.py        全局配置 (env → Config 单例)
  src/logging_config.py 日志系统
data_provider/         多数据源适配 + fallback 链 (base.py: DataFetcherManager)
bot/                   机器人接入 (飞书/Telegram/Discord)
templates/             Jinja2 报告模板
scripts/               CI/构建/发布脚本
tests/                 pytest 测试
```

## 初始化链路

1. `server.py`：入口 → `setup_env()` → `get_config()` → `setup_logging()` → `from api.app import app`
2. `api/app.py`：`create_app()` → CORS 中间件 → 注册 `api_v1_router` → 挂载静态文件 SPA
3. `main.py`：更重的入口，包含调度器、前端构建检查、任务队列初始化

`Config` 和 `DatabaseManager` 都是单例：`Config.get_instance()` / `DatabaseManager.get_instance()`。测试中通过 `reset_instance()` 隔离。

## 数据源 Fallback 链

`data_provider/base.py` 中的 `DataFetcherManager` 按优先级遍历所有 fetcher：

- 默认优先级：`efinance(0) > akshare(1) > tushare/pytdx(2) > baostock(3) > yfinance(4)`
- Tushare 有有效 token 时自动提升到 P-1（最高）
- 实时行情有独立优先级，通过 `.env` 中 `REALTIME_SOURCE_PRIORITY` 控制
- 每个 fetcher 有独立的熔断器（`data_provider/realtime_types.py`）

## Portfolio 持仓模块关键设计

- **事件溯源 + 缓存**：所有交易/资金/公司行为记录在事件表中，Snapshot 通过回放事件计算，结果缓存在 `PortfolioPosition`/`PortfolioPositionLot`/`PortfolioDailySnapshot` 表
- **写事务**：`portfolio_write_session()` 使用 `BEGIN IMMEDIATE` 做 SQLite 写串行化，冲突时抛 `PortfolioBusyError`
- **成本计算**：FIFO（先进先出 lot）和 AVG（加权平均），通过 `_replay_account()` 统一回放
- **增量优化**（最近改动）：`record_trade_with_snapshot()` 在写事务内直接读取缓存持仓 → 增量应用变更 → 写回缓存，跳过全量回放。缓存为空时回退到从单笔交易构建初始状态。
- **Fast 模式**：`get_portfolio_snapshot(fast=True)` 跳过实时行情查询，仅用 DB 缓存收盘价

## API 路由总览

所有路由前缀 `/api/v1`，完整定义在 `api/v1/router.py`。

### Agent（问股聊天）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/agent/models` | 可用 Agent 模型列表 |
| `GET` | `/agent/skills` | 可用分析策略列表 |
| `POST` | `/agent/chat` | 发送消息，返回 AI 回复 |
| `POST` | `/agent/chat/stream` | 流式 SSE 聊天，实时推送思考/工具调用/生成过程 |
| `GET` | `/agent/chat/sessions` | 聊天会话列表（`?limit=50&user_id=xxx`） |
| `GET` | `/agent/chat/sessions/{id}` | 获取会话完整消息记录 |
| `DELETE` | `/agent/chat/sessions/{id}` | 删除会话 |
| `POST` | `/agent/chat/send` | 推送聊天内容到通知渠道 |
| `POST` | `/agent/research` | 深度研究（ResearchAgent） |

### Analysis（分析任务）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/analysis/analyze` | 触发股票 AI 分析（支持同步/异步） |
| `POST` | `/analysis/market-review` | 触发大盘复盘 |
| `GET` | `/analysis/tasks` | 分析任务列表 |
| `GET` | `/analysis/tasks/stream` | 任务状态 SSE 流 |
| `GET` | `/analysis/tasks/{task_id}` | 任务状态查询 |
| `GET` | `/analysis/tasks/{task_id}/run-flow` | 任务运行流快照 |

### History（历史报告）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/history` | 历史分析列表（支持分页/筛选） |
| `DELETE` | `/history` | 按条件删除历史 |
| `DELETE` | `/history/by-code/{code}` | 按股票代码删除 |
| `GET` | `/history/stocks` | 不重复个股列表（StockBar） |
| `GET` | `/history/{record_id}` | 报告详情 |
| `GET` | `/history/{record_id}/diagnostics` | 运行诊断摘要 |
| `GET` | `/history/{record_id}/run-flow` | 运行流快照 |
| `GET` | `/history/{record_id}/news` | 关联新闻 |
| `GET` | `/history/{record_id}/markdown` | Markdown 原文 |

### Stocks（股票数据）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/stocks/extract-from-image` | 图片识别提取股票代码 |
| `POST` | `/stocks/parse-import` | 解析 CSV/Excel/剪贴板导入 |
| `GET` | `/stocks/watchlist` | 获取自选队列 |
| `POST` | `/stocks/watchlist` | 加入自选队列 |
| `DELETE` | `/stocks/watchlist` | 从自选队列删除 |
| `GET` | `/stocks/quote` | 实时行情（`?stock_code=600519`） |
| `GET` | `/stocks/history` | 历史K线（`?stock_code=600519&days=365`） |

### Portfolio（持仓管理）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/portfolio/accounts` | 创建账户 |
| `GET` | `/portfolio/accounts` | 账户列表 |
| `PUT` | `/portfolio/accounts/{id}` | 更新账户 |
| `DELETE` | `/portfolio/accounts/{id}` | 停用账户 |
| `POST` | `/portfolio/trades` | 录入交易（支持 `?return_snapshot=true&fast=true`） |
| `GET` | `/portfolio/trades` | 交易流水列表 |
| `DELETE` | `/portfolio/trades/{id}` | 删除交易 |
| `POST` | `/portfolio/cash-ledger` | 录入资金流水 |
| `GET` | `/portfolio/cash-ledger` | 资金流水列表 |
| `DELETE` | `/portfolio/cash-ledger/{id}` | 删除资金流水 |
| `POST` | `/portfolio/corporate-actions` | 录入公司行为 |
| `GET` | `/portfolio/corporate-actions` | 公司行为列表 |
| `DELETE` | `/portfolio/corporate-actions/{id}` | 删除公司行为 |
| `GET` | `/portfolio/snapshot` | 持仓快照（`?fast=true&include_risk=true`） |
| `POST` | `/portfolio/positions/{symbol}/analysis` | 提交持仓分析 |
| `POST` | `/portfolio/fx/refresh` | 刷新汇率缓存 |
| `GET` | `/portfolio/risk` | 风险报告 |
| `POST` | `/portfolio/imports/csv/parse` | 解析券商 CSV |
| `GET` | `/portfolio/imports/csv/brokers` | 支持券商列表 |
| `POST` | `/portfolio/imports/csv/commit` | 提交 CSV 导入 |

### Backtest（回测）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/backtest/run` | 触发回测 |
| `GET` | `/backtest/results` | 回测结果 |
| `GET` | `/backtest/performance` | 整体回测表现 |
| `GET` | `/backtest/performance/{symbol}` | 单股回测表现 |

### Alerts（告警）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/alerts/rules` | 创建告警规则 |
| `GET` | `/alerts/rules` | 告警规则列表 |
| `GET` | `/alerts/rules/{id}` | 获取单条规则 |
| `PATCH` | `/alerts/rules/{id}` | 更新规则 |
| `DELETE` | `/alerts/rules/{id}` | 删除规则 |
| `POST` | `/alerts/rules/{id}/enable` | 启用规则 |
| `POST` | `/alerts/rules/{id}/disable` | 禁用规则 |
| `POST` | `/alerts/rules/{id}/test` | 规则试运行 |
| `GET` | `/alerts/triggers` | 触发历史 |
| `GET` | `/alerts/notifications` | 通知尝试记录 |

### DecisionSignals（决策信号）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/decision-signals` | 创建/去重决策信号 |
| `GET` | `/decision-signals` | 信号列表 |
| `GET` | `/decision-signals/latest-active` | 某股票最新活跃信号 |
| `GET` | `/decision-signals/{id}` | 单条信号详情 |
| `PATCH` | `/decision-signals/{id}/status` | 更新信号状态 |

### AlphaSift（选股引擎）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/alphasift/status` | 引擎状态 |
| `GET` | `/alphasift/strategies` | 可用策略 |
| `POST` | `/alphasift/install` | 安装策略 |
| `POST` | `/alphasift/screen/tasks` | 启动异步筛选（202） |
| `GET` | `/alphasift/screen/tasks/{id}` | 筛选任务状态 |
| `POST` | `/alphasift/screen` | 同步筛选 |

### Auth / System / Usage

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/auth/status` | 认证状态 |
| `POST` | `/auth/settings` | 更新认证设置 |
| `POST` | `/auth/login` | 登录/设初始密码 |
| `POST` | `/auth/change-password` | 修改密码 |
| `POST` | `/auth/logout` | 登出 |
| `GET` | `/system/config` | 系统配置 |
| `PUT` | `/system/config` | 更新配置 |
| `GET` | `/system/setup-status` | 初始化状态 |
| `GET` | `/system/config/schema` | 配置 JSON Schema |
| `POST` | `/system/config/validate` | 验证配置 |
| `POST` | `/system/config/llm/test` | 测试 LLM 通道 |
| `POST` | `/system/config/llm/discover` | 发现 LLM 模型 |
| `POST` | `/system/config/notification/test` | 测试通知渠道 |
| `POST` | `/system/config/export` | 导出配置备份 |
| `POST` | `/system/config/import` | 导入配置备份 |
| `GET` | `/usage/tokens` | LLM Token 用量统计 |

### 前端 API 封装

前端 `apps/dsa-web/src/api/` 下每个模块对应后端路由：

| 文件 | 导出 |
|------|------|
| `agent.ts` | `agentApi` — chat/stream/sessions/send/skills |
| `portfolio.ts` | `portfolioApi` — accounts/trades/snapshot/risk/import |
| `analysis.ts` | 分析触发、任务状态 |
| `stocks.ts` | 行情、自选、导入 |
| `backtest.ts` | 回测运行/结果 |
| `alerts.ts` | 告警规则 CRUD |
| `alphasift.ts` | 选股筛选 |
| `systemConfig.ts` | 系统配置读写 |
| `auth.ts` | 登录/登出/改密 |
| `history.ts` | 历史报告查询 |

## 常用命令

### 后端

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 API 服务
python main.py --serve-only          # 含前端构建
uvicorn server:app --reload --port 8000  # 仅 API

# 测试
python -m pytest -m "not network" -x   # 离线单元测试 (快速)
python -m pytest -m "network"          # 网络相关测试
python -m pytest tests/test_portfolio_service.py -x  # 单文件
python -m pytest tests/test_portfolio_service.py -x -k "fast or incremental"  # 按名称过滤

# CI gate (lint + compile + offline tests)
./scripts/ci_gate.sh

# 单文件语法检查
python -m py_compile src/services/portfolio_service.py
```

### 前端

```bash
cd apps/dsa-web
npm ci              # 安装依赖（lock 文件优先）
npm run lint        # ESLint
npm run build       # 生产构建 → ../../../static/
npx tsc --noEmit    # TypeScript 类型检查（不产出文件）
```

### 桌面端

```bash
cd apps/dsa-desktop
npm install
npm run build       # 需先构建 Web 前端
```

### 治理资产校验

```bash
python scripts/check_ai_assets.py     # 校验 AGENTS.md / CLAUDE.md / skills 关系
```

## 关键约定

- commit message 使用英文，不加 `Co-Authored-By`
- 新增配置项必须同步更新 `.env.example`
- 涉及用户可见变更必须更新 `docs/CHANGELOG.md` 的 `[Unreleased]` 段（扁平格式：`- [类型] 描述`）
- Windows 环境下路径使用正斜杠，shell 命令优先 PowerShell
- 不做未经确认的 `git commit` / `git push`
- PYTHONPATH 默认指向项目根目录，导入时使用 `src.xxx`、`data_provider.xxx`、`api.xxx`
