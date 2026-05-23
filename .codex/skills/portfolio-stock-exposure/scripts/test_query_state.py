import json
import tempfile
import unittest
from pathlib import Path

from query_state import read_latest_query, write_latest_query


class QueryStateTests(unittest.TestCase):
    def make_temp_dir(self):
        base_dir = Path(__file__).parent / ".tmp-tests"
        base_dir.mkdir(exist_ok=True)
        self.addCleanup(lambda: base_dir.rmdir() if base_dir.exists() and not any(base_dir.iterdir()) else None)
        return tempfile.TemporaryDirectory(dir=base_dir)

    def test_write_latest_query_overwrites_single_file(self):
        with self.make_temp_dir() as temp_dir:
            query_file = Path(temp_dir) / "latest_query.json"

            first = write_latest_query({"fund_codes": ["159836"]}, query_file)
            second = write_latest_query({"fund_codes": ["515050"]}, query_file)

            self.assertEqual(first, second)
            self.assertEqual(read_latest_query(query_file), {"fund_codes": ["515050"]})
            self.assertEqual(json.loads(query_file.read_text(encoding="utf-8")), {"fund_codes": ["515050"]})


if __name__ == "__main__":
    unittest.main()
