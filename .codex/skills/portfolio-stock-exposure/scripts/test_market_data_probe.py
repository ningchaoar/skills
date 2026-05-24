import unittest

from market_data_probe import probe_market_data


class MarketDataProbeTests(unittest.TestCase):
    def test_probe_market_data_collects_quotes_and_fx(self):
        def fake_quote(symbol, market):
            return {
                "symbol": symbol,
                "market": market,
                "currency": {"CN": "CNY", "HK": "HKD", "US": "USD"}[market],
                "current_price": 1.23,
            }

        def fake_fx(currency):
            return {
                "currency": currency,
                "target_currency": "CNY",
                "fx_rate_to_cny": 7.0 if currency == "USD" else 0.9,
                "fx_date": "2026-05-22",
            }

        report = probe_market_data(
            quote_specs=["CN:300750", "HK:00700", "US:PDD"],
            currencies=["USD", "HKD"],
            quote_fetcher=fake_quote,
            fx_fetcher=fake_fx,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(len(report["quotes"]), 3)
        self.assertEqual(len(report["fx_rates"]), 2)
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
