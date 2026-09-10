import pathlib
import tempfile
import unittest
import xml.etree.ElementTree as ET

from src.convert_e2e_to_rs3 import convert_results
from src.run_e2e_icl import CompletionResult, Document, run_experiment
from src.schemes import load_scheme


ROOT = pathlib.Path(__file__).resolve().parent.parent


class _SuccessfulClient:
    def complete(self, **kwargs):
        return CompletionResult(
            content="(NS-elaboration (text 1) (text 2))",
            response_id="fake-response",
            finish_reason="stop",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "total_tokens": 20,
            },
        )


class E2EPipelineTests(unittest.TestCase):
    def test_prediction_record_converts_to_source_faithful_rs3(self):
        scheme = load_scheme(ROOT / "configs" / "schemes" / "pcc.yaml")
        document = Document(
            doc_id="demo",
            header=("index", "text"),
            rows=(("1", "Main & claim."), ("2", "A supporting <detail>.")),
        )
        prompt = "Contract\n```tsv\n```\n"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            predictions = root / "predictions.jsonl"
            run_experiment(
                documents=[document],
                system_prompt="Return one tree.",
                icl_prompt=prompt,
                prompt_name=scheme.prompt,
                output_path=predictions,
                client=_SuccessfulClient(),
                model="fake-model",
                endpoint="http://localhost/v1",
                temperature=None,
                max_completion_tokens=100,
                reasoning_effort="medium",
                use_legacy_max_tokens=False,
                timeout=300.0,
                max_retries=2,
                scheme=scheme,
            )

            output_dir = root / "rs3"
            summary = convert_results(predictions, output_dir, scheme)
            rs3_root = ET.parse(output_dir / "demo.rs3").getroot()
            segment_texts = [
                segment.text for segment in rs3_root.findall("./body/segment")
            ]

        self.assertEqual(summary.generated, 1)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(segment_texts, ["Main & claim.", "A supporting <detail>."])


if __name__ == "__main__":
    unittest.main()
