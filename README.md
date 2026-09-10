# RST E2E ICL Parsing

This repository centers on **end-to-end RST parsing from pre-segmented EDUs with in-context learning**. It sends complete TSV documents to an OpenAI-compatible Chat Completions endpoint, validates compact bracketed trees against a versioned annotation scheme, restores the original EDU text, and writes scheme-conformant `.rs3` files.

The older pairwise relation-labeling utilities are still present, but they are no longer the main path documented here.

## What The E2E Path Does

- Reads a header-bearing TSV and groups rows by `doc_id`.
- Sends `prompts/system_prompt.txt` as the system message.
- Sends one selected `ICL_*_e2e.txt` prompt as the user message.
- Injects the current document into the prompt's final empty fenced `tsv` block.
- Writes one JSONL record per document with source EDUs, model/decoding metadata, scheme and prompt hashes, raw tree text, response usage, and structured errors.
- Excludes prompt bodies and credentials from output.
- Rejects trees with missing, duplicate, reordered, or unknown content.
- Converts validated compact trees to RS3 with `src.convert_e2e_to_rs3`.

## Installation

Use Python 3.10 or later.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-e2e.lock
```

`requirements.txt` adds the dependencies for the legacy Hugging Face/pairwise
benchmark. `requirements-e2e.lock` is the resolved Python 3.12/Linux environment
used for verification. `requirements-e2e.txt` lists only direct compatible
dependencies and is the input to deliberate future lock refreshes.

## Input TSV

The e2e runner expects a UTF-8 TSV with a header row and no columns other than
the following:

Required columns:

- `doc_id`: groups fragments into a document.
- `text`: one EDU/span fragment per row.

Optional column:

- `index`: positive, canonical integer fragment index, unique within its document. If omitted, one-based indices are assigned within each document.

Example:

```tsv
doc_id	index	text
gum_news_1	1	The committee met on Tuesday.
gum_news_1	2	It approved the proposal.
gum_news_2	1	The company reported higher revenue.
```

Rows keep their input order and define textual EDU order. Blank `doc_id` or
`text`, malformed/duplicate indices, duplicate headers, and unexpected columns
are rejected before any API request. EDU text is preserved for RS3 output.

## Scheme And Prompt Selection

The supported starter profile is `configs/schemes/pcc.yaml`. A scheme profile
defines its exact relation inventory, each relation's `rst` or `multinuc` type,
its version, and its default prompt. E2E prompts live in `prompts/` and must be
named `ICL_*_e2e.txt`.

```text
prompts/ICL_pcc_algo_e2e.txt
```

Each e2e prompt must end with one empty TSV block:

````text
```tsv
```
````

The runner validates that shape and injects the current document there. Use
`--prompt` only to override the default prompt while retaining the same scheme
inventory. The selected prompt and scheme are hashed into every prediction.

## Run An E2E Experiment

Set an API key and provide the endpoint and model explicitly:

```bash
export OPENAI_API_KEY="..."

python -m src.run_e2e_icl \
  --input data/processed/documents.example.tsv \
  --scheme configs/schemes/pcc.yaml \
  --output results/predictions/pcc_e2e.jsonl \
  --model gpt-4.1-mini \
  --endpoint https://api.openai.com/v1
```

`--endpoint` is an OpenAI-compatible base URL, so local or hosted compatible servers can use the same command shape.
The endpoint must implement Chat Completions and accept `model`, `messages`,
`temperature`, and `max_tokens`. `OPENAI_API_KEY` is required by the runner;
use a non-secret placeholder only when a local endpoint genuinely ignores it.

Useful optional flags:

```text
--temperature 0.0
--max-tokens 4096
--timeout 120.0
--system-prompt prompts/system_prompt.txt
```

## JSONL Output

The runner creates a new output file containing one object per document. It
refuses to append to an existing file so separate runs cannot be mixed silently:

```json
{
  "record_version": 1,
  "doc_id": "gum_news_1",
  "prompt_name": "ICL_pcc_algo_e2e.txt",
  "model": "gpt-4.1-mini",
  "endpoint": "https://api.openai.com/v1",
  "scheme": {"name": "pcc", "version": "1", "sha256": "..."},
  "prompt_sha256": "...",
  "system_prompt_sha256": "...",
  "decoding": {"temperature": 0.0, "max_tokens": 4096},
  "edus": [
    {"index": "1", "text": "The committee met on Tuesday."},
    {"index": "2", "text": "It approved the proposal."}
  ],
  "status": "ok",
  "raw_tree": "(NS-elaboration (text 1) (text 2))",
  "response": {
    "id": "response-id",
    "finish_reason": "stop",
    "usage": {
      "prompt_tokens": 100,
      "completion_tokens": 20,
      "total_tokens": 120
    }
  },
  "error": null
}
```

If one document fails, the record is written with `status: "error"`, `raw_tree: null`, `response: null`, and a structured `error`; later documents continue.
The runner returns a nonzero exit status if any API request fails.

## Convert Results To RS3

Convert successful JSONL records to one `.rs3` file per document:

```bash
python \
  -m src.convert_e2e_to_rs3 \
  --input results/predictions/pcc_e2e.jsonl \
  --scheme configs/schemes/pcc.yaml \
  --output-dir results/rs3/pcc_e2e
```

The converter writes:

```text
results/rs3/pcc_e2e/<doc_id>.rs3
results/rs3/pcc_e2e/conversion_report.jsonl
```

`doc_id` values are sanitized before becoming filenames. API-error records are
skipped. Scheme mismatches, malformed trees, invalid relations/nuclearity,
non-exact EDU coverage, existing output files, and filename collisions are
reported without stopping later records. Use `--overwrite` deliberately to
replace existing RS3 files and `--report` to choose a different report path.

Before writing, index leaves are replaced with the recorded source EDU text.
The deterministic writer emits only the selected scheme inventory, and the
converter verifies the final segment text, order, and header before publication.
It returns a nonzero exit status if any input record is skipped or fails.

## Adapt The Scheme

For a project-specific PCC-like scheme:

1. Copy `configs/schemes/pcc.yaml` and give it a new name and version.
2. Retain only your exact relation identifiers and mark each `rst` or `multinuc`.
3. Copy `prompts/ICL_pcc_algo_e2e.txt`; update its definitions, decisions,
   allowed-label list, and examples; reference it from the new YAML.
4. Add a prompt/profile consistency test and validate a small adjudicated pilot
   set before scaling up.

Relation identifiers cannot contain spaces; use a stable slug such as
`causal-result`. See `docs/inference-contract.md` for design rationale,
invariants, provenance, and versioning rules.

## Test

Run from the repository root:

```bash
python -m unittest discover -s tests -v
```

RS3 serialization uses the standard library and is exercised on every test run;
it does not depend on a colleague-specific environment or external converter.

## Optional Tree Evaluation

`requirements.txt` includes RST-Tace for comparing RS3 trees.

Parse and inspect one generated file as an interoperability check:

```bash
rsttace analyse results/rs3/pcc_e2e/doc_001.rs3 -o results/rsttace/
```

Compare two files:

```bash
rsttace compare \
  results/rs3/gold/doc_001.rs3 \
  results/rs3/pcc_e2e/doc_001.rs3 \
  -o results/rsttace/
```

Compare matching directories:

```bash
rsttace compare \
  results/rs3/gold/ \
  results/rs3/pcc_e2e/ \
  -o results/rsttace/
```

## Data

Add local experiment inputs under `data/raw/` or `data/processed/`.
