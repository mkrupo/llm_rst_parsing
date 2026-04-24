"""
analyze_confusions.py
======================

This script reads pre‑computed confusion matrices (in JSON format) and
creates simple heatmap visualisations using matplotlib.  Each confusion
matrix corresponds to a single annotation standard and plots the counts of
predicted versus gold coarse labels.  The resulting figures are saved to
disk as PDF files for inclusion in reports.

To run the script on the directory created by the metrics module::

    python -m rst_prompt_adequacy.src.analyze_confusions \
        --input results/metrics/confusions \
        --output results/figures

The output directory will be created if it does not exist.  Each PDF
generated will be named ``confusion_<standard>.pdf``.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import List

import matplotlib.pyplot as plt
import numpy as np


def plot_confusion(confusion: List[List[int]], labels: List[str], title: str, filepath: pathlib.Path) -> None:
    """Render a confusion heatmap and save it as a PDF.

    Parameters
    ----------
    confusion: List[List[int]]
        Square matrix of counts where rows correspond to gold labels and
        columns correspond to predicted labels.
    labels: List[str]
        Ordered list of label names for both axes.
    title: str
        Title to display above the heatmap.
    filepath: pathlib.Path
        Path to the PDF file to write.
    """
    arr = np.array(confusion)
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 0.4), max(6, len(labels) * 0.4)))
    im = ax.imshow(arr, interpolation="nearest")
    ax.set_title(title)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("Gold label")
    # Set ticks
    ax.set_xticks(np.arange(len(labels)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=90)
    ax.set_yticklabels(labels)
    # Loop over data dimensions and create text annotations
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            text = ax.text(j, i, arr[i, j], ha="center", va="center", color="black")
    fig.tight_layout()
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filepath, format="pdf")
    plt.close(fig)


def process_confusion_dir(input_dir: pathlib.Path, output_dir: pathlib.Path) -> None:
    """Read all confusion JSON files in a directory and generate PDFs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for json_path in input_dir.glob("confusion_*.json"):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        labels = data.get("labels")
        confusion = data.get("confusion")
        if labels and confusion:
            standard = json_path.stem.replace("confusion_", "")
            title = f"Confusion matrix for {standard}"
            out_file = output_dir / f"confusion_{standard}.pdf"
            plot_confusion(confusion, labels, title, out_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate confusion matrix plots from JSON files.")
    parser.add_argument("--input", type=str, required=True, help="Directory containing confusion JSON files.")
    parser.add_argument("--output", type=str, required=True, help="Directory to save PDF figures.")
    args = parser.parse_args()
    process_confusion_dir(pathlib.Path(args.input), pathlib.Path(args.output))


if __name__ == "__main__":
    main()