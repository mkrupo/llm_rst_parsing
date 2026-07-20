"""Convert successful e2e compact-tree predictions to RS3 files."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

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


def convert_results(
    input_path: pathlib.Path,
    output_dir: pathlib.Path,
    report_path: Optional[pathlib.Path] = None,
) -> ConversionSummary:
    """Convert every successful JSONL tree and write a per-record report."""
    try:
        from nltk import Tree
        from rstconverter.rs3 import write_compact_rs3
    except ImportError as exc:
        raise RuntimeError(
            "RS3 conversion requires nltk and rstconverter; use the configured rstenv"
        ) from exc

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
                    tree = Tree.fromstring(strip_tree_fence(raw_tree))
                    write_compact_rs3(tree, str(output_path))
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
        "--report",
        help="Conversion report JSONL (default: OUTPUT_DIR/conversion_report.jsonl)",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    summary = convert_results(
        pathlib.Path(args.input),
        pathlib.Path(args.output_dir),
        pathlib.Path(args.report) if args.report else None,
    )
    print(
        f"generated={summary.generated} skipped={summary.skipped} failed={summary.failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
