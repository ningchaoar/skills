---
name: portfolio-stock-exposure
description: 将用户上传图片或粘贴文本中的中国内地基金和股票持仓，实时转换为股票维度的穿透持仓占比；当用户要求把某只股票提高或降低到目标仓位时，计算机械调仓所需的股票或基金交易量。适用于 A 股、中国内地公募基金持仓截图或文字、基金穿透到股票维度的敞口分析、目标仓位调仓计算。除非用户明确扩展范围，否则不要用于美股、海外 ETF、QDII 或全球基金。
---

# 股票维度穿透持仓

## 范围

使用本技能将用户本次提供的基金和股票持仓转换为股票维度的实际敞口。默认支持范围是中国内地公募基金以及 A 股或中国上市股票。港股、美股、QDII、海外 ETF、债券、现金、衍生品默认视为范围外，除非用户明确要求扩展。

本技能只做确定性的持仓数学计算，不做投资判断。不要评价证券好坏，不要主动建议买什么或卖什么。只提取持仓、获取或请求基金成分股、计算穿透敞口，并在用户指定目标仓位时计算交易量。

## 意图判断

首先判断用户请求属于哪一种：

- 意图 A，持仓分析：用户想知道当前持仓，上传持仓图片，粘贴持仓文字，询问“真实股票占比”“穿透持仓”等。
- 意图 B，调仓计算：用户明确要求把某只股票提高或降低到某个目标百分比，或询问应该买入/卖出多少股票或基金份额。

如果意图不明确，先问一个澄清问题再计算。如果用户同时提供持仓并要求调仓，先把本次输入作为当前持仓，再基于它计算调仓。

## 数据提取

从图片或文字中提取每一只基金和股票，并整理为标准持仓列表。必需字段：

- `instrument_type`：`fund` 或 `stock`
- `name`：基金或证券名称
- `symbol`：股票代码、基金代码，或截图中可见的稳定标识
- `market_value`：当前持仓市值

可选字段：

- `quantity`
- `current_price`
- `cost_price`
- `cost_amount`
- `currency`

默认使用 `market_value` 作为仓位计算基准。成本字段只保留用于报告，不用于当前仓位权重计算，除非用户明确要求“按成本计算”。如果缺少 `market_value`，但有 `quantity` 和 `current_price`，用 Python helper 计算市值。如果关键字段缺失，先请用户补充，不要继续计算。

JSON 结构和示例见 `references/schemas.md`。

## 实时数据流程

每次执行时，都以用户本次上传的图片或粘贴的文字作为当前持仓数据。本技能不维护本地持仓状态。

如果用户没有在本次请求中提供持仓明细，但要求分析或调仓，先请用户上传截图或粘贴当前持仓。

把本次查询状态写入单一临时文件：

```text
.codex/skills/portfolio-stock-exposure/tmp/latest_query.json
```

只维护这一个临时文件。每次新查询都覆盖旧内容。需要运行脚本时，脚本默认从这个文件读取输入，并把查询结果写回同一个文件。

写入本次持仓输入：

```python
from query_state import write_latest_query

write_latest_query({
    "current_positions": current_positions,
    "fund_codes": ["159836", "515050"]
})
```

## 基金成分股

在做股票维度穿透计算之前，先获取基金成分股及其权重。优先使用官方或一手来源。每组基金成分股都必须记录 `source` 和 `disclosure_date`。

- ETF：优先使用官方每日持仓或 PCF 数据。
- 普通公募基金：使用最新公开披露持仓，并说明披露日期。
- 缺失或过期数据：不要编造成分股权重，把该基金市值保留为 `UNKNOWN_FUND_EXPOSURE`。
- 非股票部分：现金、债券、未映射部分要保留为单独 bucket，不要强行摊到股票里。

获取或解释基金成分股前，先阅读 `references/data-source-policy.md`。

已脚本化的默认查询路径：

```bash
python scripts/fund_components.py
```

该脚本默认读取 `tmp/latest_query.json` 中的 `fund_codes` 或 `current_positions`，通过东方财富/天天基金公开页面查询基金股票持仓，并把 `fund_components` 写回同一个临时文件。也可以直接指定基金代码：

```bash
python scripts/fund_components.py --fund-codes 159836 515050 --year 2025
```

如果网络不可用、页面结构变化、或基金没有公开股票持仓，脚本失败后不要猜测；把该基金作为未知基金敞口处理。

## 计算流程

最终计算必须运行 Python helper。不要在正文里手算最终百分比。

```python
from portfolio_math import (
    compute_direct_stock_rebalance,
    compute_instrument_rebalance,
    compute_stock_exposure,
    normalize_positions,
)

positions = normalize_positions(current_positions)
exposure = compute_stock_exposure(positions, fund_components)
```

持仓分析输出：

- 总市值
- 按权重排序的股票维度穿透持仓表
- 未知或未映射的基金敞口
- 每只基金成分股数据来源和披露日期
- 关键假设和缺失字段

## 调仓流程

处理调仓请求时，先基于本次输入展示股票维度穿透持仓。然后判断目标股票是只存在于直接股票持仓中、存在于一个或多个已持有基金中，还是当前完全不存在。

如果目标股票不在任何已持有基金成分股中：

- 使用 `compute_direct_stock_rebalance()` 计算直接买入或卖出股票数量。
- 如果用户没有说明资金假设，先确认是外部现金流入/流出，还是不增加资金的组合内调仓。helper 默认买入时外部现金流入，卖出时资金流出。
- 如果直接卖出，且目标股票敞口也来自基金，必须传入 `current_direct_market_value`，避免把基金穿透出来的目标股票敞口误当成可卖股票。

如果已持有基金包含目标股票：

- 用 `compute_direct_stock_rebalance()` 计算直接股票路径。
- 对每只包含目标股票的已持有基金，用 `compute_instrument_rebalance()` 计算单基金交易路径。
- 同时展示直接股票路径和基金路径。明确说明买卖基金会改变该基金所有其他成分股的敞口，不只影响目标股票。

计算完成后输出：

- 目标股票当前仓位
- 用户要求的目标仓位
- 买入/卖出动作、金额、股票数量或基金份额，且说明交易单位取整
- 取整后的最终目标股票仓位
- 如果成分股数据足够，给出调整后的完整股票维度持仓

## 输出规则

默认使用简洁中文输出。金融计算必须可审计：

- 公式只在能帮助解释结果时给出
- 必须给出基金成分股来源日期
- 明确标注过期、缺失或未知敞口
- 除非来源确实提供当前日期的数据，不要声称“当日最新”
- 说明结果是持仓数学计算，不是个性化投资建议

完整示例见 `references/examples.md`。
