## 修改需求

### 需求:前端交易录入使用合并接口

前端交易录入 `handleTradeSubmit` 必须使用 `POST /api/v1/portfolio/trades?return_snapshot=true&fast=true` 合并接口，禁止在录入后再单独调用 `getSnapshot()`、`getRisk()` 和 `listTrades()`。

#### 场景:单次请求完成录入

- **当** 用户在持仓页面填写交易表单并点击"提交交易"
- **那么** 前端必须仅发出 1 次 HTTP 请求（`POST /api/v1/portfolio/trades` 携带 `return_snapshot=true&fast=true`）
- **且** 前端必须使用响应中的 `snapshot` 字段更新持仓列表和总览卡片
- **且** 前端禁止在录入成功后自动调用 `GET /api/v1/portfolio/risk`

#### 场景:流水列表乐观更新

- **当** 交易录入成功后
- **那么** 前端必须将新交易乐观插入到交易流水列表的顶部（不发起 `listTrades` 请求）
- **且** 当流水列表当前页超过 1 页时，必须移除列表最后一项以保持每页条数一致
- **且** 用户可以通过手动点击"刷新流水"按钮获取完整列表

#### 场景:手动刷新获取完整数据

- **当** 用户点击"刷新数据"按钮
- **那么** 前端必须使用 `GET /api/v1/portfolio/snapshot?include_risk=true&fast=false` 获取包含实时行情的完整快照和风险报告
- **且** 前端必须调用 `listTrades()` 刷新流水列表

## 移除需求

无移除需求。
