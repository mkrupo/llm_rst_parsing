import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from src.normalize_rs3 import (
    RS3SchemaError,
    normalize_rs3,
    parse_rs3,
    rs3_bytes,
    main,
    write_normalized_rs3,
)


RST_RELATIONS = "".join(
    f'<rel name="{name}" type="rst"/>'
    for name in ("background", "evidence", "evaluation", "reason")
)
RELATIONS = RST_RELATIONS + '<rel name="joint" type="multinuc"/>'


def rs3(body, relations=RELATIONS):
    return io.StringIO(
        f"<rst><header><relations>{relations}</relations></header>"
        f"<body>{body}</body></rst>"
    )


class SatelliteNormalizationTests(unittest.TestCase):
    def test_right_satellites_attach_nearest_first(self):
        document = normalize_rs3(
            rs3(
                '<segment id="1" parent="9" relname="span">E1</segment>'
                '<segment id="2" parent="1" relname="background">E2</segment>'
                '<segment id="3" parent="1" relname="evidence">E3</segment>'
                '<segment id="4" parent="1" relname="evaluation">E4</segment>'
                '<group id="9" type="span"/>'
            )
        )

        self.assertEqual(document.nodes["2"].parent, "1")
        self.assertEqual(document.nodes["3"].parent, "10")
        self.assertEqual(document.nodes["4"].parent, "11")
        self.assertEqual(document.nodes["1"].parent, "10")
        self.assertEqual(document.nodes["10"].parent, "11")
        self.assertEqual(document.nodes["11"].parent, "9")

    def test_left_satellites_attach_nearest_first(self):
        document = normalize_rs3(
            rs3(
                '<segment id="1" parent="4" relname="background">E1</segment>'
                '<segment id="2" parent="4" relname="evidence">E2</segment>'
                '<segment id="3" parent="4" relname="evaluation">E3</segment>'
                '<segment id="4" parent="9" relname="span">E4</segment>'
                '<group id="9" type="span"/>'
            )
        )

        self.assertEqual(document.nodes["3"].parent, "4")
        self.assertEqual(document.nodes["2"].parent, "10")
        self.assertEqual(document.nodes["1"].parent, "11")
        self.assertEqual(document.nodes["4"].parent, "10")
        self.assertEqual(document.nodes["10"].parent, "11")
        self.assertEqual(document.nodes["11"].parent, "9")

    def test_multiple_satellites_around_multinuclear_nucleus(self):
        document = normalize_rs3(
            rs3(
                '<segment id="1" parent="9" relname="background">E1</segment>'
                '<segment id="2" parent="9" relname="joint">E2</segment>'
                '<segment id="3" parent="9" relname="joint">E3</segment>'
                '<segment id="4" parent="9" relname="evidence">E4</segment>'
                '<segment id="5" parent="9" relname="evaluation">E5</segment>'
                '<group id="9" type="multinuc"/>'
            )
        )

        self.assertEqual(document.nodes["1"].parent, "9")
        self.assertEqual(document.nodes["4"].parent, "10")
        self.assertEqual(document.nodes["5"].parent, "11")
        self.assertEqual(document.nodes["9"].parent, "10")
        self.assertEqual(document.nodes["10"].parent, "11")
        self.assertIsNone(document.nodes["11"].parent)

    def test_normalization_is_idempotent_and_preserves_source_information(self):
        source = rs3(
            '<segment id="10" parent="90" relname="span"> Keep  (this). </segment>'
            '<segment id="30" parent="10" relname="evidence">E2</segment>'
            '<segment id="50" parent="10" relname="evaluation">E3</segment>'
            '<group id="90" type="span"/>'
        )
        first_document = normalize_rs3(source)
        first = rs3_bytes(first_document)
        second = rs3_bytes(normalize_rs3(io.BytesIO(first)))

        self.assertEqual(first, second)
        reparsed = parse_rs3(io.BytesIO(first))
        self.assertEqual(reparsed.nodes["10"].text, " Keep  (this). ")
        self.assertEqual(reparsed.nodes["30"].relation, "evidence")
        self.assertEqual(reparsed.nodes["50"].relation, "evaluation")
        self.assertEqual(
            set(reparsed.nodes) - {"10", "30", "50", "90"}, {"91"}
        )

    def test_strict_mode_rejects_relation_schema_mismatch(self):
        source = rs3(
            '<segment id="1" parent="9" relname="span">E1</segment>'
            '<segment id="2" parent="1" relname="joint">E2</segment>'
            '<group id="9" type="span"/>'
        )
        with self.assertRaises(RS3SchemaError):
            normalize_rs3(source)


class FileSafetyTests(unittest.TestCase):
    def test_writer_refuses_existing_output_and_input_output_identity(self):
        payload = (
            "<rst><header><relations/></header><body>"
            '<segment id="1" parent="2" relname="span">E1</segment>'
            '<group id="2" type="span"/>'
            "</body></rst>"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.rs3"
            output = Path(temp_dir) / "output.rs3"
            source.write_text(payload, encoding="utf-8")
            output.write_text("keep", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                write_normalized_rs3(source, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep")
            with self.assertRaises(FileExistsError):
                write_normalized_rs3(source, source, overwrite=True)

    def test_directory_cli_validates_entire_batch_before_writing(self):
        valid = (
            "<rst><header><relations/></header><body>"
            '<segment id="1" parent="2" relname="span">E1</segment>'
            '<group id="2" type="span"/>'
            "</body></rst>"
        )
        invalid = "<rst><header/><body><segment id=\"1\">E1</segment></body></rst>"
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            output_dir = Path(temp_dir) / "output"
            input_dir.mkdir()
            (input_dir / "a.rs3").write_text(valid, encoding="utf-8")
            (input_dir / "b.rs3").write_text(invalid, encoding="utf-8")

            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(input_dir), str(output_dir)])
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
