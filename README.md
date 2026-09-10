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

Use Python 3.10 or later. The verified setup uses Python 3.12 and `uv`:

```bash
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python requirements-e2e.lock
source .venv/bin/activate
```

If `uv` is unavailable, the equivalent standard-library/pip setup is:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-e2e.lock
```

`.venv/` is ignored by Git. Activate it in every new shell before using the
commands below; no API credential is stored in the environment directory.

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

### Prepare TSV from existing RS3

If source documents are already `.rs3`, export their segment layer directly:

```bash
python -m src.rs3_to_e2e_tsv \
  --input /path/to/gold-rs3/ \
  --output data/processed/project_documents.tsv
```

The input may be one file or a directory. Add `--recursive` for nested
directories. The command writes the inference TSV plus, by default:

```text
data/processed/project_documents.tsv.manifest.jsonl
```

RS3 segment elements are read in XML body order and assigned fresh sequential
indices. Their text is preserved exactly. The manifest maps each new index to
its original RS3 node ID and records source/text hashes. This matters because
RS3 node IDs are graph identifiers and are not reliably consecutive textual
positions.

The exporter verifies its TSV through the inference reader before publishing
it and refuses existing outputs unless `--overwrite` is supplied. The TSV
contains no gold tree or relation labels; retain the original `.rs3` files for
evaluation. Consequently, this preprocessing step is lossless for the EDU
layer but intentionally not a structural RS3 round-trip.

## Scheme And Prompt Selection

The repository includes a general PCC starter and the project-specific English
ArgMicrotexts profile. The latter reproduces the released 34-relation header
without `sameunit`, matching inputs whose segmentation does not split
interrupted EDUs.

```text
configs/schemes/pcc.yaml
configs/schemes/argmicrotexts.yaml
prompts/ICL_argmicrotexts_algo_e2e.txt
```

A scheme profile defines its exact relation inventory, each relation's `rst`
or `multinuc` type, its version, and its default prompt. E2E prompts live in
`prompts/` and must be named `ICL_*_e2e.txt`.

Each e2e prompt must end with one empty TSV block:

````text
```tsv
```
````

The runner validates that shape and injects the current document there. Use
`--prompt` only to override the default prompt while retaining the same scheme
inventory. The selected prompt and scheme are hashed into every prediction.

## Run An E2E Experiment

For a copy-ready walkthrough of the first ArgMicrotexts request, see
[`docs/argmicrotexts-smoke-test.md`](docs/argmicrotexts-smoke-test.md).

Enter an API key without echoing it or placing it in shell history. The
variable is available only to this shell and its child processes; close the
shell or run `unset OPENAI_API_KEY` when finished.

```bash
read -rsp "OpenAI API key: " OPENAI_API_KEY
export OPENAI_API_KEY
printf '\n'
```

Prepare a one-document smoke-test TSV:

```bash
python -m src.rs3_to_e2e_tsv \
  --input data/input/microtexts_nosameunit_subset/micro_b001_original.rs3 \
  --output data/processed/argmicrotexts_smoke.tsv
```

Then run the recommended initial OpenAI experiment:

```bash
python -m src.run_e2e_icl \
  --input data/processed/argmicrotexts_smoke.tsv \
  --scheme configs/schemes/argmicrotexts.yaml \
  --output results/predictions/argmicrotexts_terra_medium_smoke.jsonl \
  --model gpt-5.6-terra \
  --endpoint https://api.openai.com/v1 \
  --reasoning-effort medium \
  --max-completion-tokens 8192
```

`--endpoint` is an OpenAI-compatible base URL, so local or hosted compatible
servers can use the same command shape. The endpoint must implement Chat
Completions and accept `model` and `messages`. Modern OpenAI requests use
`max_completion_tokens`; pass `--max-tokens` instead for an older compatible
server that implements only that legacy parameter. `--reasoning-effort` and
`--temperature` are omitted unless explicitly supplied, which avoids sending
unsupported options to other providers. `OPENAI_API_KEY` remains required by
the runner; use a non-secret placeholder only when a local endpoint genuinely
ignores it.

Useful optional flags:

```text
--reasoning-effort medium
--temperature 0.0
--max-completion-tokens 8192
--max-tokens 4096              # legacy alternative; mutually exclusive
--timeout 300.0
--max-retries 2
--system-prompt prompts/system_prompt.txt
```

## JSONL Output

The runner creates a new output file containing one object per document. It
refuses to append to an existing file so separate runs cannot be mixed silently:

```json
{
  "record_version": 2,
  "doc_id": "micro_b001_original",
  "prompt_name": "ICL_argmicrotexts_algo_e2e.txt",
  "model": "gpt-5.6-terra",
  "endpoint": "https://api.openai.com/v1",
  "scheme": {"name": "argmicrotexts-en-nosameunit", "version": "1", "sha256": "..."},
  "prompt_sha256": "...",
  "system_prompt_sha256": "...",
  "decoding": {
    "temperature": null,
    "reasoning_effort": "medium",
    "max_completion_tokens": 8192,
    "max_tokens": null
  },
  "transport": {"timeout_seconds": 300.0, "max_retries": 2},
  "edus": [
    {"index": "1", "text": "The committee met on Tuesday."},
    {"index": "2", "text": "It approved the proposal."}
  ],
  "status": "ok",
  "raw_tree": "(NS-elaboration (text 1) (text 2))",
  "response": {
    "id": "response-id",
    "model": "returned-model-id",
    "system_fingerprint": "provider-fingerprint",
    "created": 1789056000,
    "service_tier": "default",
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
python -m src.convert_e2e_to_rs3 \
  --input results/predictions/argmicrotexts_terra_medium_smoke.jsonl \
  --scheme configs/schemes/argmicrotexts.yaml \
  --output-dir results/rs3/argmicrotexts_terra_medium_smoke
```

The converter writes:

```text
results/rs3/argmicrotexts_terra_medium_smoke/<doc_id>.rs3
results/rs3/argmicrotexts_terra_medium_smoke/conversion_report.jsonl
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

The evidence audit and unresolved decisions for the current ArgMicrotexts
adaptation are recorded in `docs/argmicrotexts-project-profile.md`.

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

Evaluator compatibility must be checked on the chosen gold corpus before a
full run. In particular, RST-Tace rejects original ArgMicrotexts trees that
attach multiple mononuclear satellites directly to one nucleus. Such trees
need a documented normalization or a different evaluator; do not silently
rewrite gold files merely to satisfy a scoring tool.

## Data

Add local experiment inputs under `data/raw/` or `data/processed/`.
