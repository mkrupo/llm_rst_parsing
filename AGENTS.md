# Repository working agreement

These instructions apply to the whole repository.

## Primary workflow

The supported inference path is pre-segmented TSV -> OpenAI-compatible Chat
Completions -> validated compact tree -> RS3. The older pairwise benchmark is
legacy code and must not silently define e2e behavior.

## Sources of truth

- `configs/schemes/*.yaml` defines an exact, versioned relation inventory and
  the `rst`/`multinuc` type of every relation.
- The scheme's referenced `prompts/ICL_*_e2e.txt` defines annotation semantics
  and the model-facing compact-tree contract.
- `prompts/system_prompt.txt` must remain task-only and must not request prose,
  personas, hidden rubrics, or Markdown.
- Prediction records must retain source EDUs plus scheme and prompt hashes.

## Invariants

- Input indices are unique positive canonical integers within each document.
- A successful tree uses every input index exactly once and in input order.
- Model output never supplies final RS3 segment text; conversion hydrates the
  validated indices from the recorded source EDUs.
- Relations are case-sensitive and must occur in the selected scheme.
- `NN` is valid only for `multinuc`; `NS` and `SN` are valid only for `rst`.
- Validation fails closed. Do not silently repair, reorder, relabel, or discard
  model output.
- Generated files under `results/` are evidence, not gold data. Do not edit
  them to make a failing prediction appear valid.
- Dependency changes update `requirements-e2e.txt` and, after a clean install
  and full test run, the resolved `requirements-e2e.lock`.

## Required verification

Run the network-free suite from the repository root:

```bash
python -m unittest discover -s tests -v
```

The RS3 integration test uses only the standard library plus the scheme loader
and must run in the normal suite. For contract changes, add a focused regression
test before or with the change.

## Adapting to a new project

Copy a scheme YAML and its prompt under new names. Change relation definitions
and examples in the prompt, and change exact labels/types in the YAML. Do not
add project-specific `if` statements to the generic runner or converter.
Document intentional contract changes in `docs/inference-contract.md`.
