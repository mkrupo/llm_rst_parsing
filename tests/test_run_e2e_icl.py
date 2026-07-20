import pathlib
import tempfile
import unittest

from src.run_e2e_icl import (
    Document,
    build_messages,
    inject_tsv,
    read_tsv_documents,
    resolve_prompt,
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


if __name__ == "__main__":
    unittest.main()
