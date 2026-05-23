---
name: portfolio-stock-exposure
description: 将用户上传图片或粘贴文本中的中国内地基金和股票持仓，实时转换为股票维度的穿透持仓占比；当用户要求把某只股票提高或降低到目标仓位时，计算机械调仓所需的股票或基金交易量。适用于 A 股、中国内地公募基金持仓截图或文字、基金穿透到股票维度的敞口分析、目标仓位调仓计算。除非用户明确扩展范围，否则不要用于美股、海外 ETF、QDII 或全球基金。
---

# 股票维度穿透持仓

## 基本原则

本技能只做确定性的持仓数据计算，不做投资判断。最终回答只能输出持仓数据结果或具体调仓操作。

默认范围：

- 中国内地公募基金
- A 股或中国上市股票
- 人民币计价持仓

默认不处理：

- 美股、海外 ETF、QDII、全球基金
- 多币种换算
- 债券、现金、衍生品的进一步拆分

如果用户要求扩展默认范围，先确认数据源和币种换算口径。

## 第 1 步：判断用户意图

每次触发本技能后，先判断用户意图，只能归入以下两类之一。

### 意图 A：持仓分析

用户想知道当前基金和股票持仓穿透到股票维度后的结果。

典型表达：

- 上传持仓截图
- 粘贴持仓文字
- 询问“真实股票占比”
- 询问“穿透持仓”
- 要求“看一下当前股票维度持仓”

### 意图 B：调仓计算

用户明确指定某只股票的目标仓位，并要求计算如何买入或卖出。

典型表达：

- “把宁德时代调到 15%”
- “把东方财富降到 5%”
- “要买多少股才能到目标仓位”
- “是否可以通过买入基金实现目标仓位”

### 意图不明确时

只问一个澄清问题：

```text
你是想做“持仓分析”，还是想计算某只股票调到目标仓位的具体买卖操作？
```

不要在意图不明确时继续计算。

## 第 2 步：通用前置流程

意图 A 和意图 B 都必须先执行本节流程。

### 2.1 提取本次持仓

从用户本次上传的图片或粘贴的文字中提取每一条基金和股票持仓。

每条持仓整理为：

```json
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
}
```

必需字段：

- `instrument_type`：`fund` 或 `stock`
- `name`：基金或股票名称
- `symbol`：基金代码或股票代码
- `market_value`：当前持仓市值

如果缺少 `market_value`，但有 `quantity` 和 `current_price`，用脚本计算市值。

如果缺少名称、代码、市值，且无法从数量和现价推导市值，停止并只输出缺失字段清单，让用户补充。

### 2.2 写入单一临时文件

本技能只维护一个临时文件：

```text
.codex/skills/portfolio-stock-exposure/tmp/latest_query.json
```

每次执行都覆盖旧内容。需要运行脚本时，脚本默认从这个文件读取输入，并把查询结果写回同一个文件。

写入示例：

```python
from query_state import write_latest_query

write_latest_query({
    "current_positions": current_positions,
    "fund_codes": ["159836", "515050"]
})
```

### 2.3 查询基金成分股

如果本次持仓中包含基金，运行：

```bash
python scripts/fund_components.py
```

脚本行为：

- 从 `tmp/latest_query.json` 读取 `fund_codes` 或 `current_positions`
- 查询东方财富/天天基金公开页面
- 解析基金股票持仓
- 将 `fund_components` 写回同一个 `tmp/latest_query.json`

也可以直接指定基金代码：

```bash
python scripts/fund_components.py --fund-codes 159836 515050 --year 2025
```

如果网络不可用、页面结构变化、基金没有公开股票持仓，或脚本没有返回可用成分股，不要猜测。该基金记为 `UNKNOWN_FUND_EXPOSURE`。

### 2.4 运行穿透计算

最终计算必须调用 Python，不要手算最终百分比。

```python
from portfolio_math import compute_stock_exposure, normalize_positions

positions = normalize_positions(current_positions)
exposure = compute_stock_exposure(positions, fund_components)
```

计算口径：

- 使用当前市值 `market_value` 计算仓位。
- 成本价和成本金额只保留为原始信息，不参与仓位权重计算。
- 基金成分股权重使用小数，例如 8.2% 写作 `0.082`。
- 基金无法穿透的部分保留为 `UNKNOWN_FUND_EXPOSURE` 或 `UNMAPPED_<fund_code>`。

## 意图 A 工作流：持仓分析

按以下步骤执行。

### A1. 完成通用前置流程

先完成：

1. 提取本次持仓
2. 写入 `tmp/latest_query.json`
3. 查询基金成分股
4. 运行 `compute_stock_exposure()`

### A2. 整理输出数据

将 `compute_stock_exposure()` 的结果整理成表格。

输出字段只包含：

- 股票代码
- 股票名称
- 股票维度市值
- 股票维度占比
- 来源：直接持股、基金穿透、未知基金敞口、未映射基金部分
- 基金成分股披露日期

### A3. 最终输出格式

最终回答只输出数据，不输出分析。

推荐格式：

```text
总市值：xxx.xx

| 代码 | 名称 | 股票维度市值 | 占比 | 来源 | 披露日期 |
|---|---:|---:|---:|---|---|
| 300750 | 宁德时代 | xxx.xx | xx.xx% | 直接持股 + 基金穿透 | 2025-12-31 |

未知/未映射敞口：
| 标识 | 市值 | 占比 | 原因 |
|---|---:|---:|---|
| UNKNOWN_FUND_EXPOSURE | xxx.xx | xx.xx% | 未取得基金成分股 |
```

不要输出：

- 行业分析
- 个股评价
- 投资建议
- 背景说明
- 公式推导

## 意图 B 工作流：调仓计算

按以下步骤执行。

### B1. 校验调仓输入

必须确认以下信息：

- 目标股票代码或名称
- 目标仓位百分比
- 本次当前持仓
- 目标股票当前价格，或可从本次持仓中推导的价格
- 交易单位，例如 A 股默认 100 股，基金份额默认按用户或平台口径

如果缺少目标股票、目标仓位或当前持仓，停止并只输出缺失字段清单。

如果用户没有说明资金假设，只问一个问题：

```text
这次调仓是允许外部现金流入/流出，还是要求组合内不增加资金？
```

当前脚本的默认调仓 helper 使用外部现金流入/流出口径。

### B2. 完成通用前置流程

先完成：

1. 提取本次持仓
2. 写入 `tmp/latest_query.json`
3. 查询基金成分股
4. 运行 `compute_stock_exposure()`

### B3. 判断目标股票来源

根据穿透结果判断目标股票敞口来自哪里：

- 只来自直接股票持仓
- 同时来自直接股票和基金成分股
- 只来自基金成分股
- 当前完全没有该股票敞口

同时计算：

- 目标股票当前股票维度市值
- 目标股票当前股票维度占比
- 目标股票直接持股市值
- 每只包含目标股票的基金中，该股票的成分股权重

### B4. 计算直接股票路径

如果可以直接买入或卖出目标股票，调用：

```python
from portfolio_math import compute_direct_stock_rebalance

direct_plan = compute_direct_stock_rebalance(
    exposure,
    target_symbol="300750",
    target_weight=0.15,
    current_price=198.0,
    lot_size=100,
    current_direct_market_value=direct_market_value
)
```

注意：

- 买入时，helper 默认外部现金流入。
- 卖出时，helper 默认资金流出。
- 如果目标股票敞口也来自基金，必须传入 `current_direct_market_value`，避免把基金穿透敞口当作可卖股票。

### B5. 计算基金路径

如果用户持有的基金中包含目标股票，逐只基金调用：

```python
from portfolio_math import compute_instrument_rebalance

fund_plan = compute_instrument_rebalance(
    exposure,
    target_symbol="300750",
    target_weight=0.15,
    instrument_symbol="159836",
    instrument_name="创业板300ETF天弘",
    instrument_target_weight=0.1325,
    current_price=1.072,
    lot_size=100,
    current_instrument_market_value=128640
)
```

基金路径只作为一种机械计算路径。不要评价哪条路径更好。除非用户要求只给一种操作，否则可以列出直接股票路径和基金路径。

### B6. 计算调整后结果

对每条可执行路径，输出：

- 买入或卖出标的
- 买入或卖出金额
- 买入或卖出股数/份额
- 交易单位取整规则
- 目标股票调整后仓位
- 如果数据足够，给出调整后的股票维度持仓表

### B7. 最终输出格式

最终回答只输出具体操作，不输出分析。

推荐格式：

```text
目标：300750 宁德时代，从 xx.xx% 调整到 15.00%

操作路径 1：直接股票
买入/卖出：买入
标的：300750 宁德时代
数量：x 股
金额：xxx.xx
取整：按 100 股取整
调整后目标仓位：xx.xx%

操作路径 2：基金
买入/卖出：买入
标的：159836 创业板300ETF天弘
数量：x 份
金额：xxx.xx
取整：按 100 份取整
调整后目标仓位：xx.xx%
```

不要输出：

- “建议选择路径 1”
- “更看好某股票”
- “风险较高/较低”
- “可以考虑”
- 行情、行业、估值、前景判断

## 输出硬性规则

最终回答必须只属于以下两类之一：

- 持仓分析：持仓数据表、总市值、占比、未知敞口、数据来源日期。
- 调仓计算：买入/卖出标的、金额、数量/份额、取整规则、调整后仓位。

必须保留的最小信息：

- 基金成分股来源日期
- 未知、缺失、无法穿透的敞口
- 无法计算时的缺失字段清单

禁止输出：

- 投资建议
- 买卖观点
- 行情判断
- 风险机会分析
- 行业分析
- 个股评价
- 与用户目标无关的教程或背景说明
- 公式推导，除非用户明确要求展示计算过程

完整数据结构示例见 `references/schemas.md`。完整计算示例见 `references/examples.md`。数据源规则见 `references/data-source-policy.md`。
