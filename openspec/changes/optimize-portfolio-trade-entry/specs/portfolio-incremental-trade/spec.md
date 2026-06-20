## 新增需求

### 需求:交易写入支持增量持仓更新

`POST /api/v1/portfolio/trades` 接口必须支持 `return_snapshot` 和 `fast` 可选参数。当 `return_snapshot=true` 时，系统必须在写入交易后返回更新后的 Snapshot 数据，且必须使用增量方式计算持仓变更，禁止执行完整的历史回放。

#### 场景:买入交易增量更新

- **当** 客户端请求 `POST /api/v1/portfolio/trades` 且 `return_snapshot=true&fast=true`，提交买入交易
- **那么** 系统必须在单个数据库写事务内完成以下操作：
  1. 验证去重（trade_uid / dedup_hash）
  2. 插入交易记录
  3. 从 `PortfolioPosition` 和 `PortfolioPositionLot` 缓存表加载当前持仓
  4. 增量应用买入：FIFO 模式下追加新 lot，AVG 模式下更新加权平均成本
  5. 使用数据库缓存收盘价刷新价格（不调用外部 API）
  6. 写回更新后的缓存表
  7. 返回包含更新后 Snapshot 的响应
- **且** 响应必须包含 `snapshot` 字段，其结构与 `GET /api/v1/portfolio/snapshot` 响应一致

#### 场景:卖出交易增量更新

- **当** 客户端提交卖出交易且 `return_snapshot=true`
- **那么** 系统必须基于缓存表验证可用数量
- **且** FIFO 模式下必须按先进先出顺序消费 lot
- **且** AVG 模式下必须按加权平均成本扣减
- **且** 当可用数量不足时，必须返回 `409 portfolio_oversell` 错误

#### 场景:缓存为空时回退全量回放

- **当** 缓存表（`PortfolioPosition`、`PortfolioPositionLot`）中该账户无数据
- **那么** 系统必须回退到全量历史回放模式计算初始缓存
- **且** 回放完成后必须将结果写入缓存表以供后续增量操作使用

#### 场景:增量更新的 FIFO 精度

- **当** 连续多次买入同一股票后部分卖出，使用增量模式
- **那么** 卖出后的持仓数量必须与全量回放计算的持仓数量完全一致
- **且** 剩余 lot 的 remaining_quantity 和 unit_cost 必须与全量回放一致

#### 场景:不请求 Snapshot 时行为不变

- **当** 客户端请求 `POST /api/v1/portfolio/trades` 不含 `return_snapshot` 或 `return_snapshot=false`
- **那么** 行为必须与优化前完全一致（仅写入交易，返回 `{id: trade_id}`）

### 需求:增量更新的事务原子性

增量持仓更新的"读缓存→修改→写回"操作必须在同一个数据库写事务（`BEGIN IMMEDIATE`）内完成，确保并发安全。

#### 场景:事务内原子操作

- **当** 两个并发请求同时写入同一账户的交易
- **那么** SQLite 写锁必须确保其中一个请求在另一个完成后才开始
- **且** 第二个请求必须能看到第一个请求写入后的缓存状态
