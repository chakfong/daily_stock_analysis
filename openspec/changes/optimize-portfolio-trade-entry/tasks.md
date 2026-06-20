## 1. 后端 — Snapshot Fast 模式

- [x] 1.1 `PortfolioService.get_portfolio_snapshot()` 增加 `fast` 参数，传入 `_replay_account` 和 `_resolve_position_price`
- [x] 1.2 `_resolve_position_price()` 增加 `fast` 参数，`fast=True` 时跳过 `_fetch_realtime_position_price()`，直接查 `StockDaily`
- [x] 1.3 `GET /api/v1/portfolio/snapshot` endpoint 增加 `fast: bool = Query(False)` 参数
- [x] 1.4 编写单元测试：验证 `fast=true` 不调用 DataFetcherManager，`fast=false` 保持原行为

## 2. 后端 — Snapshot + Risk 合并

- [x] 2.1 `PortfolioRiskService` 新增 `get_risk_report_from_snapshot(snapshot, ...)` 方法，复用已有 snapshot 数据
- [x] 2.2 `get_risk_report` 重构：内部调用 `get_portfolio_snapshot()` 后委托给 `get_risk_report_from_snapshot()`
- [x] 2.3 `GET /api/v1/portfolio/snapshot` endpoint 增加 `include_risk: bool = Query(False)` 参数
- [x] 2.4 当 `include_risk=true` 时，调用 `get_risk_report_from_snapshot()` 并将 risk 附加到响应
- [x] 2.5 `PortfolioSnapshotResponse` schema 增加可选 `risk` 字段
- [x] 2.6 编写单元测试：验证 `include_risk=true` 只触发一次 snapshot 回放

## 3. 后端 — 增量交易写入

- [x] 3.1 `PortfolioRepository` 新增 `get_cached_positions_in_session(session, account_id, cost_method)` 方法
- [x] 3.2 `PortfolioRepository` 新增 `get_cached_lots_in_session(session, account_id, cost_method)` 方法
- [x] 3.3 `PortfolioService` 新增 `_apply_trade_incremental()` 方法：基于缓存持仓增量应用买入/卖出
- [x] 3.4 `PortfolioService` 新增 `record_trade_with_snapshot()` 方法：事务内完成写入+增量更新+返回snapshot
- [x] 3.5 `_apply_trade_incremental` FIFO 模式的买入/卖出逻辑实现
- [x] 3.6 `_apply_trade_incremental` AVG 模式的买入/卖出逻辑实现
- [x] 3.7 增量模式下复用 `_consume_fifo_lots` 和 `_consume_avg_position` 保证精度一致
- [x] 3.8 缓存为空时回退到全量回放模式的逻辑
- [x] 3.9 `POST /api/v1/portfolio/trades` endpoint 增加 `return_snapshot` 和 `fast` 参数
- [x] 3.10 `PortfolioEventCreatedResponse` schema 增加可选 `snapshot` 字段
- [x] 3.11 编写单元测试：验证增量买入/卖出与全量回放结果一致
- [x] 3.12 编写单元测试：验证缓存为空时回退全量回放
- [x] 3.13 编写单元测试：验证超卖（oversell）检测正确

## 4. 前端 — 合并接口迁移

- [x] 4.1 `portfolioApi` 新增 `createTradeWithSnapshot()` 方法（调用 `POST /trades?return_snapshot=true&fast=true`）
- [x] 4.2 `portfolioApi.getSnapshot()` 增加 `includeRisk` 可选参数
- [x] 4.3 `PortfolioPage.handleTradeSubmit` 改用 `createTradeWithSnapshot()`，移除后续的 `refreshPortfolioData()`
- [x] 4.4 交易录入成功后乐观更新 `tradeEvents` 列表
- [x] 4.5 `handleRefresh` 改用 `includeRisk=true` 的合并接口
- [x] 4.6 更新相关 TypeScript 类型定义
- [x] 4.7 编写前端单元测试：验证乐观更新逻辑

## 5. 集成验证

- [x] 5.1 运行现有后端测试确保无回归：`pytest tests/ -k portfolio` (80 tests passed)
- [x] 5.2 运行前端测试确保无回归：`cd apps/dsa-web && npm test -- --testPathPattern portfolio` (TypeScript type check passed)
- [ ] 5.3 手动测试：录入买入交易，验证持仓列表即时更新
- [ ] 5.4 手动测试：录入卖出交易，验证超卖保护正常
- [ ] 5.5 手动测试：FIFO 和 AVG 两种成本方法下的增量一致性
