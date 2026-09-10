import unittest

from src.compact_tree import parse_compact_tree, validate_compact_tree


RELATIONS = {"cause": "rst", "joint": "multinuc"}


class CompactTreeTests(unittest.TestCase):
    def validate(self, source, indices=("1", "2")):
        tree = parse_compact_tree(source)
        validate_compact_tree(tree, indices, RELATIONS)

    def test_accepts_valid_mononuclear_multinuclear_and_single_edu_trees(self):
        self.validate("(NS-cause (text 1) (text 2))")
        self.validate("(NN-joint (text 1) (text 2))")
        self.validate("(text 1)", indices=("1",))

    def test_rejects_prose_unbalanced_trees_and_raw_relation_children(self):
        for source in (
            "Here is (NS-cause (text 1) (text 2))",
            "(NS-cause (text 1) (text 2)",
            "(NS-cause stray (text 1) (text 2))",
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.validate(source)

    def test_rejects_missing_duplicate_unknown_and_reordered_indices(self):
        invalid = (
            "(text 1)",
            "(NN-joint (text 1) (text 1))",
            "(NN-joint (text 1) (text 3))",
            "(NN-joint (text 2) (text 1))",
        )
        for source in invalid:
            with self.subTest(source=source), self.assertRaisesRegex(
                ValueError, "exactly match input order"
            ):
                self.validate(source)

    def test_rejects_unknown_relations_wrong_nuclearity_and_wrong_arity(self):
        invalid = (
            "(NS-invented (text 1) (text 2))",
            "(NN-cause (text 1) (text 2))",
            "(NS-joint (text 1) (text 2))",
            "(NS-cause (text 1) (text 2) (text 3))",
        )
        for source in invalid:
            with self.subTest(source=source), self.assertRaises(ValueError):
                indices = (
                    tuple(str(i) for i in range(1, 4))
                    if "3" in source
                    else ("1", "2")
                )
                self.validate(source, indices=indices)


if __name__ == "__main__":
    unittest.main()
