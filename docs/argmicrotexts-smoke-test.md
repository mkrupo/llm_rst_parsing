# ArgMicrotexts inference smoke test

Run these commands from a Bash terminal. The local `.venv` has already been
created; the setup commands are included so the procedure remains reproducible.

## 1. Enter the repository and activate the environment

```bash
cd /home/max/projects-wsl/rststandards
source .venv/bin/activate
```

To recreate the environment later, use:

```bash
cd /home/max/projects-wsl/rststandards
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python requirements-e2e.lock
source .venv/bin/activate
```

## 2. Add the API key temporarily

The first command waits for the key without displaying it. Paste the key,
press Enter, and then run the remaining commands. The key is available only to
this shell and programs launched from it. Do not put the key in this repository
or paste it into experiment logs.

```bash
read -rsp "OpenAI API key: " OPENAI_API_KEY
export OPENAI_API_KEY
printf '\n'
```

## 3. Prepare one document

This extracts only the ordered EDU text from the gold RS3 file. It does not put
gold relations or tree structure into the model input.

```bash
python -m src.rs3_to_e2e_tsv \
  --input data/input/microtexts_nosameunit_subset/micro_b001_original.rs3 \
  --output data/processed/argmicrotexts_smoke.tsv
```

The exporter refuses to replace an existing TSV. If this filename already
exists from an earlier attempt, choose a new output filename and use the same
new filename in the inference command below.

## 4. Run one inference request

This uses the English 34-relation ArgMicrotexts profile, medium reasoning, and
the OpenAI Chat Completions endpoint.

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

The expected terminal summary is:

```text
succeeded=1 failed=0
```

The runner deliberately refuses to append to an existing JSONL file. Give a
retry a new output filename so separate attempts cannot be mixed silently.

## 5. Convert the prediction to RS3

Run this only after inference reports one successful document:

```bash
python -m src.convert_e2e_to_rs3 \
  --input results/predictions/argmicrotexts_terra_medium_smoke.jsonl \
  --scheme configs/schemes/argmicrotexts.yaml \
  --output-dir results/rs3/argmicrotexts_terra_medium_smoke
```

The predicted document and conversion report will be written under:

```text
results/rs3/argmicrotexts_terra_medium_smoke/
```

## 6. Remove the key from the shell

```bash
unset OPENAI_API_KEY
```

Closing the terminal also removes this temporary shell variable. Never paste
the key into an issue, chat message, committed file, or result artifact.

