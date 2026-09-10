"""Convert successful e2e compact-tree predictions to RS3 files."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .compact_tree import parse_compact_tree, validate_compact_tree
from .rs3_writer import write_rs3
from .schemes import Scheme, load_scheme

_OUTER_FENCE = re.compile(
    r"\A```(?:text)?[ \t]*\n(?P<body>.*)\n```[ \t]*\Z",
    re.DOTALL | re.IGNORECASE,
)
_FENCED_BLOCK = re.compile(
    r"```(?:text)?[ \t]*\n(?P<body>.*?)\n```", re.DOTALL | re.IGNORECASE
)
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ConversionSummary:
    """Counts of conversion outcomes."""

    generated: int
    skipped: int
    failed: int


def strip_tree_fence(raw_tree: str) -> str:
    """Extract a compact tree from bare, fenced, or analysis-wrapped output."""
    stripped = raw_tree.strip()
    match = _OUTER_FENCE.fullmatch(stripped)
    if match:
        return match.group("body").strip()
    fenced_blocks = list(_FENCED_BLOCK.finditer(stripped))
    if fenced_blocks:
        return fenced_blocks[-1].group("body").strip()
    return stripped


def safe_doc_filename(doc_id: str) -> str:
    """Turn a document identifier into one safe filename stem."""
    stem = _UNSAFE_FILENAME.sub("_", doc_id.strip()).strip("._")
    if not stem:
        raise ValueError("doc_id does not contain a usable filename")
    return stem


def _error(exc: Exception) -> Dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def _record_edus(record: Mapping[str, Any]) -> Tuple[List[str], Dict[str, str]]:
    edus = record.get("edus")
    if not isinstance(edus, list) or not edus:
        raise ValueError("successful record must contain a nonempty edus list")
    indices: List[str] = []
    texts: Dict[str, str] = {}
    for position, edu in enumerate(edus, start=1):
        if not isinstance(edu, dict):
            raise ValueError(f"EDU {position} must be an object")
        index = edu.get("index")
        text = edu.get("text")
        if not isinstance(index, str) or not re.fullmatch(r"[1-9][0-9]*", index):
            raise ValueError(f"EDU {position} has an invalid index")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"EDU {position} has invalid text")
        if index in texts:
            raise ValueError(f"duplicate EDU index in result record: {index}")
        indices.append(index)
        texts[index] = text
    return indices, texts


def _validate_scheme_provenance(record: Mapping[str, Any], scheme: Scheme) -> None:
    if record.get("record_version") != 1:
        raise ValueError(
            f"unsupported prediction record version: {record.get('record_version')!r}"
        )
    metadata = record.get("scheme")
    if not isinstance(metadata, dict):
        raise ValueError("successful record is missing scheme provenance")
    for key, expected in scheme.metadata().items():
        if metadata.get(key) != expected:
            raise ValueError(
                f"prediction scheme {key} does not match converter scheme: "
                f"{metadata.get(key)!r} != {expected!r}"
            )


def _validate_rs3(
    path: pathlib.Path,
    scheme: Scheme,
    expected_texts: List[str],
) -> None:
    xml_tree = ET.parse(path)
    root = xml_tree.getroot()
    relations_element = root.find("./header/relations")
    if relations_element is None:
        raise ValueError("generated RS3 has no relation inventory")
    actual_relations = {
        element.attrib.get("name"): element.attrib.get("type")
        for element in relations_element.findall("rel")
    }
    if actual_relations != dict(scheme.relations):
        raise ValueError("generated RS3 relation inventory differs from the scheme")

    actual_texts = [segment.text or "" for segment in root.findall("./body/segment")]
    if actual_texts != expected_texts:
        raise ValueError(
            "generated RS3 segment text/order differs from the source EDUs: "
            f"expected={expected_texts!r}, actual={actual_texts!r}"
        )


def convert_results(
    input_path: pathlib.Path,
    output_dir: pathlib.Path,
    scheme: Scheme,
    report_path: Optional[pathlib.Path] = None,
    *,
    overwrite: bool = False,
) -> ConversionSummary:
    """Convert every successful JSONL tree and write a per-record report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_path or output_dir / "conversion_report.jsonl"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    reserved = set()
    counts = {"generated": 0, "skipped": 0, "failed": 0}

    with input_path.open("r", encoding="utf-8") as source, report_path.open(
        "w", encoding="utf-8"
    ) as report:
        for line_number, line in enumerate(source, start=1):
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("JSONL record must be an object")
            except Exception as exc:
                outcome = {
                    "line": line_number,
                    "doc_id": None,
                    "status": "failed",
                    "output_file": None,
                    "error": _error(exc),
                }
                counts["failed"] += 1
                report.write(json.dumps(outcome, ensure_ascii=False) + "\n")
                continue

            doc_id = record.get("doc_id")
            if record.get("status") != "ok":
                outcome = {
                    "line": line_number,
                    "doc_id": doc_id,
                    "status": "skipped",
                    "output_file": None,
                    "error": record.get("error"),
                }
                counts["skipped"] += 1
            else:
                try:
                    if not isinstance(doc_id, str):
                        raise ValueError("successful record must contain a string doc_id")
                    raw_tree = record.get("raw_tree")
                    if not isinstance(raw_tree, str) or not raw_tree.strip():
                        raise ValueError("successful record must contain a nonempty raw_tree")
                    _validate_scheme_provenance(record, scheme)
                    edu_indices, edu_text = _record_edus(record)
                    stem = safe_doc_filename(doc_id)
                    normalized = stem.casefold()
                    if normalized in reserved:
                        raise ValueError(
                            f"sanitized filename collision for document {doc_id!r}: {stem}.rs3"
                        )
                    reserved.add(normalized)
                    output_path = output_dir / f"{stem}.rs3"
                    if output_path.resolve() == report_path.resolve():
                        raise ValueError("RS3 output path collides with conversion report")
                    if output_path.exists() and not overwrite:
                        raise FileExistsError(
                            f"RS3 output already exists (use --overwrite): {output_path}"
                        )

                    compact_tree = parse_compact_tree(strip_tree_fence(raw_tree))
                    validate_compact_tree(
                        compact_tree,
                        edu_indices,
                        scheme.relations,
                    )
                    temp_handle = tempfile.NamedTemporaryFile(
                        prefix=f".{stem}.",
                        suffix=".rs3.tmp",
                        dir=output_dir,
                        delete=False,
                    )
                    temp_path = pathlib.Path(temp_handle.name)
                    temp_handle.close()
                    try:
                        write_rs3(compact_tree, edu_text, scheme, temp_path)
                        _validate_rs3(
                            temp_path,
                            scheme,
                            [edu_text[index] for index in edu_indices],
                        )
                        os.replace(temp_path, output_path)
                    finally:
                        temp_path.unlink(missing_ok=True)
                    outcome = {
                        "line": line_number,
                        "doc_id": doc_id,
                        "status": "generated",
                        "output_file": str(output_path),
                        "error": None,
                    }
                    counts["generated"] += 1
                except Exception as exc:
                    outcome = {
                        "line": line_number,
                        "doc_id": doc_id,
                        "status": "failed",
                        "output_file": None,
                        "error": _error(exc),
                    }
                    counts["failed"] += 1
            report.write(json.dumps(outcome, ensure_ascii=False) + "\n")
            report.flush()

    return ConversionSummary(**counts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert successful e2e JSONL compact trees into XML-based RS3 files."
    )
    parser.add_argument("--input", required=True, help="E2E experiment JSONL")
    parser.add_argument("--output-dir", required=True, help="Directory for .rs3 files")
    parser.add_argument(
        "--scheme",
        required=True,
        help="Scheme YAML used for inference and RS3 validation",
    )
    parser.add_argument(
        "--report",
        help="Conversion report JSONL (default: OUTPUT_DIR/conversion_report.jsonl)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing per-document RS3 files",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    summary = convert_results(
        pathlib.Path(args.input),
        pathlib.Path(args.output_dir),
        load_scheme(pathlib.Path(args.scheme)),
        pathlib.Path(args.report) if args.report else None,
        overwrite=args.overwrite,
    )
    print(
        f"generated={summary.generated} skipped={summary.skipped} failed={summary.failed}"
    )
    return 1 if summary.skipped or summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
