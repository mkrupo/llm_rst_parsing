"""Export RS3 segment layers to the TSV consumed by e2e inference."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .run_e2e_icl import read_tsv_documents


@dataclass(frozen=True)
class SourceSegment:
    """One source RS3 segment and its prompt-facing sequential index."""

    index: str
    source_id: str
    text: str


@dataclass(frozen=True)
class SourceDocument:
    """The losslessly extracted segment layer of one RS3 document."""

    doc_id: str
    source_path: str
    source_sha256: str
    segments: Tuple[SourceSegment, ...]


@dataclass(frozen=True)
class ExportSummary:
    """Counts for a completed and verified RS3-to-TSV export."""

    documents: int
    segments: int


def discover_rs3_files(input_path: pathlib.Path, *, recursive: bool) -> List[pathlib.Path]:
    """Return a stable list of source RS3 files."""
    if input_path.is_file():
        if input_path.suffix.lower() != ".rs3":
            raise ValueError(f"input file must have an .rs3 suffix: {input_path}")
        return [input_path]
    if not input_path.is_dir():
        raise FileNotFoundError(f"input path does not exist: {input_path}")

    candidates = input_path.rglob("*.rs3") if recursive else input_path.glob("*.rs3")
    files = sorted(
        (path for path in candidates if path.is_file() and not path.name.startswith(".")),
        key=lambda path: path.relative_to(input_path).as_posix(),
    )
    if not files:
        scope = "recursively " if recursive else ""
        raise ValueError(f"no .rs3 files found {scope}under {input_path}")
    return files


def _source_label(path: pathlib.Path, input_path: pathlib.Path) -> str:
    if input_path.is_dir():
        return path.relative_to(input_path).as_posix()
    return path.name


def read_rs3_segments(path: pathlib.Path, *, source_path: str) -> SourceDocument:
    """Extract direct body segments in XML order without changing their text."""
    try:
        raw_bytes = path.read_bytes()
        root = ET.fromstring(raw_bytes)
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f"cannot parse RS3 XML {path}: {exc}") from exc

    if root.tag != "rst":
        raise ValueError(f"RS3 root must be <rst> in {path}, got <{root.tag}>")
    body = root.find("body")
    if body is None:
        raise ValueError(f"RS3 document has no <body>: {path}")

    node_ids = set()
    segment_elements = []
    for element in body:
        if element.tag not in {"segment", "group"}:
            raise ValueError(f"unsupported <{element.tag}> element in RS3 body: {path}")
        node_id = element.get("id")
        if not node_id:
            raise ValueError(f"RS3 body node has no id in {path}")
        if node_id in node_ids:
            raise ValueError(f"duplicate RS3 body node id {node_id!r} in {path}")
        node_ids.add(node_id)
        if element.tag == "segment":
            segment_elements.append(element)

    if not segment_elements:
        raise ValueError(f"RS3 document contains no segments: {path}")

    segments = []
    for position, element in enumerate(segment_elements, start=1):
        source_id = element.get("id")
        if list(element):
            raise ValueError(
                f"RS3 segment {source_id!r} contains unsupported nested XML in {path}"
            )
        text = element.text or ""
        if not text.strip():
            raise ValueError(f"RS3 segment {source_id!r} has blank text in {path}")
        segments.append(SourceSegment(str(position), source_id, text))

    return SourceDocument(
        doc_id=path.stem,
        source_path=source_path,
        source_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        segments=tuple(segments),
    )


def load_source_documents(
    input_path: pathlib.Path,
    *,
    recursive: bool = False,
) -> List[SourceDocument]:
    """Discover and extract RS3 documents while rejecting ambiguous IDs."""
    files = discover_rs3_files(input_path, recursive=recursive)
    documents = [
        read_rs3_segments(path, source_path=_source_label(path, input_path))
        for path in files
    ]
    seen = {}
    for document in documents:
        normalized = document.doc_id.casefold()
        if normalized in seen:
            raise ValueError(
                "duplicate document ID derived from RS3 filenames: "
                f"{seen[normalized]!r} and {document.source_path!r} both map to "
                f"{document.doc_id!r}"
            )
        seen[normalized] = document.source_path
    return documents


def _manifest_record(document: SourceDocument) -> dict:
    return {
        "record_version": 1,
        "doc_id": document.doc_id,
        "source_path": document.source_path,
        "source_sha256": document.source_sha256,
        "segment_count": len(document.segments),
        "segments": [
            {
                "index": segment.index,
                "source_id": segment.source_id,
                "text_sha256": hashlib.sha256(segment.text.encode("utf-8")).hexdigest(),
            }
            for segment in document.segments
        ],
    }


def verify_tsv_export(path: pathlib.Path, expected: Sequence[SourceDocument]) -> None:
    """Re-read an exported TSV through the inference reader and compare exactly."""
    actual = read_tsv_documents(path)
    if len(actual) != len(expected):
        raise ValueError(
            f"TSV verification found {len(actual)} documents, expected {len(expected)}"
        )
    for actual_document, expected_document in zip(actual, expected):
        expected_rows = tuple(
            (segment.index, segment.text) for segment in expected_document.segments
        )
        if actual_document.doc_id != expected_document.doc_id:
            raise ValueError(
                "TSV verification changed document order/IDs: "
                f"{actual_document.doc_id!r} != {expected_document.doc_id!r}"
            )
        if actual_document.rows != expected_rows:
            raise ValueError(
                f"TSV verification changed indices or text for {expected_document.doc_id!r}"
            )


def export_rs3_to_tsv(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    manifest_path: Optional[pathlib.Path] = None,
    *,
    recursive: bool = False,
    overwrite: bool = False,
) -> ExportSummary:
    """Export and verify the segment layer of one file or directory of RS3."""
    manifest_path = manifest_path or output_path.with_suffix(output_path.suffix + ".manifest.jsonl")
    if output_path.resolve() == manifest_path.resolve():
        raise ValueError("TSV output and manifest paths must differ")
    existing = [path for path in (output_path, manifest_path) if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "output already exists (use --overwrite): "
            + ", ".join(str(path) for path in existing)
        )

    documents = load_source_documents(input_path, recursive=recursive)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    tsv_handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
        delete=False,
    )
    manifest_handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{manifest_path.name}.",
        suffix=".tmp",
        dir=manifest_path.parent,
        delete=False,
    )
    tsv_temp = pathlib.Path(tsv_handle.name)
    manifest_temp = pathlib.Path(manifest_handle.name)
    try:
        with tsv_handle, manifest_handle:
            writer = csv.writer(tsv_handle, delimiter="\t", lineterminator="\n")
            writer.writerow(("doc_id", "index", "text"))
            for document in documents:
                for segment in document.segments:
                    writer.writerow((document.doc_id, segment.index, segment.text))
                manifest_handle.write(
                    json.dumps(_manifest_record(document), ensure_ascii=False) + "\n"
                )
        verify_tsv_export(tsv_temp, documents)
        os.replace(tsv_temp, output_path)
        os.replace(manifest_temp, manifest_path)
    finally:
        tsv_temp.unlink(missing_ok=True)
        manifest_temp.unlink(missing_ok=True)

    return ExportSummary(
        documents=len(documents),
        segments=sum(len(document.segments) for document in documents),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export RS3 segments, in XML body order and with exact text, to the "
            "doc_id/index/text TSV consumed by e2e inference."
        )
    )
    parser.add_argument("--input", required=True, help="Source .rs3 file or directory")
    parser.add_argument("--output", required=True, help="Destination inference TSV")
    parser.add_argument(
        "--manifest",
        help="Source-ID/provenance JSONL (default: OUTPUT.manifest.jsonl)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Discover .rs3 files recursively below an input directory",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing TSV and/or manifest",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    summary = export_rs3_to_tsv(
        pathlib.Path(args.input),
        pathlib.Path(args.output),
        pathlib.Path(args.manifest) if args.manifest else None,
        recursive=args.recursive,
        overwrite=args.overwrite,
    )
    print(f"documents={summary.documents} segments={summary.segments}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
