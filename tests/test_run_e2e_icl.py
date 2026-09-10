import pathlib
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

from src.run_e2e_icl import (
    Document,
    CompletionResult,
    ExperimentSummary,
    OpenAIChatClient,
    build_messages,
    inject_tsv,
    read_tsv_documents,
    resolve_prompt,
    run_experiment,
)
from src.schemes import Scheme


TEST_SCHEME = Scheme(
    name="test",
    version="1",
    description="test scheme",
    prompt="ICL_test_e2e.txt",
    relations={"Joint": "multinuc"},
    sha256="a" * 64,
    path=pathlib.Path("test.yaml"),
)


class TsvDocumentTests(unittest.TestCase):
    def write_tsv(self, contents: str) -> pathlib.Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = pathlib.Path(temp_dir.name) / "documents.tsv"
        path.write_text(contents, encoding="utf-8")
        return path

    def test_groups_documents_and_preserves_row_order(self):
        path = self.write_tsv(
            "doc_id\tindex\ttext\n"
            "d1\t1\tFirst.\n"
            "d1\t2\tSecond.\n"
            "d2\t1\tOther.\n"
        )

        documents = read_tsv_documents(path)

        self.assertEqual([document.doc_id for document in documents], ["d1", "d2"])
        self.assertEqual(documents[0].header, ("index", "text"))
        self.assertEqual(documents[0].rows, (("1", "First."), ("2", "Second.")))
        self.assertEqual(documents[1].rows, (("1", "Other."),))

    def test_assigns_indices_when_column_is_absent(self):
        path = self.write_tsv("doc_id\ttext\nd1\tFirst.\nd1\tSecond.\n")

        documents = read_tsv_documents(path)

        self.assertEqual(documents[0].header, ("index", "text"))
        self.assertEqual(documents[0].rows, (("1", "First."), ("2", "Second.")))

    def test_rejects_empty_file(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            read_tsv_documents(self.write_tsv(""))

    def test_rejects_missing_required_columns(self):
        with self.assertRaisesRegex(ValueError, "doc_id"):
            read_tsv_documents(self.write_tsv("text\nFirst.\n"))
        with self.assertRaisesRegex(ValueError, "text"):
            read_tsv_documents(self.write_tsv("doc_id\nd1\n"))

    def test_rejects_blank_document_id_or_text(self):
        with self.assertRaisesRegex(ValueError, "doc_id"):
            read_tsv_documents(self.write_tsv("doc_id\ttext\n\tFirst.\n"))
        with self.assertRaisesRegex(ValueError, "text"):
            read_tsv_documents(self.write_tsv("doc_id\ttext\nd1\t \n"))

    def test_rejects_bad_or_duplicate_indices_and_unknown_columns(self):
        with self.assertRaisesRegex(ValueError, "positive canonical integer"):
            read_tsv_documents(self.write_tsv("doc_id\tindex\ttext\nd1\t01\tFirst.\n"))
        with self.assertRaisesRegex(ValueError, "duplicate index"):
            read_tsv_documents(
                self.write_tsv(
                    "doc_id\tindex\ttext\nd1\t1\tFirst.\nd1\t1\tSecond.\n"
                )
            )
        with self.assertRaisesRegex(ValueError, "unsupported columns"):
            read_tsv_documents(
                self.write_tsv("doc_id\ttext\tgenre\nd1\tFirst.\tnews\n")
            )

    def test_preserves_edu_text_for_rs3_hydration(self):
        documents = read_tsv_documents(
            self.write_tsv("doc_id\ttext\nd1\t  Preserve me.  \n")
        )

        self.assertEqual(documents[0].rows[0], ("1", "  Preserve me.  "))


class PromptCompositionTests(unittest.TestCase):
    def setUp(self):
        self.document = Document(
            doc_id="d1",
            header=("index", "text"),
            rows=(("1", "First."), ("2", "Second.")),
        )

    def test_builds_exact_system_and_user_messages(self):
        self.assertEqual(
            build_messages("SYSTEM SECRET", "USER BODY"),
            [
                {"role": "system", "content": "SYSTEM SECRET"},
                {"role": "user", "content": "USER BODY"},
            ],
        )

    def test_injects_document_into_terminal_tsv_block(self):
        result = inject_tsv("intro\n```tsv\n```\n", self.document)

        self.assertEqual(
            result,
            "intro\n```tsv\nindex\ttext\n1\tFirst.\n2\tSecond.\n```\n",
        )

    def test_rejects_missing_nonterminal_or_multiple_placeholders(self):
        with self.assertRaisesRegex(ValueError, "terminal"):
            inject_tsv("intro", self.document)
        with self.assertRaisesRegex(ValueError, "terminal"):
            inject_tsv("```tsv\n```\ntrailing", self.document)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            inject_tsv("```tsv\n```\n```tsv\n```\n", self.document)

    def test_resolves_filename_under_prompt_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_dir = pathlib.Path(temp_dir)
            prompt = prompt_dir / "ICL_rstweb_algo_e2e.txt"
            prompt.write_text("prompt", encoding="utf-8")

            self.assertEqual(resolve_prompt(prompt.name, prompt_dir), prompt)
            self.assertEqual(resolve_prompt(str(prompt), prompt_dir), prompt)

    def test_rejects_non_icl_prompt_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_dir = pathlib.Path(temp_dir)
            prompt = prompt_dir / "rstweb.md"
            prompt.write_text("prompt", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "ICL_"):
                resolve_prompt(str(prompt), prompt_dir)


class FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class OpenAIChatClientTests(unittest.TestCase):
    def test_normalizes_chat_completion_response(self):
        response = SimpleNamespace(
            id="response-1",
            model="returned-model-snapshot",
            system_fingerprint="fingerprint-1",
            created=1234567890,
            service_tier="default",
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="(NN-Joint (text 1) (text 2))"),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=12,
                completion_tokens=8,
                total_tokens=20,
                prompt_tokens_details=SimpleNamespace(cached_tokens=4),
                completion_tokens_details=SimpleNamespace(reasoning_tokens=6),
            ),
        )
        completions = FakeCompletions(response)
        sdk_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        client = OpenAIChatClient(
            endpoint="http://localhost:8000/v1",
            api_key="secret",
            timeout=15.0,
            client=sdk_client,
        )

        result = client.complete(
            model="test-model",
            messages=[{"role": "user", "content": "parse"}],
            temperature=0.2,
            max_completion_tokens=123,
            reasoning_effort="medium",
            use_legacy_max_tokens=False,
        )

        self.assertEqual(
            result,
            CompletionResult(
                content="(NN-Joint (text 1) (text 2))",
                response_id="response-1",
                finish_reason="stop",
                usage={
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                    "total_tokens": 20,
                    "prompt_tokens_details": {"cached_tokens": 4},
                    "completion_tokens_details": {"reasoning_tokens": 6},
                },
                returned_model="returned-model-snapshot",
                system_fingerprint="fingerprint-1",
                created=1234567890,
                service_tier="default",
            ),
        )
        self.assertEqual(
            completions.calls,
            [{
                "model": "test-model",
                "messages": [{"role": "user", "content": "parse"}],
                "temperature": 0.2,
                "max_completion_tokens": 123,
                "reasoning_effort": "medium",
            }],
        )

    def test_omits_optional_sampling_and_reasoning_and_supports_legacy_limit(self):
        response = SimpleNamespace(
            id="response-1",
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="(text 1)"),
                finish_reason="stop",
            )],
            usage=None,
        )
        completions = FakeCompletions(response)
        sdk_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        client = OpenAIChatClient("endpoint", "secret", 15.0, client=sdk_client)

        client.complete(
            model="compatible-model",
            messages=[{"role": "user", "content": "parse"}],
            temperature=None,
            max_completion_tokens=321,
            reasoning_effort=None,
            use_legacy_max_tokens=True,
        )

        self.assertEqual(
            completions.calls,
            [{
                "model": "compatible-model",
                "messages": [{"role": "user", "content": "parse"}],
                "max_tokens": 321,
            }],
        )

    def test_rejects_response_without_choices(self):
        completions = FakeCompletions(SimpleNamespace(id="response-1", choices=[], usage=None))
        sdk_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        client = OpenAIChatClient("endpoint", "secret", 15.0, client=sdk_client)

        with self.assertRaisesRegex(RuntimeError, "no choices"):
            client.complete(
                model="model",
                messages=[],
                temperature=None,
                max_completion_tokens=10,
                reasoning_effort=None,
                use_legacy_max_tokens=False,
            )


class SequencedClient:
    def __init__(self):
        self.calls = []

    def complete(
        self,
        *,
        model,
        messages,
        temperature,
        max_completion_tokens,
        reasoning_effort,
        use_legacy_max_tokens,
    ):
        self.calls.append({
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
            "reasoning_effort": reasoning_effort,
            "use_legacy_max_tokens": use_legacy_max_tokens,
        })
        user_message = messages[1]["content"]
        if "Failure." in user_message:
            raise RuntimeError("server unavailable")
        response_number = len(self.calls)
        return CompletionResult(
            content="(NN-Joint (text 1) (text 2))",
            response_id=f"r{response_number}",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )


class RunExperimentTests(unittest.TestCase):
    def test_writes_prompt_free_records_and_continues_after_failure(self):
        documents = [
            Document("d1", ("index", "text"), (("1", "First."),)),
            Document("d2", ("index", "text"), (("1", "Failure."),)),
            Document("d3", ("index", "text"), (("1", "Last."),)),
        ]
        client = SequencedClient()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = pathlib.Path(temp_dir) / "nested" / "results.jsonl"
            summary = run_experiment(
                documents=documents,
                system_prompt="SYSTEM SECRET",
                icl_prompt="USER SECRET\n```tsv\n```\n",
                prompt_name="ICL_rstweb_algo_e2e.txt",
                output_path=output,
                client=client,
                model="test-model",
                endpoint="http://localhost:8000/v1",
                temperature=None,
                max_completion_tokens=8192,
                reasoning_effort="medium",
                use_legacy_max_tokens=False,
                timeout=300.0,
                max_retries=2,
                scheme=TEST_SCHEME,
            )
            serialized = output.read_text(encoding="utf-8")

        records = [__import__("json").loads(line) for line in serialized.splitlines()]
        self.assertEqual(summary, ExperimentSummary(succeeded=2, failed=1))
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["record_version"], 2)
        self.assertEqual(records[0]["prompt_name"], "ICL_rstweb_algo_e2e.txt")
        self.assertEqual(records[0]["status"], "ok")
        self.assertEqual(records[0]["raw_tree"], "(NN-Joint (text 1) (text 2))")
        self.assertEqual(records[0]["scheme"], TEST_SCHEME.metadata())
        self.assertEqual(records[0]["edus"], [{"index": "1", "text": "First."}])
        self.assertEqual(len(records[0]["prompt_sha256"]), 64)
        self.assertEqual(len(records[0]["system_prompt_sha256"]), 64)
        self.assertEqual(
            records[0]["decoding"],
            {
                "temperature": None,
                "reasoning_effort": "medium",
                "max_completion_tokens": 8192,
                "max_tokens": None,
            },
        )
        self.assertEqual(
            records[0]["transport"],
            {"timeout_seconds": 300.0, "max_retries": 2},
        )
        self.assertEqual(records[0]["response"]["id"], "r1")
        self.assertIsNone(records[0]["error"])
        self.assertEqual(records[1]["status"], "error")
        self.assertIsNone(records[1]["raw_tree"])
        self.assertIsNone(records[1]["response"])
        self.assertEqual(
            records[1]["error"],
            {"type": "RuntimeError", "message": "server unavailable"},
        )
        self.assertEqual(records[2]["status"], "ok")
        self.assertNotIn("SYSTEM SECRET", serialized)
        self.assertNotIn("USER SECRET", serialized)


class CliHelpTests(unittest.TestCase):
    def test_runner_help_documents_configuration_and_prompt_free_output(self):
        result = subprocess.run(
            [sys.executable, "-m", "src.run_e2e_icl", "--help"],
            check=True,
            capture_output=True,
            text=True,
        )

        for expected in (
            "--endpoint",
            "--model",
            "--prompt",
            "--scheme",
            "--reasoning-effort",
            "--max-completion-tokens",
            "--max-tokens",
            "OPENAI_API_KEY",
            "prompt_name",
            "excludes prompt bodies",
        ):
            self.assertIn(expected, result.stdout)

    def test_converter_help_documents_inputs_outputs_and_report(self):
        result = subprocess.run(
            [sys.executable, "-m", "src.convert_e2e_to_rs3", "--help"],
            check=True,
            capture_output=True,
            text=True,
        )

        for expected in ("--input", "--output-dir", "--scheme", "--report"):
            self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
