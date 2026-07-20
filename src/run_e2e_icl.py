"""Run end-to-end RST parsing with ICL prompts and an OpenAI-compatible API."""

from __future__ import annotations

import csv
import io
import pathlib
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Tuple


_EMPTY_TSV_BLOCK = re.compile(r"```tsv[ \t]*\n[ \t]*```", re.IGNORECASE)
_TERMINAL_EMPTY_TSV_BLOCK = re.compile(
    r"```tsv[ \t]*\n[ \t]*```[ \t]*(?:\n)?\Z", re.IGNORECASE
)


@dataclass(frozen=True)
class Document:
    """One input document represented as prompt-facing TSV rows."""

    doc_id: str
    header: Tuple[str, ...]
    rows: Tuple[Tuple[str, ...], ...]


def read_tsv_documents(path: pathlib.Path) -> List[Document]:
    """Read and validate a header-bearing TSV grouped by ``doc_id``."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"TSV input is empty: {path}")
        if "doc_id" not in reader.fieldnames:
            raise ValueError("TSV input must contain a doc_id column")
        if "text" not in reader.fieldnames:
            raise ValueError("TSV input must contain a text column")

        source_header = tuple(name for name in reader.fieldnames if name != "doc_id")
        has_index = "index" in source_header
        output_header = source_header if has_index else ("index",) + source_header
        grouped: Dict[str, List[Tuple[str, ...]]] = OrderedDict()

        for line_number, row in enumerate(reader, start=2):
            doc_id = (row.get("doc_id") or "").strip()
            text = (row.get("text") or "").strip()
            if not doc_id:
                raise ValueError(f"blank doc_id on TSV line {line_number}")
            if not text:
                raise ValueError(f"blank text on TSV line {line_number}")

            document_rows = grouped.setdefault(doc_id, [])
            values = tuple((row.get(name) or "").strip() for name in source_header)
            if not has_index:
                values = (str(len(document_rows) + 1),) + values
            document_rows.append(values)

    if not grouped:
        raise ValueError(f"TSV input contains no document rows: {path}")

    return [
        Document(doc_id=doc_id, header=output_header, rows=tuple(rows))
        for doc_id, rows in grouped.items()
    ]


def resolve_prompt(path_or_name: str, prompt_dir: pathlib.Path) -> pathlib.Path:
    """Resolve an ICL prompt path directly or relative to ``prompt_dir``."""
    supplied = pathlib.Path(path_or_name)
    path = supplied if supplied.is_file() else prompt_dir / path_or_name
    if not re.fullmatch(r"ICL_.+\.txt", path.name):
        raise ValueError("prompt filename must match ICL_*.txt")
    if not path.is_file():
        raise FileNotFoundError(f"ICL prompt not found: {path}")
    return path


def inject_tsv(prompt: str, document: Document) -> str:
    """Insert a document into the prompt's single terminal empty TSV block."""
    placeholders = list(_EMPTY_TSV_BLOCK.finditer(prompt))
    if len(placeholders) > 1:
        raise ValueError("ICL prompt must contain exactly one empty TSV placeholder")
    terminal = _TERMINAL_EMPTY_TSV_BLOCK.search(prompt)
    if len(placeholders) != 1 or terminal is None:
        raise ValueError("ICL prompt must end with one terminal empty TSV placeholder")

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(document.header)
    writer.writerows(document.rows)
    replacement = f"```tsv\n{buffer.getvalue()}```\n"
    return prompt[: terminal.start()] + replacement


def build_messages(system_prompt: str, user_prompt: str) -> List[Dict[str, str]]:
    """Build the exact two-message chat request used for every experiment."""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
