## 为什么

用户在前端持仓页面每次手工录入交易时，系统会触发完整的历史数据回放（全部交易/资金/公司行为从头重演）并重复计算两次，同时串行调用外部实时行情 API。随着交易笔数增长，单次录入耗时从几百毫秒膨胀到数秒甚至更长，严重降低使用体验。当前架构无法支撑日常高频录入场景，需要在写入路径上做增量优化。

## 变更内容

- 消除 Snapshot + Risk 的重复全量回放：新增合并接口，Risk 复用已计算的 Snapshot 结果
- Snapshot 增加 `fast` 模式，跳过实时行情外部 API 调用，仅使用数据库缓存收盘价
- 新增 `record_trade_with_snapshot` 后端方法，将"写入交易 + 返回快照"合并为一次数据库事务内的增量操作
- 增量持仓计算引擎：基于缓存的 `PortfolioPosition`/`PortfolioPositionLot` 表直接在缓存上应用增量变更，不再做全量历史回放
- 前端改用合并接口：一次 HTTP 请求完成交易录入 + 快照刷新，乐观更新流水列表
- 交易录入后不再自动触发 Risk 重算

## 功能 (Capabilities)

### 新增功能

- `portfolio-fast-snapshot`: Snapshot 查询支持 `fast` 参数，跳过实时行情外部 API 调用，仅使用数据库缓存的历史收盘价
- `portfolio-merged-snapshot-risk`: 新增合并接口，支持在一次 Snapshot 查询中同时返回 Risk 报告，避免后端重复计算
- `portfolio-incremental-trade`: 交易写入支持增量持仓更新模式，不再做全量历史回放，而是基于缓存表增量应用变更

### 修改功能

- `portfolio-trade-entry`: 前端交易录入流程变更 — 从 4 次 HTTP 请求改为 1 次合并请求，录入后不自动刷新 Risk，流水列表采用乐观更新

## 影响

- **后端**: `api/v1/endpoints/portfolio.py`（新增/修改 endpoint）、`src/services/portfolio_service.py`（新增增量方法）、`src/services/portfolio_risk_service.py`（新增接收已有 snapshot 的方法）、`src/repositories/portfolio_repo.py`（新增缓存读取方法）
- **前端**: `apps/dsa-web/src/api/portfolio.ts`（新 API 方法）、`apps/dsa-web/src/pages/PortfolioPage.tsx`（修改提交流程）
- **数据库**: 无 schema 变更，利用现有 `PortfolioPosition`/`PortfolioPositionLot`/`PortfolioDailySnapshot` 缓存表
- **破坏性变更**: 无
