## 新增需求

### 需求:Snapshot 支持快速模式

`GET /api/v1/portfolio/snapshot` 接口必须支持 `fast` 查询参数。当 `fast=true` 时，系统禁止调用任何外部实时行情 API，必须仅使用数据库缓存的历史收盘价来填充持仓的 `last_price` 字段。

#### 场景:快速模式跳过实时行情

- **当** 客户端请求 `GET /api/v1/portfolio/snapshot?fast=true`
- **那么** 系统禁止调用 `DataFetcherManager.get_realtime_quote()`
- **且** 每个持仓的 `last_price`、`price_source`、`price_date` 必须来自 `StockDaily` 表的最新收盘记录
- **且** 响应中 `price_source` 字段必须为 `"history_close"` 或 `"missing"`

#### 场景:普通模式保持实时行情

- **当** 客户端请求 `GET /api/v1/portfolio/snapshot`（不含 `fast` 参数或 `fast=false`）
- **那么** 系统必须在 `as_of_date == today` 时尝试获取实时行情
- **且** 实时行情获取失败时，必须回退到历史收盘价

#### 场景:Fast 模式下 as_of 为历史日期

- **当** 客户端请求 `GET /api/v1/portfolio/snapshot?fast=true&as_of=2025-01-01`
- **那么** 系统必须使用历史收盘价（因为非当日无需实时行情）
- **且** 行为与普通模式相同（fast 不影响历史日期的查询）
