import unittest

from exposure_report import compute_exposure_from_query, format_exposure_markdown


class ExposureReportTests(unittest.TestCase):
    def test_compute_exposure_from_query_uses_current_positions_and_components(self):
        query = {
            "current_positions": [
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
            ],
            "fund_components": {
                "159836": {
                    "source": "fixture",
                    "disclosure_date": "2026-03-31",
                    "components": [
                        {"symbol": "300750", "name": "宁德时代", "weight": 0.7},
                        {"symbol": "300059", "name": "东方财富", "weight": 0.2},
                        {"symbol": "300014", "name": "亿纬锂能", "weight": 0.1},
                    ],
                }
            },
        }

        exposure = compute_exposure_from_query(query)
        rows = {item["symbol"]: item for item in exposure["exposures"]}

        self.assertEqual(exposure["total_market_value"], 1000000.0)
        self.assertEqual(rows["300750"]["market_value"], 850000.0)
        self.assertEqual(rows["300750"]["weight"], 0.85)
        self.assertEqual(rows["300750"]["market"], "CN")

    def test_format_exposure_markdown_separates_unknown_fund_exposure(self):
        exposure = {
            "total_market_value": 1000000.0,
            "exposures": [
                {
                    "symbol": "300750",
                    "name": "宁德时代",
                    "market_value": 850000.0,
                    "weight": 0.85,
                    "sources": [
                        {
                            "type": "fund_component",
                            "fund_symbol": "159836",
                            "fund_name": "创业板300ETF天弘",
                            "market": "CN",
                            "component_weight": 0.7,
                            "source": "fixture",
                            "disclosure_date": "2026-03-31",
                        },
                        {
                            "type": "direct_stock",
                            "symbol": "300750",
                            "name": "宁德时代",
                            "market": "CN",
                            "market_value": 500000.0,
                        },
                    ],
                },
                {
                    "symbol": "UNKNOWN_FUND_EXPOSURE",
                    "name": "Unknown fund exposure",
                    "market_value": 150000.0,
                    "weight": 0.15,
                    "sources": [
                        {
                            "type": "unknown_fund",
                            "fund_symbol": "159941",
                            "fund_name": "纳指ETF嘉实",
                            "market_value": 150000.0,
                        }
                    ],
                },
            ],
        }

        markdown = format_exposure_markdown(exposure)

        self.assertIn("| 300750 | 宁德时代 | CN | 850000.00 | 85.00% | 直接持股 + 基金穿透 | 2026-03-31 |", markdown)
        self.assertIn("未知/未映射敞口", markdown)
        self.assertIn("| UNKNOWN_FUND_EXPOSURE | 150000.00 | 15.00% | 未取得 159941 的基金成分股 |", markdown)


if __name__ == "__main__":
    unittest.main()
