# E2E inference contract

## Purpose and current scope

The supported path parses relatively short documents whose EDU segmentation is
already fixed. It targets one explicit relation scheme at a time. Automatic EDU
segmentation, universal conversion among RST frameworks, and automatic repair
of malformed model trees are deliberately out of scope.

## Why the pipeline is scheme-driven

Prompt text alone is not an enforceable schema. Each project therefore has a
versioned YAML profile in `configs/schemes/` containing:

- a stable scheme name and version;
- the default e2e prompt filename;
- every exact compact-tree/RS3 relation identifier;
- whether each relation is mononuclear (`rst`) or multinuclear (`multinuc`).

The profile bytes are hashed into every prediction. Conversion requires the
same name, version, and hash, preventing an output generated under one inventory
from being silently converted under another.

## Input contract

Input is UTF-8 TSV with exactly `doc_id`, `text`, and optionally `index`.
Provided indices must be unique positive canonical integers. If omitted, they
are assigned from 1 within each document. Row order is textual EDU order, and
EDU text is preserved for final RS3 serialization.

Unexpected columns are currently rejected. If a future project needs document
or EDU metadata, extend the input contract explicitly and test how that metadata
is represented in prompts and outputs.

## Model-output contract

The model returns one parenthesized tree. Leaves are `(text INDEX)`. Relation
nodes are `NN-RELATION`, `NS-RELATION`, or `SN-RELATION`; spaces are not allowed
inside relation identifiers. `NN` nodes have at least two children, and `NS` or
`SN` nodes have exactly two.

Every source index must appear exactly once and in source order. This both
preserves the document and ensures each tree constituent covers a contiguous
source span. Relations and nuclearity are checked against the selected scheme.

Validation intentionally rejects instead of guessing. A rejected prediction is
retained in JSONL and described in the conversion report, so it can be inspected
or regenerated without corrupting the source record.

## RS3 conversion

Only after validation are index leaves replaced with the original EDU strings.
The repository's small deterministic RS3 writer serializes the validated tree,
then its output is checked to ensure segment text/order and relation inventory
exactly match the source and scheme. This avoids unrelated upstream defaults,
casing variants, and an obsolete converter packaging dependency. Files are
written through a temporary path and existing RS3 files are preserved unless
`--overwrite` is explicitly requested.

## Reproducibility record

Each prediction contains:

- an explicit prediction-record format version;
- source `doc_id` and ordered `edus`;
- endpoint and model identifier;
- requested decoding parameters and returned usage/finish metadata;
- scheme name, version, and SHA-256;
- ICL prompt and system-prompt SHA-256 values;
- raw model text, finish reason, usage, and structured errors.

The prompt bodies are intentionally not duplicated in prediction files. Keep
the repository revision together with results so the hashes can be resolved to
the exact tracked prompt files.

The supported environment is resolved in `requirements-e2e.lock` with its
Python/platform context recorded at the top. `requirements-e2e.txt` is the
human-maintained list used when intentionally refreshing that lock.

## Adapting the starter profile

1. Copy `configs/schemes/pcc.yaml` to a project-specific filename.
2. Give it a new `name`, reset its `version`, and list only the desired exact
   relation identifiers and types.
3. Copy the referenced e2e prompt and update its definitions, decision rules,
   allowed-label line, and examples.
4. Run the tests. The scheme/prompt inventory test should be generalized for
   the new profile rather than bypassed.
5. Create a small adjudicated pilot set and inspect rejected predictions before
   scaling inference.

Changing annotation semantics, relation membership, relation type, or compact
identifier requires a scheme version change. Wording-only prompt experiments
retain their own prompt hash even if the scheme version is unchanged.

## Verification baseline

On 2026-09-10 the network-free suite completed 40 tests under CPython 3.12,
including a full fake-completion -> JSONL -> RS3 path. A nested generated RS3
tree was also parsed successfully by RST-Tace at the revision pinned in
`requirements.txt`; its analysis recovered the expected `elaboration` and
`joint` relations. This is a serialization/interoperability check, not evidence
of model annotation quality, which still requires a project-specific gold pilot.
