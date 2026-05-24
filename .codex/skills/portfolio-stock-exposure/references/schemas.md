# 数据结构

准备写入单一临时查询文件、运行脚本入口或调用计算函数时，使用以下结构。`scripts/query_state.py`、`scripts/portfolio_math.py` 和 `scripts/script_utils.py` 只供 import，不作为命令入口运行。

## 本次持仓输入

从图片或文本提取后的持仓列表放入 `current_positions`。传给 `normalize_positions()` 或 `compute_stock_exposure()` 时，直接传这个列表。

```json
[
  {
    "instrument_type": "fund",
    "name": "创业板300ETF天弘",
    "symbol": "159836",
    "market_value": 128640,
    "quantity": 120000,
    "current_price": 1.072,
    "cost_price": 1.052,
    "cost_amount": 126240,
    "currency": "CNY"
  },
  {
    "instrument_type": "stock",
    "name": "宁德时代",
    "symbol": "300750",
    "market": "CN",
    "market_value": 98640,
    "quantity": 500,
    "current_price": 197.28,
    "cost_price": 185.6,
    "cost_amount": 92800,
    "currency": "CNY"
  },
  {
    "instrument_type": "stock",
    "name": "腾讯控股",
    "symbol": "00700",
    "market": "HK",
    "quantity": 100,
    "currency": "HKD"
  },
  {
    "instrument_type": "stock",
    "name": "拼多多",
    "symbol": "PDD",
    "market": "US",
    "quantity": 2,
    "currency": "USD"
  }
]
```

每条持仓的必需字段：

- `instrument_type`：`fund` 或 `stock`
- `name` 或 `symbol`：至少要有一个稳定标识
- `market_value`，或直接股票同时提供 `quantity` 和可查询/可填写的 `current_price`

仓位权重默认按人民币 `market_value` 计算。成本字段只保留为原始信息，不参与仓位权重计算。

## 直接股票估值补全

运行 `scripts/position_values.py` 后，直接股票缺失的人民币市值会写回 `current_positions`。

```json
{
  "instrument_type": "stock",
  "name": "拼多多",
  "symbol": "PDD",
  "market": "US",
  "quantity": 2,
  "currency": "USD",
  "current_price": 94.52,
  "local_market_value": 189.04,
  "fx_rate_to_cny": 7.2,
  "market_value": 1361.088,
  "quote_source": "东方财富",
  "quote_source_url": "https://push2.eastmoney.com/api/qt/stock/get?...",
  "quote_checked_at": "2026-05-24T12:00:00+00:00",
  "fx_source": "Frankfurter",
  "fx_source_url": "https://api.frankfurter.app/latest?from=USD&to=CNY",
  "fx_date": "2026-05-22"
}
```

`market` 使用 `CN`、`HK`、`US`。`currency` 使用 `CNY`、`HKD`、`USD`。`market_value` 始终是人民币口径。

## 单一临时查询文件

本技能只维护一个运行时临时文件：

```text
.codex/skills/portfolio-stock-exposure/tmp/latest_query.json
```

每次查询前覆盖旧内容。脚本默认从该文件读取输入，并把查询结果写回同一个文件。用 `query_state.write_latest_query()` 写入，避免路径和编码不一致；需要打印或记录路径时使用 `query_state.resolve_query_path()`，不要为了取得路径再次写文件。

```json
{
  "current_positions": [
    {
      "instrument_type": "fund",
      "name": "创业板300ETF天弘",
      "symbol": "159836",
      "market_value": 128640
    },
    {
      "instrument_type": "fund",
      "name": "通信ETF华夏",
      "symbol": "515050",
      "market_value": 84320
    }
  ],
  "fund_codes": ["159836", "515050"],
  "fund_components": {},
  "fund_component_query": {
    "provider": "eastmoney_tiantian_fund",
    "queried_at": "2026-05-23T12:00:00+00:00",
    "year": "2026"
  },
  "position_value_query": {
    "base_currency": "CNY",
    "queried_at": "2026-05-24T12:00:00+00:00"
  }
}
```

`fund_codes` 可以省略；`scripts/fund_components.py` 会从 `current_positions` 中筛选 `instrument_type == "fund"` 的 `symbol`。

## 基金成分股

`scripts/fund_components.py` 写回的 `fund_components` 以基金代码为 key。

```json
{
  "159836": {
    "source": "东方财富-天天基金",
    "source_url": "https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code=159836&topline=100&year=2026&month=",
    "disclosure_date": "2026-03-31",
    "fund_code": "159836",
    "components": [
      {
        "symbol": "300750",
        "name": "宁德时代",
        "market": "CN",
        "weight": 0.082,
        "raw_weight_percent": 8.2,
        "quarter": "2026-03-31",
        "shares_10k": 36.5,
        "market_value_10k": 7201.3
      }
    ]
  }
}
```

权重使用小数，不使用百分数字符串。例如 8.2% 写作 `0.082`。

`market` 使用 `CN`、`HK`、`US` 或 `null`。东方财富脚本会按代码格式推断：6 位数字为 `CN`，5 位数字为 `HK`，美股 ticker 为 `US`。

`raw_weight_percent`、`shares_10k`、`market_value_10k` 是数据源原始展示字段，只用于追溯。实际穿透计算只使用 `weight`。

`compute_stock_exposure()` 会拒绝大于 `1` 的单个权重，也会拒绝合计大于 `1` 的成分股权重。如果已知成分股权重合计小于 `1`，剩余部分会保留为 `UNMAPPED_<fund_symbol>`。如果没有可用成分股，整只基金保留为 `UNKNOWN_FUND_EXPOSURE`。

## 穿透持仓输出

```json
{
  "total_market_value": 1000000,
  "exposures": [
    {
      "symbol": "300750",
      "name": "宁德时代",
      "market": "CN",
      "market_value": 184000,
      "weight": 0.184,
      "sources": [
        {
          "type": "direct_stock",
          "symbol": "300750",
          "name": "宁德时代",
          "market": "CN",
          "market_value": 98640
        },
        {
          "type": "fund_component",
          "fund_symbol": "159836",
          "fund_name": "创业板300ETF天弘",
          "market": "CN",
          "component_weight": 0.082,
          "source": "东方财富-天天基金",
          "disclosure_date": "2026-03-31"
        }
      ]
    }
  ]
}
```

向用户展示时，按 `weight` 或 `market_value` 从高到低排序，并保留来源类型和基金成分股披露日期。

## 调仓计算输出

`compute_direct_stock_rebalance()` 返回直接股票路径：

```json
{
  "target_symbol": "300750",
  "target_name": "宁德时代",
  "action": "buy",
  "shares": 100,
  "trade_amount": 19728,
  "current_total_market_value": 1000000,
  "current_target_market_value": 184000,
  "current_target_weight": 0.184,
  "target_weight": 0.2,
  "theoretical_trade_amount": 20000,
  "final_total_market_value": 1019728,
  "final_target_market_value": 203728,
  "final_target_weight": 0.1997897476591802,
  "rounding": {
    "lot_size": 100,
    "current_price": 197.28,
    "policy": "floor to avoid crossing the target by default"
  }
}
```

`compute_instrument_rebalance()` 返回基金路径，字段与直接路径类似，但数量字段为 `units`，并包含 `instrument_symbol`、`instrument_name`、`instrument_target_weight`。

向用户展示时，只输出操作所需字段：买入/卖出、标的、数量或份额、金额、取整规则、调整后目标仓位。不要展示公式推导，除非用户明确要求。

## 东方财富接口探测输出

`scripts/eastmoney_interface_probe.py` 用于手动检查公开网页端点是否仍可解析。它不是默认持仓分析流程的一部分。

```json
{
  "stable": true,
  "reports": [
    {
      "fund_code": "159836",
      "year": "2026",
      "attempts": 3,
      "successful_attempts": 3,
      "stable": true,
      "reason": "ok",
      "stability": {
        "stable": true,
        "reason": "ok",
        "component_count": 100,
        "disclosure_date": "2026-03-31",
        "top_symbols": ["300750", "300308", "300502", "300059", "300274"]
      },
      "timings_seconds": [0.63, 0.58, 0.61],
      "errors": [],
      "checked_at": "2026-05-23T12:00:00+00:00"
    }
  ]
}
```

该输出只用于维护脚本稳定性，不作为用户持仓分析的最终输出。
