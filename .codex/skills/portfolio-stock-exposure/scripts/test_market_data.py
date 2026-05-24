import unittest

from market_data import (
    infer_market,
    market_currency,
    parse_eastmoney_quote,
    parse_frankfurter_rate,
    resolve_eastmoney_secid,
)


class MarketDataTests(unittest.TestCase):
    def test_infer_market_from_symbol_shape(self):
        self.assertEqual(infer_market("300750"), "CN")
        self.assertEqual(infer_market("00700"), "HK")
        self.assertEqual(infer_market("PDD"), "US")
        self.assertEqual(infer_market("BRK.B"), "US")
        self.assertIsNone(infer_market("1234"))

    def test_resolve_eastmoney_secid(self):
        self.assertEqual(resolve_eastmoney_secid("300750", "CN"), "0.300750")
        self.assertEqual(resolve_eastmoney_secid("600000", "CN"), "1.600000")
        self.assertEqual(resolve_eastmoney_secid("00700", "HK"), "116.00700")
        self.assertEqual(resolve_eastmoney_secid("PDD", "US"), "105.PDD")

    def test_market_currency(self):
        self.assertEqual(market_currency("CN"), "CNY")
        self.assertEqual(market_currency("HK"), "HKD")
        self.assertEqual(market_currency("US"), "USD")

    def test_parse_eastmoney_quote_uses_f59_price_scale(self):
        quote = parse_eastmoney_quote(
            {
                "rc": 0,
                "data": {
                    "f43": 441400,
                    "f57": "00700",
                    "f58": "腾讯控股",
                    "f59": 3,
                    "f107": 116,
                    "f152": 2,
                },
            },
            requested_symbol="00700",
            requested_market="HK",
            source_url="https://example.test/quote",
        )

        self.assertEqual(quote["symbol"], "00700")
        self.assertEqual(quote["name"], "腾讯控股")
        self.assertEqual(quote["market"], "HK")
        self.assertEqual(quote["currency"], "HKD")
        self.assertEqual(quote["current_price"], 441.4)
        self.assertEqual(quote["quote_source"], "东方财富")
        self.assertEqual(quote["quote_source_url"], "https://example.test/quote")

    def test_parse_frankfurter_rate_to_cny(self):
        rate = parse_frankfurter_rate(
            {
                "amount": 1.0,
                "base": "USD",
                "date": "2026-05-22",
                "rates": {"CNY": 6.7953},
            },
            "USD",
            source_url="https://example.test/fx",
        )

        self.assertEqual(rate["currency"], "USD")
        self.assertEqual(rate["target_currency"], "CNY")
        self.assertEqual(rate["fx_rate_to_cny"], 6.7953)
        self.assertEqual(rate["fx_date"], "2026-05-22")
        self.assertEqual(rate["fx_source"], "Frankfurter")


if __name__ == "__main__":
    unittest.main()
