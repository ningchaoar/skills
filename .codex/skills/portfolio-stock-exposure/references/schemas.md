# 数据结构

准备传给 `scripts/portfolio_math.py` 的数据时，使用以下结构。

## 本次持仓输入

```json
{
  "as_of": "2026-05-23",
  "positions": [
    {
      "instrument_type": "fund",
      "name": "A基金",
      "symbol": "000000",
      "market_value": 500000,
      "quantity": null,
      "current_price": null,
      "cost_price": null,
      "cost_amount": 480000,
      "currency": "CNY"
    },
    {
      "instrument_type": "stock",
      "name": "股票b",
      "symbol": "600000",
      "market_value": 500000,
      "quantity": 10000,
      "current_price": 50,
      "cost_price": 48,
      "cost_amount": 480000,
      "currency": "CNY"
    }
  ]
}
```

每条持仓的必需字段：

- `instrument_type`：`fund` 或 `stock`
- `name` 或 `symbol`：至少要有一个稳定标识
- `market_value`，或同时提供 `quantity` 和 `current_price`

仓位权重默认按当前市值计算。成本字段只用于展示和说明。

## 单一临时查询文件

本技能只维护一个运行时临时文件：

```text
.codex/skills/portfolio-stock-exposure/tmp/latest_query.json
```

每次查询前覆盖旧内容。脚本默认从该文件读取输入，并把查询结果写回同一个文件。

```json
{
  "current_positions": [
    {
      "instrument_type": "fund",
      "name": "创业板300ETF天弘",
      "symbol": "159836",
      "market_value": 128640
    }
  ],
  "fund_codes": ["159836", "515050"],
  "fund_components": {},
  "fund_component_query": {
    "provider": "eastmoney_tiantian_fund",
    "queried_at": "2026-05-23T12:00:00+00:00",
    "year": "2026"
  }
}
```

`fund_codes` 可以省略；`scripts/fund_components.py` 会从 `current_positions` 中筛选 `instrument_type == "fund"` 的 `symbol`。

## 基金成分股

```json
{
  "000000": {
    "source": "基金公司官方披露",
    "disclosure_date": "2026-03-31",
    "components": [
      {
        "symbol": "600000",
        "name": "股票a",
        "weight": 0.7
      },
      {
        "symbol": "000001",
        "name": "股票b",
        "weight": 0.2
      },
      {
        "symbol": "000002",
        "name": "股票c",
        "weight": 0.1
      }
    ]
  }
}
```

权重使用小数，不使用百分数。例如 70% 写作 `0.7`。

`compute_stock_exposure()` 会拒绝大于 `1` 的单个权重，也会拒绝合计大于 `1` 的成分股权重。如果已知成分股权重合计小于 `1`，剩余部分会保留为 `UNMAPPED_<fund_symbol>`。

## 穿透持仓输出

```json
{
  "total_market_value": 1000000,
  "exposures": [
    {
      "symbol": "000001",
      "name": "股票b",
      "market_value": 600000,
      "weight": 0.6,
      "sources": []
    }
  ]
}
```

向用户展示时，按 `weight` 或 `market_value` 从高到低排序。
