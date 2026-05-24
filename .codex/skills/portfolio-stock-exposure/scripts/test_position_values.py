import unittest
from pathlib import Path

from position_values import enrich_position_values, update_latest_query_with_position_values
from query_state import read_latest_query, write_latest_query


def fake_quote(symbol, market):
    quotes = {
        ("00700", "HK"): {
            "symbol": "00700",
            "name": "腾讯控股",
            "market": "HK",
            "currency": "HKD",
            "current_price": 441.4,
            "quote_source": "fixture",
            "quote_source_url": "https://example.test/quote/00700",
        },
        ("PDD", "US"): {
            "symbol": "PDD",
            "name": "拼多多",
            "market": "US",
            "currency": "USD",
            "current_price": 94.52,
            "quote_source": "fixture",
            "quote_source_url": "https://example.test/quote/PDD",
        },
    }
    return quotes[(symbol, market)]


def fake_fx(currency):
    rates = {
        "HKD": {
            "currency": "HKD",
            "target_currency": "CNY",
            "fx_rate_to_cny": 0.92,
            "fx_date": "2026-05-22",
            "fx_source": "fixture",
        },
        "USD": {
            "currency": "USD",
            "target_currency": "CNY",
            "fx_rate_to_cny": 7.2,
            "fx_date": "2026-05-22",
            "fx_source": "fixture",
        },
    }
    return rates[currency]


class PositionValuesTests(unittest.TestCase):
    def test_enrich_direct_hk_and_us_stock_values(self):
        query = {
            "current_positions": [
                {"instrument_type": "stock", "name": "腾讯控股", "symbol": "00700", "quantity": 100},
                {"instrument_type": "stock", "name": "拼多多", "symbol": "PDD", "quantity": 2},
            ]
        }

        enriched = enrich_position_values(query, quote_fetcher=fake_quote, fx_fetcher=fake_fx)
        positions = enriched["current_positions"]

        self.assertEqual(positions[0]["market"], "HK")
        self.assertEqual(positions[0]["currency"], "HKD")
        self.assertEqual(positions[0]["current_price"], 441.4)
        self.assertEqual(positions[0]["local_market_value"], 44140.0)
        self.assertEqual(positions[0]["fx_rate_to_cny"], 0.92)
        self.assertEqual(positions[0]["market_value"], 40608.8)

        self.assertEqual(positions[1]["market"], "US")
        self.assertEqual(positions[1]["currency"], "USD")
        self.assertEqual(positions[1]["local_market_value"], 189.04)
        self.assertEqual(positions[1]["fx_rate_to_cny"], 7.2)
        self.assertAlmostEqual(positions[1]["market_value"], 1361.088)

    def test_existing_market_value_is_not_overwritten_or_queried(self):
        def fail_quote(symbol, market):
            raise AssertionError("quote_fetcher should not be called")

        query = {
            "current_positions": [
                {
                    "instrument_type": "stock",
                    "name": "腾讯控股",
                    "symbol": "00700",
                    "market": "HK",
                    "market_value": 12345.67,
                }
            ]
        }

        enriched = enrich_position_values(query, quote_fetcher=fail_quote, fx_fetcher=fake_fx)

        self.assertEqual(enriched["current_positions"][0]["market_value"], 12345.67)
        self.assertEqual(enriched["current_positions"][0]["market"], "HK")

    def test_current_price_and_currency_only_fetches_fx(self):
        def fail_quote(symbol, market):
            raise AssertionError("quote_fetcher should not be called")

        query = {
            "current_positions": [
                {
                    "instrument_type": "stock",
                    "name": "拼多多",
                    "symbol": "PDD",
                    "quantity": 3,
                    "current_price": 94.52,
                    "currency": "USD",
                }
            ]
        }

        enriched = enrich_position_values(query, quote_fetcher=fail_quote, fx_fetcher=fake_fx)

        position = enriched["current_positions"][0]
        self.assertEqual(position["market"], "US")
        self.assertEqual(position["local_market_value"], 283.56)
        self.assertEqual(position["market_value"], 2041.632)

    def test_missing_market_value_and_quantity_raises_clear_error(self):
        query = {
            "current_positions": [
                {
                    "instrument_type": "stock",
                    "name": "腾讯控股",
                    "symbol": "00700",
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "positions\\[0\\] must include market_value or quantity"):
            enrich_position_values(query, quote_fetcher=fake_quote, fx_fetcher=fake_fx)

    def test_update_latest_query_writes_back_to_same_file(self):
        query_file = Path(__file__).parent / ".tmp-position-values.json"
        self.addCleanup(lambda: query_file.unlink() if query_file.exists() else None)
        write_latest_query(
            {
                "current_positions": [
                    {"instrument_type": "stock", "name": "腾讯控股", "symbol": "00700", "quantity": 100}
                ]
            },
            query_file,
        )

        updated = update_latest_query_with_position_values(
            query_file,
            quote_fetcher=fake_quote,
            fx_fetcher=fake_fx,
        )

        self.assertEqual(updated, read_latest_query(query_file))
        self.assertEqual(updated["position_value_query"]["base_currency"], "CNY")
        self.assertEqual(updated["current_positions"][0]["market_value"], 40608.8)


if __name__ == "__main__":
    unittest.main()
