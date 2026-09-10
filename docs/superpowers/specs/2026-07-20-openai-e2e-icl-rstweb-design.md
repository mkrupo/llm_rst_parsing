# OpenAI E2E ICL Parsing and RSTWeb Prompts Design

> Historical design record (2026-07-20). It describes the original prototype,
> including the retired `rstconverter` path. The maintained contract is
> `docs/inference-contract.md`; `AGENTS.md` defines current repository rules.

## Goal

Add reproducible end-to-end RST parsing experiments that send TSV documents to an OpenAI-compatible Chat Completions endpoint, use the repository system prompt with a selected ICL prompt, store prompt-free JSONL results, provide RSTWeb prompt counterparts in the PCC formatting style, and convert successful bracketed trees to RS3 for verification.

## Scope

The change introduces a dedicated e2e experiment path. It does not alter the existing pairwise Hugging Face annotation workflow or generalize the repository into a multi-provider framework.

Deliverables are:

- a dedicated OpenAI-compatible e2e ICL runner;
- four RSTWeb ICL prompt files matching the PCC counterparts;
- a separate JSONL-to-RS3 conversion utility;
- automated tests and README usage documentation.

## E2E Runner

### Command-line interface

The runner will live at `src/run_e2e_icl.py` and expose these required options:

- `--input`: input TSV path;
- `--prompt`: selected `ICL_*.txt` prompt path or prompt filename resolved under `prompts/`;
- `--output`: destination JSONL path;
- `--model`: model identifier sent to the API;
- `--endpoint`: OpenAI-compatible base URL.

Optional decoding and transport options will include temperature, maximum output tokens, and request timeout. Authentication will come from `OPENAI_API_KEY`; it will never be written to output or logs. The endpoint is a base URL accepted by an OpenAI-compatible client, which invokes Chat Completions.

### TSV contract

The input is a header-bearing TSV. It must contain `doc_id` and a text-fragment column. The accepted canonical fragment column is `text`; an existing numeric fragment index is retained when supplied, otherwise indices are assigned within each document in row order. Rows are grouped by `doc_id`, preserving their input order and the original header when serialized into the prompt. Empty files, missing required fields, blank document identifiers, and documents without fragments are validation errors reported before any API request.

### Prompt composition

Every request has exactly two chat messages:

1. `prompts/system_prompt.txt` is sent as the system message.
2. The selected `ICL_*.txt` content, with the grouped document TSV inserted into its terminal empty fenced `tsv` block, is sent as the user message.

The runner validates that the selected file is named `ICL_*.txt` and contains exactly one terminal empty TSV placeholder suitable for injection. It does not concatenate the system prompt into the user message. Prompt contents are never persisted in results.

### API and continuation behavior

The API layer is a small, independently testable adapter around the official `openai` Python package configured with the supplied base URL and API key. A successful response yields the first assistant message content. A failure for one document is recorded and processing continues with later documents, allowing long experiments to retain partial results. Input-wide validation and missing credentials fail before output processing begins.

### JSONL output contract

The runner appends one record per document. Each record contains:

- `doc_id`;
- `prompt_name`, using the selected prompt filename;
- `model`;
- `endpoint`;
- `status`, either `ok` or `error`;
- `raw_tree` for successful assistant content, otherwise `null`;
- response metadata available from the server, such as response ID, finish reason, and token usage;
- a structured error object for failed requests, otherwise `null`.

Neither the system prompt nor ICL prompt body is included. The API key is never included. Records are flushed after writing so completed documents survive later failures.

## RSTWeb Prompt Assets

Add these prompt files:

- `prompts/ICL_rstweb_as_written.txt`;
- `prompts/ICL_rstweb_as_written_e2e.txt`;
- `prompts/ICL_rstweb_algo.txt`;
- `prompts/ICL_rstweb_algo_e2e.txt`.

They mirror the corresponding PCC file rather than inventing a third layout:

- pairwise files retain the PCC pairwise task wording and TSV schema;
- e2e files retain the PCC tree-building wording, bracketed-tree notation, and terminal empty fenced TSV block;
- `as_written` files use the native definitions, distinction notes, and examples from `rstweb_as_written.md`, formatted with the same heading and bullet conventions used by their PCC counterparts;
- `algo` files use the PCC staged decision/pseudocode organization, adapted to the RSTWeb inventory;
- RSTWeb-only inventory and nuclearity rules are preserved;
- PCC-only labels such as `Conjunction` and `E-Elaboration` are not introduced into RSTWeb prompts;
- all relation names exactly match the repository's RSTWeb native mapping.

The prompt bodies instruct the model to return only the requested relation annotations or a single compact bracketed tree, depending on the variant.

## RS3 Conversion Utility

The utility will live at `src/convert_e2e_to_rs3.py` and expose:

- `--input`: an e2e result JSONL file;
- `--output-dir`: directory for generated RS3 files;
- an optional `--report` path, defaulting to a conversion-report JSONL inside the output directory.

For each `status: ok` record, it will:

1. read `raw_tree`;
2. remove only a surrounding Markdown code fence, when present;
3. parse the compact tree with `nltk.Tree.fromstring`;
4. call `rstconverter.rs3.write_compact_rs3(tree, output_path)`;
5. write a report record describing the generated file.

The output filename is a filesystem-safe form of `doc_id` followed by `.rs3`. Sanitization cannot produce an empty name. Two document IDs that resolve to the same sanitized filename are conversion errors; the utility never overwrites an earlier output. API-error records, missing trees, malformed JSONL records, invalid NLTK trees, and RS3 writer errors are recorded as skipped or failed report entries while later records continue.

Verification of this utility and its integration uses `/home/daniiligantev/miniconda3/envs/rstenv/bin/python`, where the required `nltk` and `rstconverter` packages are installed.

## Internal Boundaries

The implementation keeps responsibilities separate:

- TSV reading/grouping and prompt injection are pure functions in the e2e runner module;
- the API adapter accepts already composed messages and returns a normalized response object;
- JSONL record creation is independent of API-client objects;
- RS3 cleanup, filename sanitization, and single-record conversion are testable without invoking the experiment runner.

This boundary permits network-free unit tests and leaves the pairwise benchmark untouched.

## Error Handling

Configuration and input errors produce a non-zero exit before API calls. Per-document API and conversion errors are represented in machine-readable records and do not stop remaining documents. Error messages include document and operation context but exclude prompt bodies, credentials, and opaque client internals that may contain sensitive request data.

## Testing and Verification

Tests are written before implementation and cover:

- TSV grouping, assigned indices, and stable row order;
- rejection of malformed or empty TSV input;
- exact two-message system/user composition;
- safe injection into the terminal fenced TSV placeholder;
- model and endpoint CLI propagation;
- normalized success and API-error JSONL records;
- inclusion of `prompt_name` and exclusion of both prompt bodies;
- continuation after a per-document request failure;
- parsing plain and Markdown-fenced compact trees;
- safe RS3 filenames and collision rejection;
- skip/failure reporting for unsuccessful and malformed records;
- generation of a real `.rs3` file through the installed converter;
- structural checks that each new RSTWeb prompt follows its PCC counterpart and uses only valid RSTWeb labels.

Network behavior is tested with a fake client. Final verification runs the normal repository test suite and converter-specific tests with `/home/daniiligantev/miniconda3/envs/rstenv/bin/python`.

## Documentation

The README will show complete commands for running a TSV experiment with adjustable endpoint/model and converting its JSONL output to RS3. It will document `OPENAI_API_KEY`, the TSV fields, the JSONL output contract, prompt selection, the required Python environment for conversion, and the fact that prompt bodies are intentionally excluded from results.
