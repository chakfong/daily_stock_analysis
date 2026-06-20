## 新增需求

### 需求:DataFetcherManager 全局单例

`DataFetcherManager` 必须提供 `get_instance()` 类方法返回进程级单例，避免每次创建实例时重复初始化 Tushare API（~2 秒）和重建熔断器状态。`reset_instance()` 仅供测试使用。

#### 场景:同一进程内复用实例

- **当** 多个模块（agent tools、portfolio service、history loader）分别调用 `DataFetcherManager.get_instance()`
- **那么** 所有调用必须返回同一实例
- **且** Tushare API 只初始化一次
- **且** 熔断器状态跨调用保持一致

#### 场景:测试隔离

- **当** 测试调用 `DataFetcherManager.reset_instance()`
- **那么** 下次调用 `get_instance()` 必须创建全新实例

### 需求:ETF 实时行情跳过补充字段

当实时行情源（tushare）已为 ETF 代码成功获取基本行情数据后，系统禁止继续尝试后续数据源补充 `volume_ratio`、`circ_mv`、`amplitude` 等字段，因为 ETF 基金不需要这些指标且后续源的 ETF 接口（akshare `fund_etf_spot_em`）极不稳定。

#### 场景:ETF 主源成功后直接返回

- **当** tushare 成功获取 ETF 513350 的实时行情
- **且** 该 ETF 缺少 `volume_ratio`、`circ_mv`、`amplitude` 字段
- **那么** 系统必须直接返回 tushare 数据，不继续尝试后续数据源
- **且** 不调用 `ak.fund_etf_spot_em()`

#### 场景:非 ETF 股票正常补充

- **当** tushare 成功获取 A 股 000100 的实时行情但缺少补充字段
- **那么** 系统必须继续尝试后续数据源（tencent/akshare_sina）补充缺失字段
- **且** 行为与优化前一致

### 需求:Akshare ETF 数据源熔断感知

Akshare 的 ETF 实时行情接口（`ak.fund_etf_spot_em`）必须在调用前检查专用熔断器状态。熔断器断开时直接返回 None，禁止重试浪费 12+ 秒。

#### 场景:熔断时跳过 ETF 接口

- **当** `ak.fund_etf_spot_em()` 连续失败达到熔断阈值
- **且** 后续请求需要 ETF 实时行情
- **那么** 系统必须直接返回 None
- **且** 禁止发起 HTTP 请求
- **且** 冷却时间内（300 秒）不再尝试

### 需求:数据源优先级配置

系统必须支持通过环境变量独立配置每个数据源的全局优先级，允许将不稳定数据源降级到兜底位置。

#### 场景:降级东财系数据源

- **当** `.env` 配置 `EFINANCE_PRIORITY=99` 和 `AKSHARE_PRIORITY=3`
- **那么** 全局数据源优先级必须变为 Tushare(P-1) > Pytdx(P2) > Akshare(P3) > Baostock(P3) > Yfinance(P4) > Efinance(P99)
- **且** Efinance 只在所有其他源都失败时才被调用
