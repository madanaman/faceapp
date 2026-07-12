import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HttpHandlerContractTest(unittest.TestCase):
    def test_api_cors_methods_include_delete_for_remove_actions(self):
        source = (ROOT / "backend" / "http_handler.py").read_text()
        self.assertIn('"GET, POST, DELETE, OPTIONS"', source)


if __name__ == "__main__":
    unittest.main()
