import unittest

from src.metrics import native_validity, parsed_fields
from src.parse_outputs import safe_parse_json


class ParseOutputTests(unittest.TestCase):
    def test_safe_parse_json_rejects_non_objects(self):
        self.assertIsNone(safe_parse_json("[]"))
        self.assertIsNone(safe_parse_json('"native_label"'))

    def test_safe_parse_json_extracts_embedded_object(self):
        self.assertEqual(
            safe_parse_json('Answer:\n{"native_label": "cause"}\nDone.'),
            {"native_label": "cause"},
        )


class MetricsTests(unittest.TestCase):
    def test_native_validity_counts_missing_labels_as_invalid(self):
        records = [
            {"standard": "rst", "parsed": {"native_label": "cause"}},
            {"standard": "rst", "parsed": {}},
            {"standard": "rst", "parsed": None},
            {"standard": "rst", "parsed": {"native_label": "unknown"}},
        ]

        self.assertEqual(native_validity(records, {"rst": ["cause"]}), 0.25)

    def test_parsed_fields_ignores_malformed_parsed_values(self):
        self.assertEqual(parsed_fields({"parsed": []}), {})
        self.assertEqual(parsed_fields({"parsed": "not an object"}), {})


if __name__ == "__main__":
    unittest.main()
