"""
metrics.py
==========

Collection of functions for evaluating model predictions against ground truth
and summarising important statistics for the relation‑labeling benchmark.

The module can be used both programmatically and via its command‑line
interface.  See the bottom of this file for CLI usage details.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter, defaultdict
from itertools import combinations
from typing import Dict, List, Tuple, Any

import numpy as np
from scipy.spatial.distance import jensenshannon
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix


def distribution(labels: List[str], label_space: List[str]) -> np.ndarray:
    """Compute the empirical distribution over a finite label space."""
    c = Counter(labels)
    arr = np.array([c.get(x, 0) for x in label_space], dtype=float)
    if arr.sum() == 0:
        # return uniform to avoid division by zero
        return np.ones(len(label_space)) / len(label_space)
    return arr / arr.sum()


def jsd(pred_labels: List[str], gold_labels: List[str], label_space: List[str]) -> float:
    """Compute the Jensen–Shannon divergence between two distributions."""
    p = distribution(pred_labels, label_space)
    q = distribution(gold_labels, label_space)
    return float(jensenshannon(p, q, base=2.0) ** 2)


def classification_report_rows(gold: List[str], pred: List[str], labels: List[str]) -> Dict[str, Any]:
    """Compute basic classification statistics (accuracy, macro F1, JSD and confusion)."""
    return {
        "accuracy": float(accuracy_score(gold, pred)),
        "macro_f1": float(f1_score(gold, pred, labels=labels, average="macro", zero_division=0)),
        "jsd": jsd(pred, gold, labels),
        "confusion": confusion_matrix(gold, pred, labels=labels).tolist(),
    }


def native_validity(records: List[Dict[str, Any]], valid_labels: Dict[str, List[str]]) -> float:
    """Compute the fraction of predictions with a recognised native label.

    Parameters
    ----------
    records: List[Dict[str, Any]]
        Prediction records with a parsed field containing native_label.
    valid_labels: Dict[str, List[str]]
        Mapping of standards to lists of allowed native labels.

    Returns
    -------
    float
        Ratio of valid predictions.
    """
    total = 0
    valid = 0
    for rec in records:
        parsed = rec.get("parsed") or {}
        native = parsed.get("native_label")
        standard = rec.get("standard")
        if native is not None:
            total += 1
            if standard in valid_labels and native in valid_labels[standard]:
                valid += 1
    return valid / total if total else 0.0


def native_accuracy(records: List[Dict[str, Any]]) -> float:
    """Compute accuracy on the native label when gold_native is available."""
    gold = []
    pred = []
    for rec in records:
        g = rec.get("gold_native")
        if g is not None:
            parsed = rec.get("parsed") or {}
            gold.append(g)
            pred.append(parsed.get("native_label"))
    if not gold:
        return float("nan")
    return accuracy_score(gold, pred)


def coarse_accuracy_macro_f1(records: List[Dict[str, Any]], label_space: List[str]) -> Tuple[float, float]:
    """Compute coarse label accuracy and macro F1."""
    gold = []
    pred = []
    for rec in records:
        if rec.get("gold_coarse") is not None:
            gold.append(rec["gold_coarse"])
            parsed = rec.get("parsed") or {}
            pred.append(parsed.get("coarse_label"))
    if not gold:
        return float("nan"), float("nan")
    accuracy = accuracy_score(gold, pred)
    macro_f1 = f1_score(gold, pred, labels=label_space, average="macro", zero_division=0)
    return accuracy, macro_f1


def self_consistency(records: List[Dict[str, Any]]) -> float:
    """Compute self‑consistency across repeated predictions.

    Predictions are grouped by the tuple (item_id, model, standard, formulation, shot).
    For each group with more than one record, the function computes the proportion
    of identical coarse labels among all pairs of predictions.  The final score
    is the average across groups.
    """
    groups: Dict[Tuple[str, str, str, str, str], List[str]] = defaultdict(list)
    for rec in records:
        key = (rec.get("item_id"), rec.get("model"), rec.get("standard"), rec.get("formulation"), rec.get("shot"))
        parsed = rec.get("parsed") or {}
        coarse = parsed.get("coarse_label")
        if coarse is not None:
            groups[key].append(coarse)
    scores = []
    for labels in groups.values():
        if len(labels) < 2:
            continue
        total_pairs = 0
        agree_pairs = 0
        for a, b in combinations(labels, 2):
            total_pairs += 1
            if a == b:
                agree_pairs += 1
        if total_pairs:
            scores.append(agree_pairs / total_pairs)
    return float(np.mean(scores)) if scores else float("nan")


def cross_model_consistency(records: List[Dict[str, Any]]) -> float:
    """Compute cross‑model consistency for each item/condition.

    For each (item_id, standard, formulation, shot) the coarse label is
    aggregated per model by majority vote across repeats.  The function then
    computes the proportion of item/condition instances where all models agree
    on the coarse label.  If fewer than two models are present the score is
    undefined (NaN).
    """
    # Build map: (item_id, standard, formulation, shot) -> model -> list of coarse predictions
    agg: Dict[Tuple[str, str, str, str], Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    for rec in records:
        key = (rec.get("item_id"), rec.get("standard"), rec.get("formulation"), rec.get("shot"))
        model = rec.get("model")
        parsed = rec.get("parsed") or {}
        coarse = parsed.get("coarse_label")
        if coarse is not None and model is not None:
            agg[key][model].append(coarse)
    # For each key, compute majority coarse for each model
    agreements = []
    for key, model_dict in agg.items():
        if len(model_dict) < 2:
            continue
        model_majorities = []
        for model, labels in model_dict.items():
            if labels:
                # majority vote, fallback to first if tie
                counts = Counter(labels)
                majority_label = max(counts.items(), key=lambda x: (x[1], x[0]))[0]
                model_majorities.append(majority_label)
        if len(model_majorities) >= 2:
            # Check if all majority labels are the same
            all_same = len(set(model_majorities)) == 1
            agreements.append(all_same)
    if not agreements:
        return float("nan")
    return sum(agreements) / len(agreements)


def distributional_alignment(records: List[Dict[str, Any]], label_space: List[str]) -> float:
    """Compute Jensen–Shannon divergence between predicted and gold distributions."""
    gold = []
    pred = []
    for rec in records:
        if rec.get("gold_coarse") is not None:
            gold.append(rec["gold_coarse"])
            parsed = rec.get("parsed") or {}
            pred.append(parsed.get("coarse_label"))
    if not gold:
        return float("nan")
    return jsd(pred, gold, label_space)


def load_predictions(prediction_dir: pathlib.Path) -> List[Dict[str, Any]]:
    """Load all prediction JSONL files in the given directory into a list."""
    records: List[Dict[str, Any]] = []
    for path in prediction_dir.glob("*.jsonl"):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    records.append(rec)
                except json.JSONDecodeError:
                    continue
    return records


def write_summary(summary: Dict[str, Any], out_path: pathlib.Path) -> None:
    """Write a dictionary of summary metrics to a CSV file."""
    import csv
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=summary.keys())
        writer.writeheader()
        writer.writerow(summary)


def compute_and_save_metrics(prediction_dir: pathlib.Path, mapping_path: pathlib.Path, out_dir: pathlib.Path) -> None:
    """Compute summary metrics from prediction files and save them as CSVs.

    The mapping file should define ``valid_labels`` and ``coarse_labels``.  If
    these keys are missing, reasonable defaults will be assumed.  Multiple
    output files are produced summarising the metrics listed in the
    experiment plan.
    """
    # Load records and mapping
    records = load_predictions(prediction_dir)
    mapping = {}
    if mapping_path.exists():
        import yaml
        mapping = yaml.safe_load(open(mapping_path, "r", encoding="utf-8")) or {}
    valid_labels = mapping.get("valid_labels", {})
    coarse_labels: List[str] = mapping.get("coarse_labels", [])

    # Native validity
    nat_valid = native_validity(records, valid_labels)
    write_summary({"native_validity": nat_valid}, out_dir / "native_validity.csv")

    # Native accuracy
    nat_acc = native_accuracy(records)
    write_summary({"native_accuracy": nat_acc}, out_dir / "native_accuracy.csv")

    # Coarse accuracy/macro F1
    acc, f1 = coarse_accuracy_macro_f1(records, coarse_labels)
    write_summary({"coarse_accuracy": acc, "coarse_macro_f1": f1}, out_dir / "coarse_accuracy_macro_f1.csv")

    # Self consistency
    sc = self_consistency(records)
    write_summary({"self_consistency": sc}, out_dir / "self_consistency.csv")

    # Cross model consistency
    cmc = cross_model_consistency(records)
    write_summary({"cross_model_consistency": cmc}, out_dir / "cross_model_consistency.csv")

    # Distributional alignment
    js_div = distributional_alignment(records, coarse_labels)
    write_summary({"distributional_alignment_jsd": js_div}, out_dir / "distributional_alignment_jsd.csv")

    # Confusion matrices per standard (coarse)
    # We produce one file per standard, aggregated across models and repeats
    confusion_dir = out_dir / "confusions"
    confusion_dir.mkdir(parents=True, exist_ok=True)
    for standard in set(rec.get("standard") for rec in records):
        # Filter records for this standard
        sub = [rec for rec in records if rec.get("standard") == standard]
        gold = []
        pred = []
        for rec in sub:
            if rec.get("gold_coarse") is not None:
                gold.append(rec["gold_coarse"])
                parsed = rec.get("parsed") or {}
                pred.append(parsed.get("coarse_label"))
        if gold:
            cm = confusion_matrix(gold, pred, labels=coarse_labels).tolist()
            # Write as JSON for ease of later plotting
            with open(confusion_dir / f"confusion_{standard}.json", "w", encoding="utf-8") as f:
                json.dump({"labels": coarse_labels, "confusion": cm}, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute metrics for relation label predictions.")
    parser.add_argument("--input", type=str, required=True, help="Directory containing parsed prediction JSONL files.")
    parser.add_argument("--mapping", type=str, required=True, help="YAML file with valid native labels and coarse labels.")
    parser.add_argument("--output", type=str, required=True, help="Directory to write metric CSVs and confusion matrices to.")
    args = parser.parse_args()
    compute_and_save_metrics(pathlib.Path(args.input), pathlib.Path(args.mapping), pathlib.Path(args.output))


if __name__ == "__main__":
    main()