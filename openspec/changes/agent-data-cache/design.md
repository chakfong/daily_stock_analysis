## 上下文

当前 Agent 工具的数据流：

```
Agent 调用工具 → 工具处理函数 → 外部 API → 写入 DB（部分已实现）
                                    ↑
                              每次调用都走这里
```

- `get_daily_history`：调用 `load_history_df` → 先查 DB → 如缓存不够新鲜则走 DataFetcherManager 全量拉取 → 写回 DB
- `search_stock_news` / `search_comprehensive_intel`：调用 SerpAPI/Tavily → `_persist_news_response` 写 DB，但读路径从未查 DB
- 其他工具（板块、筹码）：无缓存，每次调外部 API

实际日志分析显示：同一次问股中 002837 被调 4 次 K 线（不同窗口参数）、2 次实时行情，5 次新闻搜索累计 36 秒。根源是 DB 中有数据但不被优先读取。

## 目标 / 非目标

**目标：**
- K 线数据：DB 优先，仅补全缺口（增量），不再因窗口大小不同重复拉取
- 新闻数据：调用外部 API 前先查 DB，有近期数据直接返回
- Agent 会话内：相同工具+参数去重，避免 LLM 重复调用
- 筹码分布：默认跳过（当前成功率 ~0%，每次浪费 5-10s）

**非目标：**
- 不改变 LLM 调用策略
- 不引入 Redis/外部缓存服务
- 不修改数据库 schema
- 实时行情不做永久缓存（价格时变）

## 决策

### 决策 1：K 线增量策略

**选择**：DB 有数据时只拉缺口，不重拉已有数据

`history_loader.py` 当前逻辑：`latest_date >= end` 才命中。改为：DB 有数据即使用，用 `df` 覆盖范围判断是否需要补拉。如需补拉，DataFetcherManager 传入精确 `start_date` 只拉缺口。

**替代方案**：保持全量拉取但增加 TTL 缓存。缺点是同样浪费 API 调用，只是频率降低。

### 决策 2：新闻 DB 优先读

**选择**：`search_tools.py` 的 `_handle_search_*` 函数增加 DB 查询步骤

在调用 SerpAPI 前，先 `db.get_news_intel(code, dimension, since=<N hours ago>)`，如果有近期新闻直接返回。维度（`dimension`）作为缓存键区分不同搜索意图。

**替代方案**：在 search_service 层做缓存。缺点是 search_service 不知道 Agent 上下文，难以按维度区分。

### 决策 3：会话级工具去重

**选择**：在 Agent 执行上下文中维护 `_tool_results: Dict[str, Any]` 字典

Key = `f"{tool_name}:{json.dumps(args, sort_keys=True)}"`。同一会话中再次调用相同工具+参数时直接返回缓存结果。存储在 `agent_chat_store` 或 executor 上下文中，会话结束即清理。

### 决策 4：筹码分布跳过

**选择**：`_handle_get_chip_distribution` 增加熔断感知

检查 Akshare 筹码数据源的熔断器状态，如果已熔断直接返回 `{"status": "skipped", "reason": "circuit_breaker_open"}`，不尝试调用。

### 决策 5：本地 CYQ 计算

**选择**：新增 `src/services/cyq_calculator.py`，用纯 Python 实现陈浩 CYQ 模型

输入：DataFrame[date, open, high, low, close, volume, turnover_rate] × 120 根 K 线
输出：ChipDistribution（与现有 Schema 兼容）

核心逻辑：
1. 价格区间划分（high~low 均匀分 150 格）
2. 每日成交量按价格区间分布
3. 换手率作为当日筹码转移比例，旧筹码按 (1 - 换手率) 衰减
4. 累加多日得成本分布直方图
5. 从中计算获利比例/平均成本/90%集中度/70%集中度

数据来源：DB 中 StockDaily 表（已有 K 线，新增 turnover_rate 列），不足时通过 `load_history_df` 补拉 Tushare/Pytdx。

StockDaily 加 `turnover_rate` 列：SQLite ALTER TABLE ADD COLUMN，`save_daily_data` 写入时自动填。

### 决策 6：筹码 fallback 链

**选择**：Akshare(东财) → Tushare(需积分) → 本地自算

本地自算作为终极兜底，不受东财反爬影响，只要 DB 有 K 线就能算。

## 风险 / 权衡

- [K 线增量可能漏数据] → **缓解**：DB 查询时检查连续性，如有断档一并补拉
- [换手率估算精度] 存量数据可能缺少 turnover_rate → **缓解**：用 volume × avg_price / circ_mv 估算，或从实时行情补
- [新闻时效性] → **缓解**：`freshness` 参数支持强制跳过缓存
- [会话去重可能过激] → **缓解**：去重 key 使用标准化参数

## 迁移计划

1. StockDaily 加 `turnover_rate` 列（schema 变更，向后兼容）
2. 新增 `cyq_calculator.py`
3. 改 `history_loader.py` 增量补全
4. 改 `search_tools.py` 新闻 DB 优先读
5. 改 `data_tools.py` 筹码改用本地计算
6. Agent 会话去重
7. 回滚：每步独立可逆
