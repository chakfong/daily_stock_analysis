## 1. K 线增量补全

- [x] 1.1 `history_loader.py` 放宽缓存命中条件：`latest_date >= end` → 允许 3 个交易日缺口
- [x] 1.2 新增 `_compute_missing_range()` 函数：根据 DB 已有数据计算缺失日期范围
- [x] 1.3 修改网络回退路径：传入精确 `start_date`/`end_date` 只拉取缺失部分
- [x] 1.4 DB 写入改为追加（`save_daily_data` 已支持 upsert，确认无误）
- [ ] 1.5 编写测试：验证增量补全不会重复拉取已有数据
- [ ] 1.6 编写测试：验证 DB 有数据但缺口 > 3 天时正确回退全量拉取

## 2. 新闻 DB 优先读

- [x] 2.1 `search_tools.py` 新增 `_load_cached_news(stock_code, dimension, max_age_hours)` 函数
- [x] 2.2 `_handle_search_stock_news` 调用 API 前先查 DB 缓存，命中直接返回
- [x] 2.3 `_handle_search_comprehensive_intel` 缓存维度合并
- [x] 2.4 缓存时效默认 24 小时，支持 `freshness` 参数覆盖
- [x] 2.5 `storage.py` 新增 `get_recent_news_intel()` DB 查询方法
- [ ] 2.6 编写测试：验证 DB 有缓存时跳过外部 API

## 3. Agent 会话去重

- [x] 3.1 ToolRegistry 增加 `_session_cache` 会话级缓存
- [x] 3.2 `execute()` 调用前检查缓存 key，命中直接返回
- [x] 3.3 缓存 key 生成：`f"{tool_name}:{json.dumps(args, sort_keys=True)}"`
- [x] 3.4 `clear_session_cache()` 清理方法
- [ ] 3.5 编写测试：验证对话中去重生效

## 4. 本地 CYQ 筹码计算

- [x] 4.1 `StockDaily` 表新增 `turnover_rate` 列
- [x] 4.2 `save_daily_data` 写入时自动填充 `turnover_rate`
- [x] 4.3 新增 `src/services/cyq_calculator.py`：纯 Python 实现 CYQ 算法
- [x] 4.4 `DataFetcherManager.get_chip_distribution` fallback 链末位加入自算逻辑
- [ ] 4.5 编写测试：验证本地计算与 akshare 原始结果一致
- [ ] 4.6 编写测试：验证 DB 缺数据时自动补拉再计算

## 5. 数据源韧性

- [x] 5.1 `DataFetcherManager` 加 `get_instance()` 全局单例，消除重复 Tushare 初始化
- [x] 5.2 ETF 实时行情 tushare 成功后跳过补充字段（volume_ratio/circ_mv/amplitude）
- [x] 5.3 Akshare ETF 接口 `_get_etf_realtime_quote` 调用前检查熔断器
- [x] 5.4 `.env` 配置 `EFINANCE_PRIORITY=99` `AKSHARE_PRIORITY=3` 降级东财系数据源
- [x] 5.5 `_resolve_position_price` 新增 smart 模式（fast=None：收盘后自动用 DB 缓存）

## 6. 集成验证

- [ ] 5.1 运行现有测试确保无回归：`pytest tests/ -k agent`
- [ ] 5.2 手动测试：同一股票问两次，观察日志确认第二次走了缓存
- [ ] 5.3 手动测试：`freshness=realtime` 确认仍然调外部 API
- [ ] 5.4 手动测试：`get_chip_distribution("600519")` 确认走本地计算
