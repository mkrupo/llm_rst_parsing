# OpenAI E2E ICL Parsing and RSTWeb Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run document-level RST ICL parsing through an adjustable OpenAI-compatible endpoint, add RSTWeb prompt counterparts, and convert result trees to RS3.

**Architecture:** A dedicated runner owns TSV validation, prompt composition, Chat Completions calls, and prompt-free JSONL persistence without changing the existing Hugging Face runner. A separate converter consumes successful JSONL records and delegates compact-tree serialization to `rstconverter`; prompt assets remain plain text and mirror the PCC family.

**Tech Stack:** Python 3.10+, standard library (`argparse`, `csv`, `json`, `pathlib`), `openai`, `nltk`, `rstconverter`, `unittest`.

## Global Constraints

- Work on branch `feat/openai-e2e-icl-rstweb`.
- Every request sends `prompts/system_prompt.txt` as the system message and one selected `ICL_*.txt` prompt as the user message.
- `--model` and `--endpoint` are required CLI options.
- Output JSONL includes `prompt_name` but excludes all prompt bodies and credentials.
- Input is header-bearing TSV grouped by `doc_id` with stable row order.
- Converter verification uses `/home/daniiligantev/miniconda3/envs/rstenv/bin/python`.
- Existing untracked PCC prompt files are user-owned inputs and must not be rewritten incidentally.

---

### Task 1: E2E TSV and Prompt Composition Core

**Files:**
- Create: `src/run_e2e_icl.py`
- Create: `tests/test_run_e2e_icl.py`

**Interfaces:**
- Produces: `Document(doc_id: str, header: tuple[str, ...], rows: tuple[tuple[str, ...], ...])`
- Produces: `read_tsv_documents(path: pathlib.Path) -> list[Document]`
- Produces: `resolve_prompt(path_or_name: str, prompt_dir: pathlib.Path) -> pathlib.Path`
- Produces: `inject_tsv(prompt: str, document: Document) -> str`
- Produces: `build_messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]`

- [ ] **Step 1: Write failing TSV grouping tests**

Create `tests/test_run_e2e_icl.py` with temporary TSV fixtures asserting that `read_tsv_documents()` groups interleaved-safe contiguous rows by first-seen `doc_id`, preserves row order, rejects an empty file, rejects missing `doc_id`, rejects missing `text`, and rejects blank IDs/text. Use this canonical fixture:

```text
doc_id\tindex\ttext
d1\t1\tFirst.
d1\t2\tSecond.
d2\t1\tOther.
```

Assert that the two returned IDs are `d1`, `d2`, and that each prompt-facing header is `("index", "text")`, because `doc_id` identifies the request rather than a discourse fragment field.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_run_e2e_icl -v`

Expected: import failure for missing `src.run_e2e_icl`.

- [ ] **Step 3: Implement TSV validation minimally**

In `src/run_e2e_icl.py`, add a frozen `Document` dataclass and parse with `csv.DictReader(..., delimiter="\t")`. Require `doc_id` and `text`, remove only `doc_id` from the prompt-facing header, synthesize an `index` column before `text` when absent, assign one-based indices per document, reject blank values, and preserve first-seen document and row order.

- [ ] **Step 4: Run grouping tests and verify GREEN**

Run: `python -m unittest tests.test_run_e2e_icl -v`

Expected: grouping/validation tests pass.

- [ ] **Step 5: Write failing prompt composition tests**

Add tests asserting:

```python
messages = build_messages("SYSTEM SECRET", "USER BODY")
self.assertEqual(messages, [
    {"role": "system", "content": "SYSTEM SECRET"},
    {"role": "user", "content": "USER BODY"},
])
```

Assert that `inject_tsv("intro\n```tsv\n```\n", document)` produces exactly one terminal block containing `index\ttext` and rows, rejects no placeholder, rejects a non-terminal placeholder, and rejects multiple empty TSV placeholders. Assert `resolve_prompt()` accepts a path or a filename under `prompts/` only when its basename matches `ICL_*.txt`.

- [ ] **Step 6: Run prompt tests and verify RED**

Run: `python -m unittest tests.test_run_e2e_icl -v`

Expected: failures for missing prompt helpers.

- [ ] **Step 7: Implement prompt resolution and composition**

Implement exact matching with a terminal-placeholder regular expression equivalent to `r"```tsv\s*\n```\s*$"`; serialize document headers and rows with `csv.writer` using tab delimiters and `lineterminator="\n"`; replace the one valid placeholder; and return the exact two-message list above.

- [ ] **Step 8: Run focused tests and commit**

Run: `python -m unittest tests.test_run_e2e_icl -v`

Expected: all Task 1 tests pass.

Commit:

```bash
git add src/run_e2e_icl.py tests/test_run_e2e_icl.py
git commit -m "feat: compose e2e ICL parsing requests"
```

### Task 2: OpenAI-Compatible Runner and JSONL Contract

**Files:**
- Modify: `src/run_e2e_icl.py`
- Modify: `tests/test_run_e2e_icl.py`

**Interfaces:**
- Consumes: `Document`, `inject_tsv()`, `build_messages()` from Task 1
- Produces: `OpenAIChatClient(endpoint: str, api_key: str, timeout: float)`
- Produces: `OpenAIChatClient.complete(*, model: str, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> CompletionResult`
- Produces: `run_experiment(...) -> None`
- Produces: `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write failing adapter tests**

Define fake nested client objects matching `client.chat.completions.create`. Test that `complete()` passes `model`, `messages`, `temperature`, and `max_tokens`; normalize content, response ID, finish reason, and `prompt_tokens`/`completion_tokens`/`total_tokens` into a frozen `CompletionResult`. Test that empty response choices raise a descriptive `RuntimeError`.

- [ ] **Step 2: Run adapter tests and verify RED**

Run: `python -m unittest tests.test_run_e2e_icl -v`

Expected: failures for missing `OpenAIChatClient` and `CompletionResult`.

- [ ] **Step 3: Implement the adapter**

Import `OpenAI` lazily inside `OpenAIChatClient.__init__` and instantiate it as `OpenAI(api_key=api_key, base_url=endpoint, timeout=timeout)`. Keep exception handling out of `complete()` so `run_experiment()` owns per-document error records. Normalize optional usage fields with `getattr` and never retain client request objects.

- [ ] **Step 4: Run adapter tests and verify GREEN**

Run: `python -m unittest tests.test_run_e2e_icl -v`

Expected: adapter tests pass.

- [ ] **Step 5: Write failing experiment/output tests**

Use a fake completion client that succeeds for `d1`, raises `RuntimeError("server unavailable")` for `d2`, and succeeds for `d3`. Assert three lines are written and flushed, with these stable keys:

```python
{
    "doc_id": "d1",
    "prompt_name": "ICL_rstweb_algo_e2e.txt",
    "model": "test-model",
    "endpoint": "http://localhost:8000/v1",
    "status": "ok",
    "raw_tree": "(NN-Joint (text 1) (text 2))",
    "response": {"id": "r1", "finish_reason": "stop", "usage": {...}},
    "error": None,
}
```

For `d2`, assert `raw_tree` and `response` are null and `error` is `{"type": "RuntimeError", "message": "server unavailable"}`. Assert serialized output contains neither a sentinel system prompt nor a sentinel ICL prompt. Test missing `OPENAI_API_KEY` before client construction.

- [ ] **Step 6: Run experiment tests and verify RED**

Run: `python -m unittest tests.test_run_e2e_icl -v`

Expected: failures for missing experiment orchestration.

- [ ] **Step 7: Implement orchestration and CLI**

Add CLI arguments `--input`, `--prompt`, `--output`, `--model`, `--endpoint`, `--temperature` (default `0.0`), `--max-tokens` (default `4096`), `--timeout` (default `120.0`), and `--system-prompt` (default `prompts/system_prompt.txt`). Validate all input and prompt files plus `OPENAI_API_KEY` before opening output. Create parent directories, append one UTF-8 JSON record per document with `ensure_ascii=False`, flush each line, continue after `Exception`, and return zero after all attempted documents.

- [ ] **Step 8: Verify runner behavior and commit**

Run: `python -m unittest tests.test_run_e2e_icl -v`

Expected: all runner tests pass.

Commit:

```bash
git add src/run_e2e_icl.py tests/test_run_e2e_icl.py
git commit -m "feat: run e2e parsing through OpenAI-compatible APIs"
```

### Task 3: RSTWeb ICL Prompt Family

**Files:**
- Create: `prompts/ICL_rstweb_as_written.txt`
- Create: `prompts/ICL_rstweb_as_written_e2e.txt`
- Create: `prompts/ICL_rstweb_algo.txt`
- Create: `prompts/ICL_rstweb_algo_e2e.txt`
- Create: `tests/test_rstweb_icl_prompts.py`

**Interfaces:**
- Consumes: RSTWeb definitions in `prompts/rstweb_as_written.md` and structural conventions in the four PCC counterparts
- Produces: four selectable `ICL_*.txt` assets with terminal TSV input blocks

- [ ] **Step 1: Write failing structural prompt tests**

Test that all four files exist and are nonempty. For e2e prompts assert the first paragraph asks for a bracketed discourse tree, a `bracketed tree example:` section exists, and the file ends with exactly ` ```tsv\n``` `. For pairwise prompts assert the task asks to assign rhetorical relations and ends with a populated PCC-style schema header `doc_id\tunit1\tunit2\tdirection`. Extract relation tokens from tree labels and uppercase `assign` statements and assert they are within the RSTWeb inventory: `Antithesis`, `Background`, `Circumstance`, `Concession`, `Condition`, `Contrast`, `Elaboration`, `Enablement`, `Evaluation`, `Evidence`, `Interpretation`, `Justify`, `Motivation`, `Non-volitional Cause`, `Non-volitional Result`, `Otherwise`, `Purpose`, `Restatement`, `Solutionhood`, `Summary`, `Volitional Cause`, `Volitional Result`, `Joint`, `List`, `Sequence`, plus `Preparation`. Explicitly reject `Conjunction`, `E-Elaboration`, `Reason-N`, and `Unless`.

- [ ] **Step 2: Run prompt tests and verify RED**

Run: `python -m unittest tests.test_rstweb_icl_prompts -v`

Expected: failures because all four RSTWeb ICL files are absent.

- [ ] **Step 3: Compose the as-written pairwise prompt**

Follow `ICL_pcc_as_written.txt` section order and formatting exactly. Populate it from `rstweb_as_written.md`, keeping all native RSTWeb headings, definition bullets, effects, typical connectives, examples, remarks, nuclearity distinctions, and the PCC-style populated pairwise demonstration TSV.

- [ ] **Step 4: Compose the as-written e2e prompt**

Follow `ICL_pcc_as_written_e2e.2.txt` formatting. Convert examples to compact `(NS|SN|NN-Relation ...)` notation, use indexed `(text N)` leaves in the task example, request one tree only, and finish with one empty fenced TSV block.

- [ ] **Step 5: Compose algorithm pairwise and e2e prompts**

Follow the fenced pseudocode sequence in the PCC algorithm counterparts: nuclearity precheck; multinuclear `Sequence`/`Contrast`/`List`/`Joint`; pragmatic relations; hypothetical relations; volitional and non-volitional cause/result direction; semantic detail; textual organization; fallback. Ensure every branch maps to an RSTWeb label and the pairwise/e2e versions differ only in task framing, example, and final TSV contents.

- [ ] **Step 6: Run structural tests and inspect diffs**

Run: `python -m unittest tests.test_rstweb_icl_prompts -v`

Expected: all prompt tests pass.

Run: `git diff --no-index prompts/ICL_pcc_algo_e2e.txt prompts/ICL_rstweb_algo_e2e.txt || true`

Expected: layout remains recognizably parallel; differences reflect inventories and definitions.

- [ ] **Step 7: Commit prompt assets**

```bash
git add prompts/ICL_rstweb_as_written.txt prompts/ICL_rstweb_as_written_e2e.txt prompts/ICL_rstweb_algo.txt prompts/ICL_rstweb_algo_e2e.txt tests/test_rstweb_icl_prompts.py
git commit -m "feat: add RSTWeb ICL parsing prompts"
```

### Task 4: JSONL-to-RS3 Conversion Utility

**Files:**
- Create: `src/convert_e2e_to_rs3.py`
- Create: `tests/test_convert_e2e_to_rs3.py`

**Interfaces:**
- Produces: `strip_tree_fence(raw_tree: str) -> str`
- Produces: `safe_doc_filename(doc_id: str) -> str`
- Produces: `convert_results(input_path: pathlib.Path, output_dir: pathlib.Path, report_path: pathlib.Path | None = None) -> ConversionSummary`
- Produces: `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write failing pure-function tests**

Assert plain trees are unchanged after outer whitespace trimming; ` ```\n(tree)\n``` ` and ` ```text\n(tree)\n``` ` lose only the surrounding fence; prose plus a tree is not modified. Assert `safe_doc_filename("gum/news 1") == "gum_news_1"`, traversal strings cannot escape the output directory, and whitespace/punctuation-only IDs raise `ValueError`.

- [ ] **Step 2: Run utility tests and verify RED**

Run: `/home/daniiligantev/miniconda3/envs/rstenv/bin/python -m unittest tests.test_convert_e2e_to_rs3 -v`

Expected: import failure for missing converter module.

- [ ] **Step 3: Implement pure helpers**

Use an anchored Markdown-fence regex and replace each run outside `[A-Za-z0-9._-]` with `_`; strip leading/trailing dots and underscores; reject an empty result. Do not use input IDs as paths before sanitization.

- [ ] **Step 4: Write failing end-to-end conversion tests**

Create JSONL records for: one successful plain tree, one fenced successful tree, one `status: error`, one malformed tree, and two IDs colliding after sanitization. Assert successful records create `.rs3` files containing `<rst>`, unsuccessful records do not create files, collision never overwrites, and every input line gets a report entry with `generated`, `skipped`, or `failed` status.

- [ ] **Step 5: Run conversion tests and verify RED**

Run: `/home/daniiligantev/miniconda3/envs/rstenv/bin/python -m unittest tests.test_convert_e2e_to_rs3 -v`

Expected: failures for missing conversion orchestration.

- [ ] **Step 6: Implement conversion and CLI**

Import `Tree` from `nltk` and `write_compact_rs3` from `rstconverter.rs3`. Parse successful `raw_tree` values with `Tree.fromstring`, reserve sanitized names before writing, call `write_compact_rs3(tree, str(output_path))`, default the report to `<output-dir>/conversion_report.jsonl`, and continue on per-record parsing/writer errors. Refuse a report path equal to a generated `.rs3` path. Return a frozen `ConversionSummary(generated: int, skipped: int, failed: int)` and make the CLI return nonzero only for input-wide configuration/read failures.

- [ ] **Step 7: Run converter tests and commit**

Run: `/home/daniiligantev/miniconda3/envs/rstenv/bin/python -m unittest tests.test_convert_e2e_to_rs3 -v`

Expected: all converter tests pass and real RS3 files are generated.

Commit:

```bash
git add src/convert_e2e_to_rs3.py tests/test_convert_e2e_to_rs3.py
git commit -m "feat: convert e2e parse results to RS3"
```

### Task 5: Documentation, Dependencies, and Full Verification

**Files:**
- Modify: `README.md`
- Create: `requirements.txt`
- Modify: `tests/test_run_e2e_icl.py`

**Interfaces:**
- Consumes: CLIs from Tasks 2 and 4
- Produces: reproducible install/run/convert instructions

- [ ] **Step 1: Write a failing CLI help smoke test**

Add subprocess tests verifying `python -m src.run_e2e_icl --help` documents `--endpoint`, `--model`, `--prompt`, and `OPENAI_API_KEY`, and the `rstenv` interpreter invocation of `python -m src.convert_e2e_to_rs3 --help` documents `--input`, `--output-dir`, and `--report`.

- [ ] **Step 2: Run smoke tests and verify RED if help is incomplete**

Run: `python -m unittest tests.test_run_e2e_icl -v`

Expected: failure naming any missing help contract.

- [ ] **Step 3: Complete CLI help and dependency declaration**

Add `requirements.txt` with the repository's README-listed runtime packages plus `openai`; document `nltk` and `rstconverter` as converter requirements without attempting an install during implementation. Ensure parser descriptions state that output excludes prompts.

- [ ] **Step 4: Document exact workflows**

Add README examples:

```bash
export OPENAI_API_KEY="..."
python -m src.run_e2e_icl \
  --input data/processed/documents.tsv \
  --prompt ICL_rstweb_algo_e2e.txt \
  --output results/predictions/rstweb_e2e.jsonl \
  --model gpt-4.1-mini \
  --endpoint https://api.openai.com/v1

/home/daniiligantev/miniconda3/envs/rstenv/bin/python \
  -m src.convert_e2e_to_rs3 \
  --input results/predictions/rstweb_e2e.jsonl \
  --output-dir results/rs3/rstweb_e2e
```

Document TSV columns `doc_id`, optional `index`, and `text`; JSONL fields; per-document continuation; prompt-name/no-prompt-body behavior; and conversion reports.

- [ ] **Step 5: Run all verification commands**

Run:

```bash
python -m unittest discover -s tests -v
/home/daniiligantev/miniconda3/envs/rstenv/bin/python -m unittest discover -s tests -v
python -m src.run_e2e_icl --help
/home/daniiligantev/miniconda3/envs/rstenv/bin/python -m src.convert_e2e_to_rs3 --help
git diff --check
git status --short
```

Expected: both test-suite runs pass, both CLIs print help and exit zero, no whitespace errors, and status contains only intentional task changes plus the user's pre-existing untracked files.

- [ ] **Step 6: Commit documentation and dependency metadata**

```bash
git add README.md requirements.txt tests/test_run_e2e_icl.py
git commit -m "docs: explain e2e ICL and RS3 workflows"
```

- [ ] **Step 7: Review branch scope**

Run: `git log --oneline refactor..HEAD` and `git diff --stat refactor...HEAD`.

Expected: the design commit and focused implementation commits only; no pre-existing PCC prompt or system-prompt file is accidentally added unless intentionally required by the runner and explicitly reviewed.
