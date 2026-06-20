## 新增需求

### 需求:本地筹码分布计算

系统必须提供基于本地数据的筹码分布计算能力，禁止依赖东财 HTTP 接口。计算输入为 DB 中缓存的日 K 线数据（含换手率），输出必须与现有 `ChipDistribution` Schema 完全兼容。

#### 场景:从本地数据库获取 K 线并计算筹码

- **当** Agent 调用 `get_chip_distribution(stock_code="600519")`
- **且** 数据库中该股票有至少 120 根日 K 线记录（含换手率）
- **那么** 系统必须直接从数据库读取 K 线数据
- **且** 在本地执行 CYQ 算法计算筹码分布
- **且** 禁止调用东财或任何外部 HTTP 接口
- **且** 返回的 `ChipDistribution` 必须包含 `profit_ratio`、`avg_cost`、`concentration_90`、`concentration_70`

#### 场景:数据库缺 K 线时先拉取再计算

- **当** 数据库中该股票 K 线不足 120 根或缺少换手率字段
- **那么** 系统必须先调用 `load_history_df(stock_code, days=120)` 补全数据
- **且** 补全后换手率必须一同写入数据库
- **且** 数据补全完成后执行本地筹码计算
- **且** 返回计算结果

#### 场景:数据源 fallback 链

- **当** DataFetcherManager 的 `get_chip_distribution` 被调用
- **那么** 系统必须按以下优先级尝试：Akshare(东财) → Tushare(需积分) → 本地自算
- **且** 本地自算作为终极兜底，必须永不失败（只要 DB 有 K 线数据）
- **且** 筹码数据源熔断器对本地自算无效（本地计算不会触发限流）

### 需求:StockDaily 表存储换手率

`StockDaily` 数据库表必须新增 `turnover_rate` 字段，用于存储每日换手率数据。`save_daily_data` 方法必须在原始 DataFrame 包含换手率字段时将其一并写入。

#### 场景:K线数据入库时保存换手率

- **当** DataFetcherManager 获取日 K 线数据并返回包含 `turnover_rate` 列的 DataFrame
- **且** 调用 `save_daily_data(df, code, source)` 保存数据
- **那么** 换手率数据必须被写入 `StockDaily.turnover_rate` 字段
- **且** 存量数据中换手率为空时不影响其他字段的正常读写

#### 场景:存量数据兼容

- **当** 数据库中已存在某股票的历史 K 线记录但 `turnover_rate` 为空
- **那么** 下次拉取新数据时必须回填换手率
- **且** 筹码计算时若换手率缺失，必须使用成交量/流通市值估算
