"""
relation_mappings.py
====================

Static mappings from native relation names to coarse classes.  The benchmark
needs to harmonise different relation inventories so that models trained on
eRST, classical RST (via the RST website) and PCC annotation guidelines can
be evaluated on a common set of coarse labels.  This module defines
mappings for the known relations and exposes helper functions to resolve
unknown labels into the ``OTHER`` class.

If you wish to add new relations or adjust the mapping, edit the
dictionaries below and regenerate your mapping file via the CLI at the
bottom of this file.  The mapping file is consumed by :mod:`build_items`
to convert gold labels and by :mod:`metrics` to determine valid native
labels and the list of coarse classes.
"""

from __future__ import annotations

import json
import pathlib
from typing import Dict, List


COARSE_LABELS: List[str] = [
    "ATTRIBUTION",
    "BACKGROUND_CIRCUMSTANCE",
    "CAUSE_REASON",
    "RESULT",
    "CONDITION",
    "CONTRAST_CONCESSION",
    "ELABORATION",
    "EVALUATION_INTERPRETATION",
    "EVIDENCE_JUSTIFY",
    "PURPOSE_ENABLEMENT",
    "RESTATEMENT_SUMMARY",
    "TEMPORAL_SEQUENCE",
    "JOINT_LIST",
    "TEXTUAL_ORGANIZATION",
    "OTHER",
]


# Mapping from eRST native labels to coarse classes
ERST_NATIVE_TO_COARSE: Dict[str, str] = {
    # Attribution
    "attribution-positive": "ATTRIBUTION",
    "attribution-negative": "ATTRIBUTION",
    # Causal/contingency
    "causal-cause": "CAUSE_REASON",
    "causal-result": "RESULT",
    "contingency-condition": "CONDITION",
    "contingency-hypothetical": "CONDITION",
    # Contrastive relations
    "adversative-contrast": "CONTRAST_CONCESSION",
    "adversative-concession": "CONTRAST_CONCESSION",
    "antithesis": "CONTRAST_CONCESSION",
    # Background/Circumstance
    "context-background": "BACKGROUND_CIRCUMSTANCE",
    "context-circumstance": "BACKGROUND_CIRCUMSTANCE",
    # Elaboration
    "elaboration-additional": "ELABORATION",
    "elaboration-attribute": "ELABORATION",
    "elaboration-specification": "ELABORATION",
    # Evaluation
    "evaluation-comment": "EVALUATION_INTERPRETATION",
    "evaluation-opinion": "EVALUATION_INTERPRETATION",
    "interpretation": "EVALUATION_INTERPRETATION",
    # Evidence/Justify/Reason
    "explanation-evidence": "EVIDENCE_JUSTIFY",
    "explanation-justify": "EVIDENCE_JUSTIFY",
    "explanation-reason": "CAUSE_REASON",
    # Purpose/Enablement/Means/Manner
    "purpose-goal": "PURPOSE_ENABLEMENT",
    "purpose-attribute": "PURPOSE_ENABLEMENT",
    "manner-means": "PURPOSE_ENABLEMENT",
    # Restatement/Summary
    "restatement-repetition": "RESTATEMENT_SUMMARY",
    "restatement-summary": "RESTATEMENT_SUMMARY",
    # Temporal
    "temporal-sequence": "TEMPORAL_SEQUENCE",
    "temporal-same-time": "TEMPORAL_SEQUENCE",
    # Joint/List/Multinuclear
    "joint-list": "JOINT_LIST",
    "joint-sequence": "TEMPORAL_SEQUENCE",
    "joint-other": "JOINT_LIST",
    # Textual organisation
    "organization-heading": "TEXTUAL_ORGANIZATION",
    "organization-preparation": "TEXTUAL_ORGANIZATION",
}


# Mapping from classical RST native labels to coarse classes
RSTWEB_NATIVE_TO_COARSE: Dict[str, str] = {
    "Antithesis": "CONTRAST_CONCESSION",
    "Background": "BACKGROUND_CIRCUMSTANCE",
    "Circumstance": "BACKGROUND_CIRCUMSTANCE",
    "Concession": "CONTRAST_CONCESSION",
    "Condition": "CONDITION",
    "Consequence": "RESULT",
    "Contrast": "CONTRAST_CONCESSION",
    "Elaboration": "ELABORATION",
    "Enablement": "PURPOSE_ENABLEMENT",
    "Evaluation": "EVALUATION_INTERPRETATION",
    "Evidence": "EVIDENCE_JUSTIFY",
    "Interpretation": "EVALUATION_INTERPRETATION",
    "Justify": "EVIDENCE_JUSTIFY",
    "Motivation": "PURPOSE_ENABLEMENT",
    "Explanation": "EVIDENCE_JUSTIFY",
    "Non-volitional Cause": "CAUSE_REASON",
    "Non-volitional Result": "RESULT",
    "Otherwise": "CONDITION",
    "Purpose": "PURPOSE_ENABLEMENT",
    "Restatement": "RESTATEMENT_SUMMARY",
    "Solutionhood": "PURPOSE_ENABLEMENT",
    "Summary": "RESTATEMENT_SUMMARY",
    "Volitional Cause": "CAUSE_REASON",
    "Volitional Result": "RESULT",
    # Multinuclear
    "Contrast (multi)": "CONTRAST_CONCESSION",
    "Joint": "JOINT_LIST",
    "List": "JOINT_LIST",
    "Sequence": "TEMPORAL_SEQUENCE",
}


# Mapping from PCC native labels to coarse classes
PCC_NATIVE_TO_COARSE: Dict[str, str] = {
    # Pragmatic
    "Background": "BACKGROUND_CIRCUMSTANCE",
    "Antithesis": "CONTRAST_CONCESSION",
    "Concession": "CONTRAST_CONCESSION",
    "Evidence": "EVIDENCE_JUSTIFY",
    "Reason": "CAUSE_REASON",
    "Reason-N": "CAUSE_REASON",
    "Justify": "EVIDENCE_JUSTIFY",
    "Evaluation-S": "EVALUATION_INTERPRETATION",
    "Evaluation-N": "EVALUATION_INTERPRETATION",
    "Motivation": "PURPOSE_ENABLEMENT",
    "Enablement": "PURPOSE_ENABLEMENT",
    # Semantic
    "Circumstance": "BACKGROUND_CIRCUMSTANCE",
    "Condition": "CONDITION",
    "Otherwise": "CONDITION",
    "Unless": "CONDITION",
    "Elaboration": "ELABORATION",
    "E-Elaboration": "ELABORATION",
    "Interpretation": "EVALUATION_INTERPRETATION",
    "Means": "PURPOSE_ENABLEMENT",
    "Cause": "CAUSE_REASON",
    "Result": "RESULT",
    "Purpose": "PURPOSE_ENABLEMENT",
    "Solutionhood": "PURPOSE_ENABLEMENT",
    # Textual
    "Preparation": "TEXTUAL_ORGANIZATION",
    "Restatement": "RESTATEMENT_SUMMARY",
    "Summary": "RESTATEMENT_SUMMARY",
    # Multinuclear
    "Contrast": "CONTRAST_CONCESSION",
    "Sequence": "TEMPORAL_SEQUENCE",
    "List": "JOINT_LIST",
    "Conjunction": "JOINT_LIST",
    "Joint": "JOINT_LIST",
}


# Valid native labels per standard (non‑exhaustive lists).  Extend these as needed.
VALID_LABELS: Dict[str, List[str]] = {
    "erst": list(ERST_NATIVE_TO_COARSE.keys()),
    "rstweb": list(RSTWEB_NATIVE_TO_COARSE.keys()),
    "pcc": list(PCC_NATIVE_TO_COARSE.keys()),
}


def build_mapping_file(path: pathlib.Path) -> None:
    """Generate a YAML mapping file to disk.

    The mapping file includes three entries:

    * ``native_to_coarse``: nested dict mapping native labels to coarse labels.
    * ``valid_labels``: dict mapping standard names to lists of valid native labels.
    * ``coarse_labels``: list of all coarse labels in a fixed order.

    This file can be used by the ``build_items`` script to map gold labels and
    by the ``metrics`` script to know which labels are legal for validation.

    Parameters
    ----------
    path: pathlib.Path
        The file to write.  Parent directories will be created automatically.
    """
    import yaml
    mapping = {
        "native_to_coarse": {
            **{k: v for k, v in ERST_NATIVE_TO_COARSE.items()},
            **{k: v for k, v in RSTWEB_NATIVE_TO_COARSE.items()},
            **{k: v for k, v in PCC_NATIVE_TO_COARSE.items()},
        },
        "valid_labels": VALID_LABELS,
        "coarse_labels": COARSE_LABELS,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(mapping, f, sort_keys=False, allow_unicode=True)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Generate the relation mapping YAML file.")
    parser.add_argument("--output", type=str, required=True, help="Path to write the YAML mapping file.")
    args = parser.parse_args()
    build_mapping_file(pathlib.Path(args.output))


if __name__ == "__main__":
    main()