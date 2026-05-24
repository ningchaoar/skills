import unittest
from decimal import Decimal

from script_utils import decimal_to_float, decimal_value, infer_market, merged_market


class ScriptUtilsTests(unittest.TestCase):
    def test_infer_market_handles_supported_symbol_shapes(self):
        self.assertEqual(infer_market("300750"), "CN")
        self.assertEqual(infer_market("00700"), "HK")
        self.assertEqual(infer_market("PDD"), "US")
        self.assertEqual(infer_market("BRK.B"), "US")
        self.assertIsNone(infer_market("1234"))

    def test_decimal_value_rejects_invalid_numbers(self):
        self.assertEqual(decimal_value("1.25", "value"), Decimal("1.25"))
        with self.assertRaisesRegex(ValueError, "value must be finite"):
            decimal_value("NaN", "value")
        with self.assertRaisesRegex(ValueError, "value must be numeric"):
            decimal_value("not-a-number", "value")

    def test_decimal_to_float_and_merged_market(self):
        self.assertEqual(decimal_to_float(Decimal("1.25")), 1.25)
        self.assertEqual(
            merged_market([{"market": "US"}, {"market": "HK"}, {"market": "US"}]),
            "HK/US",
        )
        self.assertIsNone(merged_market([{"market": ""}, {}]))


if __name__ == "__main__":
    unittest.main()
