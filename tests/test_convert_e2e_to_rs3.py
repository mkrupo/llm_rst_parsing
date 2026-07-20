import json
import importlib.util
import pathlib
import tempfile
import unittest

from src.convert_e2e_to_rs3 import (
    convert_results,
    safe_doc_filename,
    strip_tree_fence,
)


ROOT = pathlib.Path(__file__).resolve().parent.parent


class TreeCleanupTests(unittest.TestCase):
    def test_keeps_plain_tree_and_strips_outer_whitespace(self):
        self.assertEqual(strip_tree_fence("  (text 1)\n"), "(text 1)")

    def test_strips_only_surrounding_markdown_fence(self):
        tree = "(NN-Joint (text First.) (text Second.))"
        self.assertEqual(strip_tree_fence(f"```\n{tree}\n```"), tree)
        self.assertEqual(strip_tree_fence(f"```text\n{tree}\n```"), tree)
        prose = f"Here is the tree:\n{tree}"
        self.assertEqual(strip_tree_fence(prose), prose)

    def test_extracts_final_tree_from_real_analysis_response(self):
        response = (ROOT / "tests" / "fixtures" / "model_output_with_analysis.txt").read_text(
            encoding="utf-8"
        )

        extracted = strip_tree_fence(response)

        self.assertTrue(extracted.startswith("(NN-List"))
        self.assertIn("(text 58)", extracted)
        self.assertNotIn("world-famous discourse analysis", extracted)

    def test_sanitizes_document_ids_without_allowing_paths(self):
        self.assertEqual(safe_doc_filename("gum/news 1"), "gum_news_1")
        self.assertEqual(safe_doc_filename("../../outside"), "outside")
        with self.assertRaisesRegex(ValueError, "filename"):
            safe_doc_filename(" ... ")


@unittest.skipUnless(
    importlib.util.find_spec("nltk") and importlib.util.find_spec("rstconverter"),
    "RS3 integration dependencies are not installed in this interpreter",
)
class ConversionTests(unittest.TestCase):
    def test_converts_successes_and_reports_skips_failures_and_collisions(self):
        records = [
            {
                "doc_id": "doc-1",
                "status": "ok",
                "raw_tree": "(NN-Joint (text First.) (text Second.))",
            },
            {
                "doc_id": "doc-2",
                "status": "ok",
                "raw_tree": "```text\n(NS-Elaboration (text Main.) (text Detail.))\n```",
            },
            {"doc_id": "api-error", "status": "error", "raw_tree": None},
            {"doc_id": "bad-tree", "status": "ok", "raw_tree": "(not closed"},
            {"doc_id": "same/id", "status": "ok", "raw_tree": "(text One.)"},
            {"doc_id": "same id", "status": "ok", "raw_tree": "(text Two.)"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            input_path = root / "results.jsonl"
            input_path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            output_dir = root / "rs3"

            summary = convert_results(input_path, output_dir)

            report_records = [
                json.loads(line)
                for line in (output_dir / "conversion_report.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            generated = list(output_dir.glob("*.rs3"))
            generated_contents = [path.read_text(encoding="utf-8") for path in generated]

        self.assertEqual(summary.generated, 3)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.failed, 2)
        self.assertEqual(len(report_records), len(records))
        self.assertEqual(len(generated), 3)
        self.assertTrue(all("<rst>" in content for content in generated_contents))
        self.assertEqual(
            [record["status"] for record in report_records],
            ["generated", "generated", "skipped", "failed", "generated", "failed"],
        )
        self.assertIn("collision", report_records[-1]["error"]["message"])


if __name__ == "__main__":
    unittest.main()
