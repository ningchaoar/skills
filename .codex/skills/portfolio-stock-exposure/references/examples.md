# 示例

## 持仓分析

输入：

- A基金市值 500000
- 股票b 市值 500000
- A基金成分股：股票a 70%，股票b 20%，股票c 10%

Python：

```python
from portfolio_math import compute_stock_exposure, normalize_positions

positions = normalize_positions([
    {"instrument_type": "fund", "name": "A基金", "symbol": "FUND_A", "market_value": 500000},
    {"instrument_type": "stock", "name": "股票b", "symbol": "STOCK_B", "market_value": 500000},
])

fund_components = {
    "FUND_A": {
        "source": "示例数据",
        "disclosure_date": "2026-03-31",
        "components": [
            {"symbol": "STOCK_A", "name": "股票a", "weight": 0.7},
            {"symbol": "STOCK_B", "name": "股票b", "weight": 0.2},
            {"symbol": "STOCK_C", "name": "股票c", "weight": 0.1},
        ],
    }
}

exposure = compute_stock_exposure(positions, fund_components)
```

预期股票维度穿透持仓：

- 股票a：350000，35%
- 股票b：600000，60%
- 股票c：50000，5%

## 直接股票调仓

如果股票a 当前是 1000000 组合中的 350000，用户想提高到 40%，且只通过外部现金买入股票a：

```text
(350000 + x) / (1000000 + x) = 0.40
x = 83333.33，未按交易单位取整
```

如果股价为 10，交易单位为 100 股，则买入 8300 股，金额 83000。最终仓位：

```text
(350000 + 83000) / (1000000 + 83000) = 39.9815%
```

## 基金路径调仓

如果 A基金中股票a 权重为 70%，通过买入 A基金把股票a 从 35% 提高到 40%：

```text
(350000 + 0.70x) / (1000000 + x) = 0.40
x = 166666.67，未按交易单位取整
```

如果基金价格为 1，交易单位为 100 份，则买入 166600 份，金额 166600。最终股票a 仓位：

```text
(350000 + 0.70 * 166600) / (1000000 + 166600) = 39.9983%
```

必须说明：买入该基金也会同步增加该基金其他成分股的敞口。
