import pathlib
import re
import tempfile
import unittest

from src.schemes import load_scheme


ROOT = pathlib.Path(__file__).resolve().parent.parent


class SchemeTests(unittest.TestCase):
    def test_loads_checked_in_pcc_profile_with_provenance(self):
        scheme = load_scheme(ROOT / "configs" / "schemes" / "pcc.yaml")

        self.assertEqual(scheme.name, "pcc")
        self.assertEqual(scheme.version, "1")
        self.assertEqual(scheme.prompt, "ICL_pcc_algo_e2e.txt")
        self.assertEqual(scheme.relations["cause"], "rst")
        self.assertEqual(scheme.relations["joint"], "multinuc")
        self.assertEqual(len(scheme.sha256), 64)

    def test_every_scheme_prompt_declares_its_exact_inventory_and_contract(self):
        scheme_paths = sorted((ROOT / "configs" / "schemes").glob("*.yaml"))
        self.assertTrue(scheme_paths)
        for scheme_path in scheme_paths:
            with self.subTest(scheme=scheme_path.name):
                scheme = load_scheme(scheme_path)
                prompt = (ROOT / "prompts" / scheme.prompt).read_text(encoding="utf-8")
                inventory_match = re.search(
                    r"Use only these exact identifiers:\n(?P<labels>.*?)\.\n",
                    prompt,
                    re.DOTALL,
                )
                self.assertIsNotNone(inventory_match)
                labels = {
                    label.strip()
                    for label in inventory_match.group("labels")
                    .replace("\n", " ")
                    .split(",")
                }
                self.assertEqual(labels, set(scheme.relations))
                for required in (
                    "Return exactly one tree",
                    "every input index exactly once",
                    "same left-to-right order",
                    "Do not alter the supplied segmentation",
                    "Return only the compact tree",
                ):
                    self.assertIn(required, prompt)

        system_prompt = (ROOT / "prompts" / "system_prompt.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("Return only the requested compact tree", system_prompt)
        self.assertNotIn("world-famous", system_prompt)

    def test_rejects_unknown_keys_and_invalid_relation_types(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "scheme.yaml"
            path.write_text(
                "name: demo\nversion: 1\nprompt: ICL_demo_e2e.txt\n"
                "relations: {cause: invalid}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "rst.*multinuc"):
                load_scheme(path)

            path.write_text(
                "name: demo\nversion: 1\nprompt: ICL_demo_e2e.txt\n"
                "relations: {cause: rst}\ntypo: true\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unknown scheme keys"):
                load_scheme(path)

    def test_rejects_relation_names_that_break_compact_tree_syntax(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "scheme.yaml"
            path.write_text(
                "name: demo\nversion: 1\nprompt: ICL_demo_e2e.txt\n"
                "relations: {'causal result': rst}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "compact tree identifiers"):
                load_scheme(path)


if __name__ == "__main__":
    unittest.main()
