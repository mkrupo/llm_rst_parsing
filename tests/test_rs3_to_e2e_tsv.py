import csv
import json
import pathlib
import tempfile
import unittest

from src.rs3_to_e2e_tsv import (
    export_rs3_to_tsv,
    load_source_documents,
    read_rs3_segments,
)
from src.run_e2e_icl import read_tsv_documents


RS3 = """\
<rst>
  <header><relations><rel name="reason" type="rst"/></relations></header>
  <body>
    <segment id="8" parent="10" relname="span">First &amp; central.</segment>
    <group id="10" type="span"/>
    <segment id="2" parent="8" relname="reason"> Leading satellite. </segment>
  </body>
</rst>
"""


class Rs3ToE2eTsvTests(unittest.TestCase):
    def test_reads_xml_body_order_and_preserves_exact_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = pathlib.Path(temp_dir) / "demo.rs3"
            source.write_text(RS3, encoding="utf-8")

            document = read_rs3_segments(source, source_path="demo.rs3")

        self.assertEqual(document.doc_id, "demo")
        self.assertEqual(
            [(segment.index, segment.source_id, segment.text) for segment in document.segments],
            [
                ("1", "8", "First & central."),
                ("2", "2", " Leading satellite. "),
            ],
        )
        self.assertEqual(len(document.source_sha256), 64)

    def test_exports_runner_compatible_tsv_and_source_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            source_dir = root / "gold"
            source_dir.mkdir()
            (source_dir / "b.rs3").write_text(RS3, encoding="utf-8")
            (source_dir / "a.rs3").write_text(
                RS3.replace("First &amp; central.", "A\tfield\nwith a newline."),
                encoding="utf-8",
            )
            output = root / "documents.tsv"

            summary = export_rs3_to_tsv(source_dir, output)
            documents = read_tsv_documents(output)
            manifest = [
                json.loads(line)
                for line in output.with_suffix(".tsv.manifest.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]

        self.assertEqual((summary.documents, summary.segments), (2, 4))
        self.assertEqual([document.doc_id for document in documents], ["a", "b"])
        self.assertEqual(documents[0].rows[0][1], "A\tfield\nwith a newline.")
        self.assertEqual(documents[1].rows[1][1], " Leading satellite. ")
        self.assertEqual(manifest[0]["source_path"], "a.rs3")
        self.assertEqual(manifest[0]["segments"][0]["source_id"], "8")
        self.assertEqual(manifest[0]["segment_count"], 2)

    def test_rejects_duplicate_document_ids_in_recursive_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            for directory in (root / "one", root / "two"):
                directory.mkdir()
                (directory / "demo.rs3").write_text(RS3, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate document ID"):
                load_source_documents(root, recursive=True)

    def test_rejects_nested_or_blank_segments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            nested = root / "nested.rs3"
            nested.write_text(
                "<rst><body><segment id='1'>bad<x/></segment></body></rst>",
                encoding="utf-8",
            )
            blank = root / "blank.rs3"
            blank.write_text(
                "<rst><body><segment id='1'>  </segment></body></rst>",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "nested XML"):
                read_rs3_segments(nested, source_path=nested.name)
            with self.assertRaisesRegex(ValueError, "blank text"):
                read_rs3_segments(blank, source_path=blank.name)

    def test_refuses_existing_output_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            source = root / "demo.rs3"
            source.write_text(RS3, encoding="utf-8")
            output = root / "documents.tsv"
            output.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "--overwrite"):
                export_rs3_to_tsv(source, output)

            export_rs3_to_tsv(source, output, overwrite=True)
            with output.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(rows[0]["text"], "First & central.")


if __name__ == "__main__":
    unittest.main()
