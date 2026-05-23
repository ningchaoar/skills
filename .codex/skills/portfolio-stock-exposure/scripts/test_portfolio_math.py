import math
import unittest

from portfolio_math import (
    compute_direct_stock_rebalance,
    compute_instrument_rebalance,
    compute_stock_exposure,
    normalize_positions,
)


class PortfolioMathTests(unittest.TestCase):
    def assertClose(self, actual, expected, *, tol=1e-9):
        self.assertTrue(
            math.isclose(actual, expected, rel_tol=tol, abs_tol=tol),
            f"{actual!r} != {expected!r}",
        )

    def test_compute_stock_exposure_expands_fund_and_merges_direct_stock(self):
        positions = normalize_positions(
            [
                {
                    "instrument_type": "fund",
                    "name": "A基金",
                    "symbol": "FUND_A",
                    "market_value": 500000,
                },
                {
                    "instrument_type": "stock",
                    "name": "股票b",
                    "symbol": "STOCK_B",
                    "market_value": 500000,
                    "quantity": 10000,
                    "current_price": 50,
                },
            ]
        )
        components = {
            "FUND_A": {
                "source": "fixture",
                "disclosure_date": "2026-03-31",
                "components": [
                    {"symbol": "STOCK_A", "name": "股票a", "weight": 0.7},
                    {"symbol": "STOCK_B", "name": "股票b", "weight": 0.2},
                    {"symbol": "STOCK_C", "name": "股票c", "weight": 0.1},
                ],
            }
        }

        exposure = compute_stock_exposure(positions, components)

        self.assertClose(exposure["total_market_value"], 1000000)
        by_symbol = {item["symbol"]: item for item in exposure["exposures"]}
        self.assertClose(by_symbol["STOCK_A"]["market_value"], 350000)
        self.assertClose(by_symbol["STOCK_A"]["weight"], 0.35)
        self.assertClose(by_symbol["STOCK_B"]["market_value"], 600000)
        self.assertClose(by_symbol["STOCK_B"]["weight"], 0.60)
        self.assertClose(by_symbol["STOCK_C"]["market_value"], 50000)
        self.assertClose(by_symbol["STOCK_C"]["weight"], 0.05)

    def test_compute_stock_exposure_keeps_unknown_fund_bucket(self):
        positions = normalize_positions(
            [
                {
                    "instrument_type": "fund",
                    "name": "缺失持仓基金",
                    "symbol": "FUND_UNKNOWN",
                    "market_value": 100000,
                },
                {
                    "instrument_type": "stock",
                    "name": "股票a",
                    "symbol": "STOCK_A",
                    "market_value": 300000,
                },
            ]
        )

        exposure = compute_stock_exposure(positions, {})

        by_symbol = {item["symbol"]: item for item in exposure["exposures"]}
        self.assertClose(by_symbol["STOCK_A"]["weight"], 0.75)
        self.assertClose(by_symbol["UNKNOWN_FUND_EXPOSURE"]["market_value"], 100000)
        self.assertClose(by_symbol["UNKNOWN_FUND_EXPOSURE"]["weight"], 0.25)

    def test_compute_stock_exposure_rejects_component_weights_above_one(self):
        positions = normalize_positions(
            [
                {
                    "instrument_type": "fund",
                    "name": "A基金",
                    "symbol": "FUND_A",
                    "market_value": 100000,
                }
            ]
        )
        components = {
            "FUND_A": {
                "source": "fixture",
                "disclosure_date": "2026-03-31",
                "components": [
                    {"symbol": "STOCK_A", "name": "股票a", "weight": 70},
                ],
            }
        }

        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            compute_stock_exposure(positions, components)

    def test_direct_stock_rebalance_uses_new_total_value_for_buying(self):
        exposure = {
            "total_market_value": 1000000,
            "exposures": [
                {"symbol": "STOCK_A", "name": "股票a", "market_value": 350000, "weight": 0.35},
                {"symbol": "STOCK_B", "name": "股票b", "market_value": 600000, "weight": 0.60},
                {"symbol": "STOCK_C", "name": "股票c", "market_value": 50000, "weight": 0.05},
            ],
        }

        plan = compute_direct_stock_rebalance(
            exposure,
            target_symbol="STOCK_A",
            target_weight=0.40,
            current_price=10,
            lot_size=100,
        )

        self.assertEqual(plan["action"], "buy")
        self.assertClose(plan["trade_amount"], 83000)
        self.assertEqual(plan["shares"], 8300)
        self.assertClose(plan["final_total_market_value"], 1083000)
        self.assertClose(plan["final_target_market_value"], 433000)
        self.assertClose(plan["final_target_weight"], 433000 / 1083000)

    def test_direct_stock_rebalance_caps_sell_by_direct_market_value(self):
        exposure = {
            "total_market_value": 1000000,
            "exposures": [
                {"symbol": "STOCK_A", "name": "股票a", "market_value": 600000, "weight": 0.60},
                {"symbol": "STOCK_B", "name": "股票b", "market_value": 400000, "weight": 0.40},
            ],
        }

        plan = compute_direct_stock_rebalance(
            exposure,
            target_symbol="STOCK_A",
            target_weight=0.30,
            current_price=10,
            lot_size=100,
            current_direct_market_value=200000,
        )

        self.assertEqual(plan["action"], "sell")
        self.assertEqual(plan["shares"], 20000)
        self.assertClose(plan["trade_amount"], 200000)
        self.assertTrue(plan["capped_by_direct_holding"])
        self.assertClose(plan["final_total_market_value"], 800000)
        self.assertClose(plan["final_target_market_value"], 400000)
        self.assertClose(plan["final_target_weight"], 0.50)

    def test_instrument_rebalance_can_buy_fund_containing_target_stock(self):
        exposure = {
            "total_market_value": 1000000,
            "exposures": [
                {"symbol": "STOCK_A", "name": "股票a", "market_value": 350000, "weight": 0.35},
                {"symbol": "STOCK_B", "name": "股票b", "market_value": 600000, "weight": 0.60},
                {"symbol": "STOCK_C", "name": "股票c", "market_value": 50000, "weight": 0.05},
            ],
        }

        plan = compute_instrument_rebalance(
            exposure,
            target_symbol="STOCK_A",
            target_weight=0.40,
            instrument_symbol="FUND_A",
            instrument_name="A基金",
            instrument_target_weight=0.70,
            current_price=1,
            lot_size=100,
            current_instrument_market_value=500000,
        )

        self.assertEqual(plan["action"], "buy")
        self.assertEqual(plan["units"], 166600)
        self.assertClose(plan["trade_amount"], 166600)
        self.assertClose(plan["final_total_market_value"], 1166600)
        self.assertClose(plan["final_target_market_value"], 466620)
        self.assertClose(plan["final_target_weight"], 466620 / 1166600)


if __name__ == "__main__":
    unittest.main()
