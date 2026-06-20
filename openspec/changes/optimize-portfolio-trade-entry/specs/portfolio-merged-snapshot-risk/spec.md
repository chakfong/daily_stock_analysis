## 新增需求

### 需求:Snapshot 查询可附带 Risk 报告

`GET /api/v1/portfolio/snapshot` 接口必须支持 `include_risk` 查询参数。当 `include_risk=true` 时，系统必须在一次请求中返回 Snapshot 和 Risk 报告，且 Risk 计算必须复用已生成的 Snapshot 数据，禁止重复执行完整的历史回放。

#### 场景:合并返回 Snapshot 和 Risk

- **当** 客户端请求 `GET /api/v1/portfolio/snapshot?include_risk=true`
- **那么** 响应必须包含 `risk` 字段，其结构必须与 `GET /api/v1/portfolio/risk` 的响应一致
- **且** 系统禁止在 Risk 计算中重复调用 `PortfolioService.get_portfolio_snapshot()`
- **且** 响应中的 `concentration`、`sector_concentration`、`stop_loss` 字段必须基于已计算的 Snapshot 数据填充

#### 场景:Drawdown 计算仍查历史快照表

- **当** 客户端请求 `GET /api/v1/portfolio/snapshot?include_risk=true`
- **那么** Risk 报告中的 `drawdown` 字段必须通过查询 `PortfolioDailySnapshot` 表获取历史快照序列来计算
- **且** Drawdown 计算禁止再次触发当日数据的回放

#### 场景:不包含 Risk 时行为不变

- **当** 客户端请求 `GET /api/v1/portfolio/snapshot`（不含 `include_risk` 或 `include_risk=false`）
- **那么** 响应必须仅包含 Snapshot 数据，不包含 `risk` 字段
- **且** 行为与优化前完全一致

### 需求:Risk Service 支持外部传入 Snapshot

`PortfolioRiskService` 必须提供 `get_risk_report_from_snapshot(snapshot, ...)` 方法，接收已计算好的 Snapshot 字典作为输入，禁止在此方法内部调用 `get_portfolio_snapshot()`。

#### 场景:基于已有 Snapshot 计算 Risk

- **当** 调用 `get_risk_report_from_snapshot(snapshot=precomputed_data, ...)`
- **那么** 方法必须使用传入的 `snapshot` 数据计算集中度、行业集中度、止损警告
- **且** 方法禁止调用 `self.portfolio_service.get_portfolio_snapshot()`
- **且** 返回结果必须与 `get_risk_report()` 在相同输入下产生相同输出
