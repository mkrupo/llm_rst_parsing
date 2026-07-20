import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
RSTWEB_PROMPTS = (
    "ICL_rstweb_as_written.txt",
    "ICL_rstweb_as_written_e2e.txt",
    "ICL_rstweb_algo.txt",
    "ICL_rstweb_algo_e2e.txt",
)


class RstwebIclPromptTests(unittest.TestCase):
    def test_all_rstweb_counterparts_exist_and_are_nonempty(self):
        for name in RSTWEB_PROMPTS:
            with self.subTest(name=name):
                content = (PROMPTS / name).read_text(encoding="utf-8")
                self.assertGreater(len(content.splitlines()), 50)

    def test_e2e_prompts_match_pcc_tree_framing(self):
        for name in ("ICL_rstweb_as_written_e2e.txt", "ICL_rstweb_algo_e2e.txt"):
            with self.subTest(name=name):
                content = (PROMPTS / name).read_text(encoding="utf-8")
                self.assertIn("build a bracketed discourse tree end-to-end", content)
                self.assertIn("bracketed tree example:", content)
                self.assertTrue(content.endswith("```tsv\n```\n"))
                self.assertEqual(content.count("```tsv\n```"), 1)

    def test_pairwise_prompts_match_pcc_pair_framing(self):
        for name in ("ICL_rstweb_as_written.txt", "ICL_rstweb_algo.txt"):
            with self.subTest(name=name):
                content = (PROMPTS / name).read_text(encoding="utf-8")
                self.assertIn("assign rhetorical relations", content)
                self.assertIn("doc_id\tunit1\tunit2\tdirection", content)

    def test_prompts_exclude_pcc_only_labels(self):
        for name in RSTWEB_PROMPTS:
            with self.subTest(name=name):
                content = (PROMPTS / name).read_text(encoding="utf-8")
                for forbidden in ("Conjunction", "E-Elaboration", "Reason-N", "Unless"):
                    self.assertNotIn(forbidden, content)

    def test_prompts_cover_rstweb_inventory(self):
        required = (
            "Antithesis", "Background", "Circumstance", "Concession", "Condition",
            "Contrast", "Elaboration", "Enablement", "Evaluation", "Evidence",
            "Interpretation", "Justify", "Motivation", "Non-volitional Cause",
            "Non-volitional Result", "Otherwise", "Preparation", "Purpose",
            "Restatement", "Solutionhood", "Summary", "Volitional Cause",
            "Volitional Result", "Joint", "List", "Sequence",
        )
        for name in RSTWEB_PROMPTS:
            content = (PROMPTS / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                for relation in required:
                    self.assertIn(relation, content)


if __name__ == "__main__":
    unittest.main()
