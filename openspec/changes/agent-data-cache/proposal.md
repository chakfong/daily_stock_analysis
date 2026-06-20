## 为什么

问股 Agent 每次分析都会重复获取已拉取过的数据。从实际日志看，同一只股票在一次问股中被调用了 4 次 K 线接口（不同时间窗口）、2 次实时行情、5 次新闻搜索（累计 36 秒）。虽然 K 线数据和新闻已经在写入时做了 DB 持久化，但读取路径仍然优先走外部 API。需要将"永久存储 → 优先读 DB → 缺失部分才拉 API"的策略贯彻到所有事实型数据上。

## 变更内容

- K 线数据 `load_history_df` 改为增量补全：DB 有缓存时只拉取缺失天数，不再全量重拉
- 新闻搜索增加 DB 优先读取：调用外部搜索 API 前先查本地已持久化的新闻，命中则直接返回
- Agent 会话级工具去重：同一会话中相同工具+相同参数不重复调用，直接返回首次结果
- 筹码分布改为本地计算：基于 DB 中缓存的 K 线+换手率直接用 Python 跑 CYQ 算法，不再依赖不稳定的东财接口
- 基本面/板块数据查询结果写入 DB 并优先读缓存

## 功能 (Capabilities)

### 新增功能

- `kline-incremental-sync`: K 线数据加载改为增量策略 — DB 优先，仅补全缺口，不再因窗口大小不同而重复拉取
- `news-persistent-read`: 新闻搜索在读路径上增加 DB 优先检查，命中直接返回持久化结果，跳过外部 API
- `agent-tool-dedup`: Agent 单次会话内同一工具+参数去重，避免 LLM 多次调用同一查询
- `local-cyq-calculator`: 本地筹码分布计算 — 基于 K 线+换手率纯 Python 实现 CYQ 算法，数据来自本地 DB 和稳定数据源
- `fetcher-resilience`: 数据源韧性优化 — DataFetcherManager 全局单例、ETF 实时行情跳过补充字段、Akshare ETF 熔断感知、不稳定数据源优先级降级

### 修改功能

- `agent-data-tools`: `get_daily_history` 的缓存命中条件从 `latest_date >= end` 放宽为允许少量缺失天数，网络回退时传入精确 `date_range` 只拉缺口

## 影响

- **后端**: `src/services/history_loader.py`、`src/services/cyq_calculator.py`、`src/agent/tools/data_tools.py`、`src/agent/tools/search_tools.py`、`src/agent/tools/registry.py`、`data_provider/base.py`、`data_provider/akshare_fetcher.py`、`src/storage.py`
- **前端**: `apps/dsa-web/src/pages/PortfolioPage.tsx`（默认 fast=true）
- **数据库**: `StockDaily` 表新增 `turnover_rate` 列（schema 变更）、其余复用现有表
- **环境变量**: `EFINANCE_PRIORITY`、`AKSHARE_PRIORITY`、`PYTDX_PRIORITY`、`BAOSTOCK_PRIORITY`
- **破坏性变更**: 无
