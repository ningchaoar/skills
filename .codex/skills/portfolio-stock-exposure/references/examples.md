# 示例

本文件的基金成分股权重、行情和汇率是测试夹具，用于说明计算流程；不要把示例权重、价格或汇率当成最新真实数据。真实执行时必须用 `scripts/position_values.py`、`scripts/fund_components.py` 查询并写回 `tmp/latest_query.json`。

## 持仓分析

用户输入示例：

```text
我持有创业板300ETF天弘（159836）500000 元，宁德时代（300750）500000 元。
```

内部计算输入：

```python
from portfolio_math import compute_stock_exposure, normalize_positions

positions = normalize_positions([
    {
        "instrument_type": "fund",
        "name": "创业板300ETF天弘",
        "symbol": "159836",
        "market_value": 500000,
    },
    {
        "instrument_type": "stock",
        "name": "宁德时代",
        "symbol": "300750",
        "market_value": 500000,
    },
])

fund_components = {
    "159836": {
        "source": "测试夹具",
        "disclosure_date": "2026-03-31",
        "components": [
            {"symbol": "300750", "name": "宁德时代", "weight": 0.7},
            {"symbol": "300059", "name": "东方财富", "weight": 0.2},
            {"symbol": "300014", "name": "亿纬锂能", "weight": 0.1},
        ],
    }
}

exposure = compute_stock_exposure(positions, fund_components)
```

最终回答只输出数据：

```text
总市值：1000000.00

| 代码 | 名称 | 市场 | 股票维度市值 | 占比 | 来源 | 披露日期 |
|---|---|---|---:|---:|---|---|
| 300750 | 宁德时代 | CN | 850000.00 | 85.00% | 直接持股 + 基金穿透 | 2026-03-31 |
| 300059 | 东方财富 | CN | 100000.00 | 10.00% | 基金穿透 | 2026-03-31 |
| 300014 | 亿纬锂能 | CN | 50000.00 | 5.00% | 基金穿透 | 2026-03-31 |
```

不要在最终回答中解释公式或评价持仓。

## 直接美港股持仓

用户输入示例：

```text
我持有腾讯控股（00700）100 股，拼多多（PDD）2 股。
```

内部先写入：

```json
{
  "current_positions": [
    {"instrument_type": "stock", "name": "腾讯控股", "symbol": "00700", "quantity": 100},
    {"instrument_type": "stock", "name": "拼多多", "symbol": "PDD", "quantity": 2}
  ]
}
```

运行：

```bash
python scripts/position_values.py
python scripts/exposure_report.py
```

如果测试夹具价格为腾讯控股 441.40 HKD、拼多多 94.52 USD，汇率为 HKD/CNY 0.92、USD/CNY 7.20，则最终回答只输出数据：

```text
总市值：41969.89

| 代码 | 名称 | 市场 | 股票维度市值 | 占比 | 来源 | 披露日期 |
|---|---|---|---:|---:|---|---|
| 00700 | 腾讯控股 | HK | 40608.80 | 96.76% | 直接持股 | - |
| PDD | 拼多多 | US | 1361.09 | 3.24% | 直接持股 | - |
```

如果行情或汇率查询失败，只输出缺失字段清单，让用户补充人民币市值、本币价格或汇率。

## 直接股票调仓

用户输入示例：

```text
把宁德时代调到 90%，只告诉我需要买卖多少。
```

在上一个示例的穿透结果基础上，内部调用：

```python
from portfolio_math import compute_direct_stock_rebalance

direct_plan = compute_direct_stock_rebalance(
    exposure,
    target_symbol="300750",
    target_weight=0.9,
    current_price=200,
    lot_size=100,
    current_direct_market_value=500000,
)
```

最终回答只输出操作：

```text
目标：300750 宁德时代，从 85.00% 调整到 90.00%

操作路径 1：直接股票
买入/卖出：买入
标的：300750 宁德时代
数量：2500 股
金额：500000.00
取整：按 100 股向下取整
调整后目标仓位：90.00%
```

## 基金路径调仓

如果用户允许通过持有基金调仓，且目标股票是基金成分股，内部调用：

```python
from portfolio_math import compute_instrument_rebalance

fund_plan = compute_instrument_rebalance(
    exposure,
    target_symbol="300750",
    target_weight=0.9,
    instrument_symbol="159836",
    instrument_name="创业板300ETF天弘",
    instrument_target_weight=0.7,
    current_price=1,
    lot_size=100,
    current_instrument_market_value=500000,
)
```

最终回答只输出操作：

```text
操作路径 2：基金
买入/卖出：卖出
标的：159836 创业板300ETF天弘
数量：250000 份
金额：250000.00
取整：按 100 份向下取整
调整后目标仓位：90.00%
```

不要在最终回答中说明“哪条路径更好”，也不要输出投资建议。

## 未知基金敞口

如果基金查询失败，或 `fund_components["159836"]["components"]` 为空，最终回答保留未知敞口：

```text
总市值：1000000.00

| 代码 | 名称 | 市场 | 股票维度市值 | 占比 | 来源 | 披露日期 |
|---|---|---|---:|---:|---|---|
| 300750 | 宁德时代 | CN | 500000.00 | 50.00% | 直接持股 | - |

未知/未映射敞口：
| 标识 | 市值 | 占比 | 原因 |
|---|---:|---:|---|
| UNKNOWN_FUND_EXPOSURE | 500000.00 | 50.00% | 未取得 159836 的基金成分股 |
```
