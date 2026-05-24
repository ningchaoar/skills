import unittest

from eastmoney_interface_probe import assess_stability


def sample_result(disclosure_date="2025-12-31", first_symbol="300750"):
    return {
        "fund_code": "159836",
        "disclosure_date": disclosure_date,
        "components": [
            {
                "symbol": first_symbol,
                "name": "宁德时代",
                "market": "CN",
                "weight": 0.1325,
                "raw_weight_percent": 13.25,
                "quarter": disclosure_date,
                "shares_10k": 5.25,
                "market_value_10k": 1927.01,
            },
            {
                "symbol": "300059",
                "name": "东方财富",
                "market": "CN",
                "weight": 0.052,
                "raw_weight_percent": 5.2,
                "quarter": disclosure_date,
                "shares_10k": 20.0,
                "market_value_10k": 800.0,
            },
        ],
    }


class EastmoneyInterfaceProbeTests(unittest.TestCase):
    def test_assess_stability_passes_matching_repeated_results(self):
        report = assess_stability([sample_result(), sample_result()], min_components=2, compare_top_n=2)

        self.assertTrue(report["stable"])
        self.assertEqual(report["reason"], "ok")
        self.assertEqual(report["component_count"], 2)
        self.assertEqual(report["disclosure_date"], "2025-12-31")

    def test_assess_stability_fails_when_disclosure_date_changes(self):
        report = assess_stability(
            [sample_result("2025-12-31"), sample_result("2025-09-30")],
            min_components=2,
            compare_top_n=2,
        )

        self.assertFalse(report["stable"])
        self.assertIn("disclosure date changed", report["reason"])

    def test_assess_stability_fails_when_top_symbols_change(self):
        report = assess_stability(
            [sample_result(first_symbol="300750"), sample_result(first_symbol="300014")],
            min_components=2,
            compare_top_n=2,
        )

        self.assertFalse(report["stable"])
        self.assertIn("top components changed", report["reason"])

    def test_assess_stability_fails_when_too_few_components(self):
        result = sample_result()
        result["components"] = result["components"][:1]

        report = assess_stability([result], min_components=2, compare_top_n=2)

        self.assertFalse(report["stable"])
        self.assertIn("too few components", report["reason"])


if __name__ == "__main__":
    unittest.main()
