# 数据源规则

获取基金成分股并做股票维度穿透时，遵守本规则。

## 优先来源

优先使用一手或官方来源：

- 基金公司官方产品页面
- 交易所 ETF 每日持仓或 PCF 文件
- 基金官方定期报告
- 只有在官方来源不可用时，才使用公认的数据服务商

必须记录 `source` 和 `disclosure_date`。如果页面没有显示日期，明确说明成分股日期未知。

## 脚本化查询

默认脚本：

```bash
python scripts/fund_components.py
```

脚本使用东方财富/天天基金公开网页端点查询基金股票持仓，并写回单一临时文件 `tmp/latest_query.json`：

```text
https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code=<fund_code>&topline=100&year=<year>&month=
```

这是可脚本化的公开网页端点，不等同于券商或数据商承诺 SLA 的正式 API。网络失败、反爬限制、字段变化或页面结构变化都可能导致查询失败。

脚本默认查询当前自然年，也可以通过 `--year` 指定年份。若当前年尚未披露可用持仓，重新指定最近可能有披露数据的年份；不要在没有数据的情况下猜测成分股。

解析规则：

- 以证券代码定位表格中的持仓行，不依赖固定列序；支持 A 股 6 位代码、港股 5 位代码和美股 ticker。
- 对解析出的成分股写入 `market`：A 股为 `CN`，港股为 `HK`，美股为 `US`。
- 以百分号字段解析成分股权重，写入 `weight` 和 `raw_weight_percent`。
- 同一年有多个披露期时，只保留解析结果中最新的 `quarter`/`disclosure_date`。
- 解析不到任何成分股时，调用方必须把基金保留为 `UNKNOWN_FUND_EXPOSURE`。

接口稳定性探测脚本：

```bash
python scripts/eastmoney_interface_probe.py --fund-codes 159836 515050 --year 2025 --attempts 3
```

该脚本会多次请求同一基金同一年份的东方财富/天天基金持仓页面，检查请求是否报错、解析出的成分股数量是否达到阈值、披露日期是否一致、前 N 个成分股代码是否一致。它是手动运行的在线探测，不应放入默认单元测试，因为网络波动或页面调整会导致结果变化。

如果当前环境已安装 AKShare，也可以参考 AKShare 的 `fund_portfolio_hold_em` 接口口径；该接口同样来源于天天基金网“基金档案-投资组合-基金持仓”，返回指定基金和年份的持仓数据。当前技能内置脚本不强依赖 AKShare，避免额外安装依赖。

## 直接股票行情和汇率

直接股票缺少人民币 `market_value` 时，运行：

```bash
python scripts/position_values.py
```

行情默认使用东方财富公开 quote 端点：

```text
https://push2.eastmoney.com/api/qt/stock/get?secid=<market>.<symbol>&fields=f43,f57,f58,f59,f107,f152
```

`secid` 规则：

- A 股：深市 `0.<symbol>`，沪市 `1.<symbol>`
- 港股：`116.<symbol>`，例如 `116.00700`
- 美股：`105.<ticker>`，例如 `105.PDD`

价格解析优先使用 `f59` 作为缩放位数，按 `f43 / 10^f59` 得到本币价格；如果响应缺少 `f59`，才回退到 `f152`。

汇率默认使用 Frankfurter 公开 API：

```text
https://api.frankfurter.app/latest?from=<currency>&to=CNY
```

该端点不需要 API key。脚本只支持 `CNY`、`HKD`、`USD` 到 `CNY` 的换算。东方财富 quote 和 Frankfurter 汇率都属于公开数据源，不承诺 SLA；网络失败、字段变化、限流或汇率服务异常时，不要猜测价格或汇率，要求用户补充人民币市值、本币价格或汇率。

行情和汇率稳定性探测脚本：

```bash
python scripts/market_data_probe.py --quotes CN:300750 HK:00700 US:PDD --currencies USD HKD
```

该脚本是手动在线探测，不应放入默认单元测试。

## 基金类型处理

ETF 通常可能有每日或接近日频的持仓数据。使用能找到的最新官方日期，不要默认它就是今天。若只通过东方财富/天天基金公开页面取得基金持仓，按页面返回的披露日期处理。

普通公募基金通常通过季报、半年报或年报披露持仓。使用最新公开披露持仓，并说明它可能滞后于基金当前真实组合。

如果基金包含债券、现金、存款、期货或其他非股票资产，这些部分必须单独保留。不要把非股票资产重新分配到可见股票上。

## 缺失数据

如果找不到某只基金的成分股，不要凭记忆或猜测估算权重。把该基金全部市值保留为：

```text
UNKNOWN_FUND_EXPOSURE
```

如果只能拿到前十大持仓等部分持仓，录入可见部分，并把剩余市值保留为：

```text
UNMAPPED_<fund_symbol>
```

## 默认范围限制

默认不覆盖：

- 海外 ETF
- 海外共同基金、全球共同基金的独立数据源查询
- 非 `CNY/HKD/USD` 货币之间的汇率换算
- 税费、交易成本、盘中实时性保证

如果用户要求扩展范围，先确认汇率换算口径和可接受的数据源，再开始计算。
