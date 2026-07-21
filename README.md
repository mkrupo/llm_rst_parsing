# RST E2E ICL Parsing

This repository now centers on **end-to-end RST parsing with in-context learning**. It sends complete TSV documents to an OpenAI-compatible Chat Completions endpoint, asks for a compact bracketed discourse tree, stores prompt-free JSONL results, and converts successful trees to `.rs3` for downstream inspection or scoring.

The older pairwise relation-labeling utilities are still present, but they are no longer the main path documented here.

## What The E2E Path Does

- Reads a header-bearing TSV and groups rows by `doc_id`.
- Sends `prompts/system_prompt.txt` as the system message.
- Sends one selected `ICL_*_e2e.txt` prompt as the user message.
- Injects the current document into the prompt's final empty fenced `tsv` block.
- Writes one JSONL record per document with model metadata, status, raw tree text, response usage, and structured errors.
- Excludes prompt bodies and credentials from output.
- Converts successful compact trees to RS3 with `src.convert_e2e_to_rs3`.

## Installation

Use Python 3.10 or later.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Input TSV

The e2e runner expects a TSV with a header row.

Required columns:

- `doc_id`: groups fragments into a document.
- `text`: one EDU/span fragment per row.

Optional column:

- `index`: fragment index. If omitted, one-based indices are assigned within each document.

Example:

```tsv
doc_id	index	text
gum_news_1	1	The committee met on Tuesday.
gum_news_1	2	It approved the proposal.
gum_news_2	1	The company reported higher revenue.
```

Rows keep their input order. Blank `doc_id` or `text` values are rejected before any API request.

## Prompt Selection

E2E prompts live in `prompts/` and must be named `ICL_*_e2e.txt`. Current e2e options include:

```text
prompts/ICL_pcc_as_written_e2e.txt
prompts/ICL_pcc_algo_e2e.txt
prompts/ICL_rstweb_as_written_e2e.txt
prompts/ICL_rstweb_algo_e2e.txt
```

Each e2e prompt must end with one empty TSV block:

````text
```tsv
```
````

The runner validates that shape and injects the current document there.

## Run An E2E Experiment

Set an API key and provide the endpoint and model explicitly:

```bash
export OPENAI_API_KEY="..."

python -m src.run_e2e_icl \
  --input data/processed/documents.tsv \
  --prompt ICL_rstweb_algo_e2e.txt \
  --output results/predictions/rstweb_e2e.jsonl \
  --model gpt-4.1-mini \
  --endpoint https://api.openai.com/v1
```

`--endpoint` is an OpenAI-compatible base URL, so local or hosted compatible servers can use the same command shape.

Useful optional flags:

```text
--temperature 0.0
--max-tokens 4096
--timeout 120.0
--system-prompt prompts/system_prompt.txt
```

## JSONL Output

The runner appends one object per document:

```json
{
  "doc_id": "gum_news_1",
  "prompt_name": "ICL_rstweb_algo_e2e.txt",
  "model": "gpt-4.1-mini",
  "endpoint": "https://api.openai.com/v1",
  "status": "ok",
  "raw_tree": "(NS-Elaboration (text 1) (text 2))",
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

## Convert Results To RS3

Convert successful JSONL records to one `.rs3` file per document:

```bash
python \
  -m src.convert_e2e_to_rs3 \
  --input results/predictions/rstweb_e2e.jsonl \
  --output-dir results/rs3/rstweb_e2e
```

The converter writes:

```text
results/rs3/rstweb_e2e/<doc_id>.rs3
results/rs3/rstweb_e2e/conversion_report.jsonl
```

`doc_id` values are sanitized before becoming filenames. API-error records are skipped. Malformed trees and filename collisions are reported without overwriting previous outputs. Use `--report` to choose a different report path.

## Optional Tree Evaluation

`requirements.txt` includes RST-Tace for comparing RS3 trees.

Compare two files:

```bash
rsttace compare \
  results/rs3/gold/doc_001.rs3 \
  results/rs3/rstweb_e2e/doc_001.rs3 \
  -o results/rsttace/
```

Compare matching directories:

```bash
rsttace compare \
  results/rs3/gold/ \
  results/rs3/rstweb_e2e/ \
  -o results/rsttace/
```

## Data

Add local experiment inputs under `data/raw/` or `data/processed/`.
