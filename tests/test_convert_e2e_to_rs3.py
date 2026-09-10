import json
import pathlib
import tempfile
import unittest
import xml.etree.ElementTree as ET

from src.convert_e2e_to_rs3 import (
    _validate_scheme_provenance,
    convert_results,
    safe_doc_filename,
    strip_tree_fence,
)
from src.schemes import load_scheme


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


class ConversionTests(unittest.TestCase):
    def test_accepts_current_and_previous_versions_and_rejects_unknown_version(self):
        scheme = load_scheme(ROOT / "configs" / "schemes" / "pcc.yaml")
        _validate_scheme_provenance(
            {"record_version": 1, "scheme": scheme.metadata()}, scheme
        )
        _validate_scheme_provenance(
            {"record_version": 2, "scheme": scheme.metadata()}, scheme
        )
        with self.assertRaisesRegex(ValueError, "record version"):
            _validate_scheme_provenance(
                {"record_version": 3, "scheme": scheme.metadata()}, scheme
            )
        wrong_metadata = scheme.metadata()
        wrong_metadata["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "sha256"):
            _validate_scheme_provenance(
                {"record_version": 1, "scheme": wrong_metadata}, scheme
            )

    def test_converts_successes_and_reports_skips_failures_and_collisions(self):
        scheme = load_scheme(ROOT / "configs" / "schemes" / "pcc.yaml")

        def success(doc_id, raw_tree, edus):
            return {
                "record_version": 1,
                "doc_id": doc_id,
                "status": "ok",
                "raw_tree": raw_tree,
                "scheme": scheme.metadata(),
                "edus": [
                    {"index": str(index), "text": text}
                    for index, text in enumerate(edus, start=1)
                ],
            }

        records = [
            success("doc-1", "(NN-joint (text 1) (text 2))", ["First.", "Second."]),
            success(
                "doc-2",
                "```text\n(NS-elaboration (text 1) (text 2))\n```",
                ["Main & premise.", "Detail <qualified>."],
            ),
            {"doc_id": "api-error", "status": "error", "raw_tree": None},
            success("bad-tree", "(not closed", ["Bad."]),
            success("same/id", "(text 1)", ["One."]),
            success("same id", "(text 1)", ["Two."]),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            input_path = root / "results.jsonl"
            input_path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            output_dir = root / "rs3"

            summary = convert_results(input_path, output_dir, scheme)

            report_records = [
                json.loads(line)
                for line in (output_dir / "conversion_report.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            generated = list(output_dir.glob("*.rs3"))
            generated_contents = [path.read_text(encoding="utf-8") for path in generated]
            doc1_root = ET.parse(output_dir / "doc-1.rs3").getroot()
            doc1_texts = [
                element.text for element in doc1_root.findall("./body/segment")
            ]
            doc1_relations = {
                element.attrib["name"]
                for element in doc1_root.findall("./header/relations/rel")
            }
            doc2_root = ET.parse(output_dir / "doc-2.rs3").getroot()
            doc2_segments = doc2_root.findall("./body/segment")
            doc2_group = doc2_root.find("./body/group")

        self.assertEqual(summary.generated, 3)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.failed, 2)
        self.assertEqual(len(report_records), len(records))
        self.assertEqual(len(generated), 3)
        self.assertTrue(all("<rst>" in content for content in generated_contents))
        self.assertEqual(doc1_texts, ["First.", "Second."])
        self.assertEqual(doc1_relations, set(scheme.relations))
        doc1_segments = doc1_root.findall("./body/segment")
        doc1_group = doc1_root.find("./body/group")
        self.assertEqual(doc1_group.attrib, {"id": "3", "type": "multinuc"})
        self.assertEqual(
            [element.attrib for element in doc1_segments],
            [
                {"id": "1", "parent": "3", "relname": "joint"},
                {"id": "2", "parent": "3", "relname": "joint"},
            ],
        )
        self.assertEqual(
            [element.text for element in doc2_segments],
            ["Main & premise.", "Detail <qualified>."],
        )
        self.assertEqual(doc2_group.attrib, {"id": "3", "type": "span"})
        self.assertEqual(
            [element.attrib for element in doc2_segments],
            [
                {"id": "1", "parent": "3", "relname": "span"},
                {"id": "2", "parent": "1", "relname": "elaboration"},
            ],
        )
        self.assertEqual(
            [record["status"] for record in report_records],
            ["generated", "generated", "skipped", "failed", "generated", "failed"],
        )
        self.assertIn("collision", report_records[-1]["error"]["message"])


if __name__ == "__main__":
    unittest.main()
