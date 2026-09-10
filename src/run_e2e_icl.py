"""Run end-to-end RST parsing with ICL prompts and an OpenAI-compatible API."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import pathlib
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .schemes import Scheme, load_scheme


_ROOT = pathlib.Path(__file__).resolve().parent.parent


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


@dataclass(frozen=True)
class CompletionResult:
    """Normalized fields from one Chat Completions response."""

    content: str
    response_id: Optional[str]
    finish_reason: Optional[str]
    usage: Dict[str, Optional[int]]


@dataclass(frozen=True)
class ExperimentSummary:
    """Counts of API-level document outcomes."""

    succeeded: int
    failed: int


class OpenAIChatClient:
    """Small adapter for an OpenAI-compatible Chat Completions endpoint."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        timeout: float,
        *,
        client: Optional[Any] = None,
    ) -> None:
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "the openai package is required; install it before running experiments"
                ) from exc
            client = OpenAI(api_key=api_key, base_url=endpoint, timeout=timeout)
        self._client = client

    def complete(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> CompletionResult:
        """Send a chat completion and normalize the first returned choice."""
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not getattr(response, "choices", None):
            raise RuntimeError("Chat Completions response contained no choices")
        choice = response.choices[0]
        content = getattr(getattr(choice, "message", None), "content", None)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Chat Completions response contained no assistant text")
        usage = getattr(response, "usage", None)
        usage_fields = {
            name: getattr(usage, name, None) if usage is not None else None
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
        return CompletionResult(
            content=content,
            response_id=getattr(response, "id", None),
            finish_reason=getattr(choice, "finish_reason", None),
            usage=usage_fields,
        )


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
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("TSV input contains duplicate column names")
        unexpected = set(reader.fieldnames) - {"doc_id", "index", "text"}
        if unexpected:
            raise ValueError(f"TSV input contains unsupported columns: {sorted(unexpected)}")

        has_index = "index" in reader.fieldnames
        output_header = ("index", "text")
        grouped: Dict[str, List[Tuple[str, ...]]] = OrderedDict()
        seen_indices: Dict[str, set[str]] = {}

        for line_number, row in enumerate(reader, start=2):
            doc_id = (row.get("doc_id") or "").strip()
            text = row.get("text") or ""
            if not doc_id:
                raise ValueError(f"blank doc_id on TSV line {line_number}")
            if not text.strip():
                raise ValueError(f"blank text on TSV line {line_number}")

            document_rows = grouped.setdefault(doc_id, [])
            index = (
                (row.get("index") or "").strip()
                if has_index
                else str(len(document_rows) + 1)
            )
            if not re.fullmatch(r"[1-9][0-9]*", index):
                raise ValueError(
                    f"index must be a positive canonical integer on TSV line {line_number}"
                )
            document_indices = seen_indices.setdefault(doc_id, set())
            if index in document_indices:
                raise ValueError(
                    f"duplicate index {index!r} for document {doc_id!r} "
                    f"on TSV line {line_number}"
                )
            document_indices.add(index)
            document_rows.append((index, text))

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
    if not re.fullmatch(r"ICL_.+_e2e\.txt", path.name):
        raise ValueError("prompt filename must match ICL_*_e2e.txt")
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


def run_experiment(
    *,
    documents: List[Document],
    system_prompt: str,
    icl_prompt: str,
    prompt_name: str,
    output_path: pathlib.Path,
    client: Any,
    model: str,
    endpoint: str,
    temperature: float,
    max_tokens: int,
    scheme: Scheme,
) -> ExperimentSummary:
    """Run each document independently and persist one prompt-free JSON record."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_sha256 = hashlib.sha256(icl_prompt.encode("utf-8")).hexdigest()
    system_prompt_sha256 = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
    counts = {"succeeded": 0, "failed": 0}
    with output_path.open("x", encoding="utf-8") as output:
        for document in documents:
            messages = build_messages(system_prompt, inject_tsv(icl_prompt, document))
            base_record: Dict[str, Any] = {
                "record_version": 1,
                "doc_id": document.doc_id,
                "prompt_name": prompt_name,
                "model": model,
                "endpoint": endpoint,
                "scheme": scheme.metadata(),
                "prompt_sha256": prompt_sha256,
                "system_prompt_sha256": system_prompt_sha256,
                "decoding": {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                "edus": [
                    {"index": index, "text": text}
                    for index, text in document.rows
                ],
            }
            try:
                result = client.complete(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if result.finish_reason not in (None, "stop"):
                    raise RuntimeError(
                        f"completion did not finish normally: {result.finish_reason}"
                    )
                record = {
                    **base_record,
                    "status": "ok",
                    "raw_tree": result.content,
                    "response": {
                        "id": result.response_id,
                        "finish_reason": result.finish_reason,
                        "usage": result.usage,
                    },
                    "error": None,
                }
                counts["succeeded"] += 1
            except Exception as exc:
                record = {
                    **base_record,
                    "status": "error",
                    "raw_tree": None,
                    "response": None,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
                counts["failed"] += 1
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
    return ExperimentSummary(**counts)


def build_parser() -> argparse.ArgumentParser:
    """Create the e2e experiment argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Run e2e RST ICL parsing through OpenAI-compatible Chat Completions; "
            "JSONL output includes prompt_name but excludes prompt bodies. "
            "Set OPENAI_API_KEY for authentication."
        )
    )
    parser.add_argument("--input", required=True, help="Header-bearing document TSV")
    parser.add_argument(
        "--scheme",
        required=True,
        help="Versioned YAML relation inventory and default prompt",
    )
    parser.add_argument(
        "--prompt",
        help="Optional ICL_*_e2e.txt override (default: prompt from --scheme)",
    )
    parser.add_argument("--output", required=True, help="Destination JSONL path")
    parser.add_argument("--model", required=True, help="API model identifier")
    parser.add_argument("--endpoint", required=True, help="OpenAI-compatible base URL")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--system-prompt",
        default=str(_ROOT / "prompts" / "system_prompt.txt"),
        help="System prompt path (default: prompts/system_prompt.txt)",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")

    input_path = pathlib.Path(args.input)
    scheme = load_scheme(pathlib.Path(args.scheme))
    prompt_path = resolve_prompt(args.prompt or scheme.prompt, _ROOT / "prompts")
    system_path = pathlib.Path(args.system_prompt)
    documents = read_tsv_documents(input_path)
    icl_prompt = prompt_path.read_text(encoding="utf-8")
    system_prompt = system_path.read_text(encoding="utf-8")
    if not system_prompt.strip():
        raise ValueError(f"system prompt is empty: {system_path}")
    # Validate prompt shape before creating the API client or opening output.
    inject_tsv(icl_prompt, documents[0])

    client = OpenAIChatClient(args.endpoint, api_key, args.timeout)
    summary = run_experiment(
        documents=documents,
        system_prompt=system_prompt,
        icl_prompt=icl_prompt,
        prompt_name=prompt_path.name,
        output_path=pathlib.Path(args.output),
        client=client,
        model=args.model,
        endpoint=args.endpoint,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        scheme=scheme,
    )
    print(f"succeeded={summary.succeeded} failed={summary.failed}")
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
