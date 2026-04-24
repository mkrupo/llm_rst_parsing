"""
build_items.py
================

This module contains a simple CLI for converting raw data files into a processed
JSONL format compatible with the relation‑labeling benchmark.  The expected
input is a directory of one or more JSON or JSONL files containing pre‑segmented
EDU pairs.  Each entry in the output will contain a minimal set of fields
including an identifier, the text spans on the left and right of the relation,
optional context, a native gold label (if available) and a coarse gold label.

The goal of this script is to take any upstream data and normalise it into
the schema described in the experiment plan.  See the README or the `data`
contract in the paper for details.

Usage (from the repository root)::

    python -m rst_prompt_adequacy.src.build_items \
        --input data/raw \
        --output data/processed/relation_pairs.jsonl \
        --mapping data/mappings/relation_map.yaml

The mapping file is optional and allows the script to convert raw native
labels into the coarse label space used by the benchmark.  The script
expects the mapping file to be a YAML document with two top‑level keys:
``native_to_coarse`` mapping native relation names to coarse classes, and
``valid_labels`` listing all allowed native labels for each standard.

This script is intentionally conservative – if the input data is already
in the correct format it will simply be copied to the output.  Otherwise
it attempts a best effort normalisation.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Dict, Any, Iterable, Optional

import yaml


def load_mapping(mapping_path: Optional[pathlib.Path]) -> Dict[str, Dict[str, str]]:
    """Load a YAML mapping file if provided.

    The mapping file should define a ``native_to_coarse`` dictionary mapping
    native relation names to coarse label names.  If the file is missing or
    invalid, an empty mapping is returned and coarse labels will not be
    generated automatically.

    Parameters
    ----------
    mapping_path: Optional[pathlib.Path]
        Path to the YAML mapping file.

    Returns
    -------
    Dict[str, Dict[str, str]]
        A dictionary containing at least the key ``native_to_coarse``.
    """
    if mapping_path is None or not mapping_path.exists():
        return {"native_to_coarse": {}}
    with open(mapping_path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return {"native_to_coarse": {}}
            return data
        except yaml.YAMLError:
            return {"native_to_coarse": {}}


def iter_input_records(input_dir: pathlib.Path) -> Iterable[Dict[str, Any]]:
    """Yield raw annotation records from JSON/JSONL files in a directory.

    The function walks through the provided directory and yields dictionaries
    for each record found in files ending with ``.json`` or ``.jsonl``.

    Parameters
    ----------
    input_dir: pathlib.Path
        The directory containing raw annotation files.

    Yields
    ------
    Dict[str, Any]
        Each raw record dictionary.
    """
    for path in input_dir.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".jsonl"}:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if isinstance(record, dict):
                            yield record
                    except json.JSONDecodeError:
                        # ignore malformed lines
                        continue


def normalise_record(raw: Dict[str, Any], mapping: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """Normalise a raw record into the benchmark schema.

    This function attempts to fill missing fields and map native labels
    to coarse labels using the supplied mapping.  Any missing mandatory
    fields will raise a ValueError.

    Parameters
    ----------
    raw: Dict[str, Any]
        The raw record dictionary.
    mapping: Dict[str, Dict[str, str]]
        The mapping dictionary loaded via :func:`load_mapping`.

    Returns
    -------
    Dict[str, Any]
        A normalised record conforming to the benchmark schema.
    """
    required_fields = {"item_id", "left", "right"}
    missing = required_fields - raw.keys()
    if missing:
        raise ValueError(f"Missing mandatory fields {missing} in record {raw.get('item_id')}")

    result: Dict[str, Any] = {
        "item_id": raw["item_id"],
        "source": raw.get("source", "unknown"),
        "genre": raw.get("genre", "unknown"),
        "doc_id": raw.get("doc_id", "unknown"),
        "left": raw["left"],
        "right": raw["right"],
        "context_before": raw.get("context_before", ""),
        "context_after": raw.get("context_after", ""),
        "gold_native": raw.get("gold_native"),
        "gold_standard": raw.get("gold_standard"),
        "gold_coarse": raw.get("gold_coarse"),
        "nuclearity": raw.get("nuclearity", "unknown"),
        "split": raw.get("split", "train"),
    }

    # Derive coarse label if missing and mapping available
    if result["gold_coarse"] is None and result["gold_native"] is not None:
        native_to_coarse = mapping.get("native_to_coarse", {})
        result["gold_coarse"] = native_to_coarse.get(result["gold_native"], None)

    return result


def build_items(input_dir: pathlib.Path, output_path: pathlib.Path, mapping_path: Optional[pathlib.Path] = None) -> None:
    """Process raw annotation files into a single JSONL output file.

    Parameters
    ----------
    input_dir: pathlib.Path
        Directory containing raw JSON/JSONL files.
    output_path: pathlib.Path
        The file to write normalised records into.
    mapping_path: Optional[pathlib.Path]
        Optional path to a YAML mapping file.
    """
    mapping = load_mapping(mapping_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out:
        for raw_record in iter_input_records(input_dir):
            try:
                record = normalise_record(raw_record, mapping)
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
            except ValueError as exc:
                # Log and skip invalid records
                print(f"Skipping record {raw_record.get('item_id')}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalise raw annotation files for the RST prompt benchmark.")
    parser.add_argument("--input", type=str, required=True, help="Path to the input directory containing raw files.")
    parser.add_argument("--output", type=str, required=True, help="Path to the output JSONL file.")
    parser.add_argument("--mapping", type=str, default=None, help="Optional YAML file mapping native to coarse labels.")
    args = parser.parse_args()

    input_dir = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output)
    mapping_path = pathlib.Path(args.mapping) if args.mapping else None

    build_items(input_dir, output_path, mapping_path)


if __name__ == "__main__":
    main()