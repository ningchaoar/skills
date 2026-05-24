import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from fund_components import main, parse_eastmoney_holdings, update_latest_query_with_fund_components
from query_state import read_latest_query, write_latest_query


class FundComponentsTests(unittest.TestCase):
    def test_parse_eastmoney_holdings_uses_latest_quarter(self):
        html = """
        <table>
          <tr><th>序号</th><th>股票代码</th><th>股票名称</th><th>占净值比例</th><th>持股数</th><th>持仓市值</th><th>季度</th></tr>
          <tr><td>1</td><td>300750</td><td>宁德时代</td><td>8.20%</td><td>20.00</td><td>3900.00</td><td>2024年4季度</td></tr>
          <tr><td>2</td><td>300059</td><td>东方财富</td><td>5.10%</td><td>100.00</td><td>1300.00</td><td>2024年4季度</td></tr>
          <tr><td>1</td><td>300014</td><td>亿纬锂能</td><td>4.50%</td><td>30.00</td><td>1000.00</td><td>2024年3季度</td></tr>
        </table>
        """

        result = parse_eastmoney_holdings(html, fund_code="159836", source_url="https://example.test")

        self.assertEqual(result["source"], "东方财富-天天基金")
        self.assertEqual(result["source_url"], "https://example.test")
        self.assertEqual(result["disclosure_date"], "2024年4季度")
        self.assertEqual(
            result["components"],
            [
                {
                    "symbol": "300750",
                    "name": "宁德时代",
                    "market": "CN",
                    "weight": 0.082,
                    "raw_weight_percent": 8.2,
                    "quarter": "2024年4季度",
                    "shares_10k": 20.0,
                    "market_value_10k": 3900.0,
                },
                {
                    "symbol": "300059",
                    "name": "东方财富",
                    "market": "CN",
                    "weight": 0.051,
                    "raw_weight_percent": 5.1,
                    "quarter": "2024年4季度",
                    "shares_10k": 100.0,
                    "market_value_10k": 1300.0,
                },
            ],
        )

    def test_parse_eastmoney_real_page_shape_with_news_column_and_header_date(self):
        html = """
        var apidata={ content:"<div class='box'><h4 class='t'><label>创业板300ETF天弘&nbsp;&nbsp;2025年4季度股票投资明细</label><label>截止至：<font>2025-12-31</font></label></h4>
        <table><thead><tr><th>序号</th><th>股票代码</th><th>股票名称</th><th>相关资讯</th><th>占净值<br />比例</th><th>持股数<br />（万股）</th><th>持仓市值<br />（万元）</th></tr></thead>
        <tbody><tr><td>1</td><td><a>300750</a></td><td><a>宁德时代</a></td><td><a>股吧</a><a>行情</a></td><td>13.25%</td><td>5.25</td><td>1050.00</td></tr></tbody></table></div>"};
        """

        result = parse_eastmoney_holdings(html, fund_code="159836", source_url="https://example.test")

        self.assertEqual(result["disclosure_date"], "2025-12-31")
        self.assertEqual(result["components"][0]["symbol"], "300750")
        self.assertEqual(result["components"][0]["name"], "宁德时代")
        self.assertEqual(result["components"][0]["market"], "CN")
        self.assertEqual(result["components"][0]["weight"], 0.1325)
        self.assertEqual(result["components"][0]["quarter"], "2025-12-31")
        self.assertEqual(result["components"][0]["shares_10k"], 5.25)
        self.assertEqual(result["components"][0]["market_value_10k"], 1050.0)

    def test_parse_eastmoney_qdii_page_with_hk_and_us_symbols(self):
        html = """
        var apidata={ content:"<div class='box'><h4 class='t'><label>中概互联网ETF易方达&nbsp;&nbsp;2025年4季度股票投资明细</label><label>截止至：<font>2025-12-31</font></label></h4>
        <table><thead><tr><th>序号</th><th>股票代码</th><th>股票名称</th><th>相关资讯</th><th>占净值比例</th><th>持股数</th><th>持仓市值</th></tr></thead>
        <tbody>
        <tr><td>1</td><td><a>00700</a></td><td><a>腾讯控股</a></td><td><a>股吧</a><a>行情</a></td><td>31.02%</td><td>2,285.64</td><td>1,236,597.02</td></tr>
        <tr><td>2</td><td><a>09988</a></td><td><a>阿里巴巴-W</a></td><td><a>股吧</a><a>行情</a></td><td>25.90%</td><td>8,004.67</td><td>1,032,440.76</td></tr>
        <tr><td>3</td><td><a>PDD</a></td><td><a>拼多多</a></td><td><a>股吧</a><a>行情</a></td><td>7.01%</td><td>350.40</td><td>279,268.39</td></tr>
        </tbody></table></div>"};
        """

        result = parse_eastmoney_holdings(html, fund_code="513050", source_url="https://example.test")

        self.assertEqual(result["disclosure_date"], "2025-12-31")
        self.assertEqual(
            result["components"],
            [
                {
                    "symbol": "00700",
                    "name": "腾讯控股",
                    "market": "HK",
                    "weight": 0.3102,
                    "raw_weight_percent": 31.02,
                    "quarter": "2025-12-31",
                    "shares_10k": 2285.64,
                    "market_value_10k": 1236597.02,
                },
                {
                    "symbol": "09988",
                    "name": "阿里巴巴-W",
                    "market": "HK",
                    "weight": 0.259,
                    "raw_weight_percent": 25.9,
                    "quarter": "2025-12-31",
                    "shares_10k": 8004.67,
                    "market_value_10k": 1032440.76,
                },
                {
                    "symbol": "PDD",
                    "name": "拼多多",
                    "market": "US",
                    "weight": 0.0701,
                    "raw_weight_percent": 7.01,
                    "quarter": "2025-12-31",
                    "shares_10k": 350.4,
                    "market_value_10k": 279268.39,
                },
            ],
        )

    def test_update_latest_query_writes_components_back_to_same_file(self):
        query_file = Path(__file__).parent / ".tmp-latest-query.json"
        self.addCleanup(lambda: query_file.unlink() if query_file.exists() else None)
        write_latest_query(
            {
                "current_positions": [
                    {
                        "instrument_type": "fund",
                        "symbol": "159836",
                        "name": "创业板300ETF天弘",
                        "market_value": 100000,
                    }
                ]
            },
            query_file,
        )

        with patch(
            "fund_components.fetch_fund_components",
            return_value={
                "159836": {
                    "source": "fixture",
                    "disclosure_date": "2024年4季度",
                    "components": [{"symbol": "300750", "name": "宁德时代", "weight": 0.08}],
                }
            },
        ):
            updated = update_latest_query_with_fund_components(query_file, year="2024")

        self.assertEqual(updated, read_latest_query(query_file))
        self.assertIn("fund_components", updated)
        self.assertEqual(updated["fund_components"]["159836"]["components"][0]["symbol"], "300750")
        self.assertEqual(updated["fund_component_query"]["provider"], "eastmoney_tiantian_fund")
        self.assertEqual(updated["fund_component_query"]["year"], "2024")

    def test_cli_with_fund_codes_writes_latest_query_once(self):
        query_file = Path(__file__).parent / ".tmp-fund-components-cli.json"
        self.addCleanup(lambda: query_file.unlink() if query_file.exists() else None)

        with (
            patch(
                "fund_components.fetch_fund_components",
                return_value={
                    "159836": {
                        "source": "fixture",
                        "disclosure_date": "2024年4季度",
                        "components": [{"symbol": "300750", "name": "宁德时代", "weight": 0.08}],
                    }
                },
            ),
            patch("fund_components.write_latest_query", wraps=write_latest_query) as write_mock,
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = main(["--fund-codes", "159836", "--year", "2024", "--query-file", str(query_file)])

        self.assertEqual(result, 0)
        self.assertEqual(write_mock.call_count, 1)
        self.assertEqual(stdout.getvalue().strip(), str(query_file))
        self.assertEqual(read_latest_query(query_file)["fund_components"]["159836"]["components"][0]["symbol"], "300750")


if __name__ == "__main__":
    unittest.main()
