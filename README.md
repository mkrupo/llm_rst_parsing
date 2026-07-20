# RST Prompt Adequacy Benchmark

This repository implements a lightweight benchmark for evaluating **Rhetorical Structure Theory (RST) annotation standards as LLM-facing specifications**. It focuses on relation labeling for already segmented EDU/span pairs rather than full discourse parsing. The implemented standards are **eRST**, **RST website/classical RST**, and **PCC**, each with both a native/as-written prompt formulation and a normalized prompt formulation.

## Repository status and plan match

The repository substantially matches the initial implementation plan at the scaffold level. It contains the requested directory layout, six prompt files, data-contract support, relation mappings, HuggingFace-based annotation running, output parsing, core metrics, confusion-matrix plotting, an optional Discursive-Circuits bridge, and optional activation-steering helper utilities for downstream generation experiments.

The main implementation is suitable as a starting point for the proposed paper experiments, but it is not yet a fully polished experimental package. Before running a final benchmark, review the caveats below.

### Matches the plan

- Implements a **relation-labeling benchmark**, not a full RST parser.
- Assumes **pre-segmented EDU/span pairs** with context.
- Provides six prompt conditions:
  - `erst_as_written`
  - `erst_normalized`
  - `rstweb_as_written`
  - `rstweb_normalized`
  - `pcc_as_written`
  - `pcc_normalized`
- Provides the planned JSON output schema:
  - `native_label`
  - `coarse_label`
  - `nuclearity`
  - `confidence`
  - `evidence`
  - `rejected_alternatives`
- Includes a coarse shared label space and native-to-coarse mappings.
- Includes scripts for:
  - building normalized JSONL items
  - building prompts
  - running LLM annotation
  - parsing model outputs
  - computing metrics
  - plotting confusion matrices
  - optionally bridging to Discursive-Circuits
  - optionally building activation-steering utilities

### Partial or missing pieces

- Few-shot balancing is expected by the design, but not automatically enforced.
- Metrics are implemented globally, but not yet fully broken down by every condition in the final deliverable format.
- `metrics.py` writes several useful CSVs, but does not yet write all planned per-condition summary files exactly as named in the plan.
- `build_items.py` reads JSONL-style records. It does not currently parse JSON arrays from `.json` files.
- The HuggingFace model runner is intentionally minimal. It may need `device_map`, dtype handling, authentication, chat templates, and batching for serious experiments.
- The dummy fallback makes dry-runs easy, but can also hide model-loading failures if logs are not inspected.
- Native validity currently counts non-null native labels, but a stricter invalid-label rate should count missing or malformed predictions as invalid.
- The optional activation-steering utilities are helper-level only. They do not yet include a complete downstream generation experiment script.
- The repository includes a `__pycache__` directory, which can be removed before publication.
- The `repos/` directory is intentionally empty. External repositories should be cloned there only when needed.

## Directory layout

```text
rst_prompt_adequacy/
  data/
    raw/
    processed/
    mappings/
  prompts/
    erst_as_written.md
    rstweb_as_written.md
    pcc_as_written.md
    erst_normalized.md
    rstweb_normalized.md
    pcc_normalized.md
  src/
    activation_optional/
      __init__.py
      activation_utils.py
      rst_dataset.py
    build_items.py
    prompt_templates.py
    run_llm_annotation.py
    parse_outputs.py
    metrics.py
    relation_mappings.py
    analyze_confusions.py
    optional_cudr_bridge.py
  configs/
    experiment.yaml
    models.yaml
  results/
    predictions/
    metrics/
    figures/
  repos/
```

## Data format

The core benchmark expects a JSONL file with one item per line. Each item should describe a pre-segmented relation instance.

```json
{
  "item_id": "gum_000001",
  "source": "GUM_eRST",
  "genre": "news",
  "doc_id": "GUM_news_x",
  "left": "The company announced the merger",
  "right": "because it wanted to expand into Asia",
  "context_before": "optional preceding text",
  "context_after": "optional following text",
  "gold_native": "causal-cause",
  "gold_standard": "eRST",
  "gold_coarse": "CAUSE_REASON",
  "nuclearity": "NS",
  "split": "test"
}
```

The repository includes a tiny demonstration file at:

```text
data/processed/relation_pairs.jsonl
```

For real experiments, replace this file with your own processed benchmark data.

## Coarse label space

The benchmark maps native relation labels into this shared coarse space:

```python
COARSE_LABELS = [
    "ATTRIBUTION",
    "BACKGROUND_CIRCUMSTANCE",
    "CAUSE_REASON",
    "RESULT",
    "CONDITION",
    "CONTRAST_CONCESSION",
    "ELABORATION",
    "EVALUATION_INTERPRETATION",
    "EVIDENCE_JUSTIFY",
    "PURPOSE_ENABLEMENT",
    "RESTATEMENT_SUMMARY",
    "TEMPORAL_SEQUENCE",
    "JOINT_LIST",
    "TEXTUAL_ORGANIZATION",
    "OTHER",
]
```

The YAML mapping used by the scripts is stored at:

```text
data/mappings/relation_map.yaml
```

You can regenerate it with:

```bash
python -m src.relation_mappings --output data/mappings/relation_map.yaml
```

If running from a parent directory as a package, use the package-qualified form instead:

```bash
python -m rst_prompt_adequacy.src.relation_mappings --output rst_prompt_adequacy/data/mappings/relation_map.yaml
```

## Installation

Create an environment with Python 3.10 or later.

```bash
conda create -n rst_prompt_adequacy python=3.10 -y
conda activate rst_prompt_adequacy
```

Install the core dependencies:

```bash
pip install torch transformers accelerate datasets pyyaml pandas numpy scipy scikit-learn krippendorff tqdm matplotlib
```

Optional steering and circuit experiments may require additional dependencies from the external repositories.

## Running the core benchmark

All commands below assume you are in the repository root.

### 1. Prepare data

If your raw files already follow the expected schema, place them under `data/raw/` and run:

```bash
python -m src.build_items \
  --input data/raw \
  --output data/processed/relation_pairs.jsonl \
  --mapping data/mappings/relation_map.yaml
```

The resulting file is the input to the LLM annotation runner.

### 2. Configure models

Edit:

```text
configs/experiment.yaml
```

The default model examples are:

```yaml
models:
  - name: local_model_a
    provider: hf
    model_id: meta-llama/Llama-3.2-3B-Instruct
  - name: local_model_b
    provider: hf
    model_id: Qwen/Qwen2.5-3B-Instruct
```

These models may require HuggingFace access or significant local resources. For locked or gated models, authenticate with HuggingFace before running.

### 3. Run annotation

```bash
python -m src.run_llm_annotation --config configs/experiment.yaml
```

Outputs are written to:

```text
results/predictions/
```

Each output file is a JSONL file containing raw model output and parsed JSON.

### 4. Parse model outputs

If you want to re-parse raw outputs or normalize outputs into a separate folder, run:

```bash
python -m src.parse_outputs \
  --input results/predictions \
  --output results/predictions_parsed
```

### 5. Compute metrics

```bash
python -m src.metrics \
  --input results/predictions_parsed \
  --mapping data/mappings/relation_map.yaml \
  --output results/metrics
```

If you did not run `parse_outputs.py`, you can point `--input` directly to `results/predictions` because the runner already stores a parsed field.

The metrics module currently writes:

```text
results/metrics/native_validity.csv
results/metrics/native_accuracy.csv
results/metrics/coarse_accuracy_macro_f1.csv
results/metrics/self_consistency.csv
results/metrics/cross_model_consistency.csv
results/metrics/distributional_alignment_jsd.csv
results/metrics/confusions/confusion_<standard>.json
```

### 6. Plot confusion matrices

```bash
python -m src.analyze_confusions \
  --input results/metrics/confusions \
  --output results/figures
```

This generates PDF confusion matrices such as:

```text
results/figures/confusion_erst.pdf
results/figures/confusion_rstweb.pdf
results/figures/confusion_pcc.pdf
```

## Prompt files

The prompt files live under `prompts/`.

The native/as-written prompts are intended to approximate the original annotation standard’s own style and terminology. The normalized prompts keep the same relation inventory but rewrite the instructions into a more comparable decision format across standards.

The runner constructs prompts by concatenating:

1. The selected prompt template.
2. Optional few-shot examples.
3. The current relation-labeling item.
4. A JSON-only output request.

The prompt assembly logic is in:

```text
src/prompt_templates.py
```

## Optional Discursive-Circuits bridge

The core experiments do not require Discursive-Circuits.

To use the optional bridge, clone the external repository into `repos/`:

```bash
git clone https://github.com/ruthenian8/Discursive-Circuits repos/Discursive-Circuits
```

Then follow that repository’s setup instructions for data and models.

The wrapper script is:

```text
src/optional_cudr_bridge.py
```

Example:

```bash
python -m src.optional_cudr_bridge \
  --repo repos/Discursive-Circuits \
  --relation causal-result_r \
  --source_relation Contingency.Cause.Result \
  --dataset_name RST \
  --dataset_name_source PDTB
```

This is intended only as an auxiliary relation-family bridge. It is not part of the core benchmark.

## End-to-end ICL parsing through an OpenAI-compatible API

The e2e runner parses complete documents into compact bracketed RST trees. It uses `prompts/system_prompt.txt` as the system message for every request and injects one document into the terminal TSV block of the selected `ICL_*_e2e.txt` user prompt.

Input must be a header-bearing TSV with these columns:

- `doc_id`: groups fragments into documents;
- `text`: fragment text;
- `index`: optional fragment index; one-based indices are assigned per document when omitted.

Rows retain their source order. For example:

```tsv
doc_id	index	text
gum_news_1	1	The committee met on Tuesday.
gum_news_1	2	It approved the proposal.
```

Install the dependencies from `requirements.txt`, set the API key, and choose the endpoint and model on the command line:

```bash
export OPENAI_API_KEY="..."
python -m src.run_e2e_icl \
  --input data/processed/documents.tsv \
  --prompt ICL_rstweb_algo_e2e.txt \
  --output results/predictions/rstweb_e2e.jsonl \
  --model gpt-4.1-mini \
  --endpoint https://api.openai.com/v1
```

`--endpoint` accepts an OpenAI-compatible base URL, so the same runner can target compatible local or hosted servers. Optional controls include `--temperature`, `--max-tokens`, and `--timeout`.

The output contains one JSON object per document with `doc_id`, `prompt_name`, `model`, `endpoint`, `status`, `raw_tree`, response metadata, and a structured error. Prompt bodies and credentials are deliberately excluded. A failed document is recorded and later documents continue.

### Convert e2e results to RS3

Convert every successful compact tree to a separate XML-based `.rs3` file with the environment containing `nltk` and `rstconverter`:

```bash
/home/daniiligantev/miniconda3/envs/rstenv/bin/python \
  -m src.convert_e2e_to_rs3 \
  --input results/predictions/rstweb_e2e.jsonl \
  --output-dir results/rs3/rstweb_e2e
```

The converter writes one sanitized `<doc_id>.rs3` per successful record and `conversion_report.jsonl` in the output directory. API errors are skipped; malformed trees, unsafe identifiers, and filename collisions are reported without overwriting an existing result. Use `--report` to select another report path.

## Optional activation steering utilities

The repository includes optional utilities for downstream generation experiments under:

```text
src/activation_optional/
```

These utilities are designed to test whether activation-level steering changes model behavior in coherence-sensitive generation tasks. They are not required for the annotation benchmark.

The utilities provide:

- `RSTPromptDataset`: wraps benchmark rows as prompt/label examples.
- `prepare_activation_capture`: registers hooks for activation capture.
- `compute_activation_stats`: captures last-token activations over a dataset.
- `build_steering_vectors`: builds contrastive vectors from positive and negative activation groups.
- `apply_activation_steering`: registers steering hooks for generation.

To use them, clone the external steering repository into `repos/`:

```bash
git clone https://github.com/ruthenian8/steering_content_effects repos/steering_content_effects
```

Then import the helpers:

```python
from src.activation_optional import (
    RSTPromptDataset,
    compute_activation_stats,
    build_steering_vectors,
    apply_activation_steering,
)
```

A minimal steering workflow is:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from src.activation_optional import RSTPromptDataset, compute_activation_stats, build_steering_vectors, apply_activation_steering
from src.prompt_templates import build_prompt

model_id = "Qwen/Qwen2.5-3B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")

module_names = ["model.layers.10", "model.layers.20"]

def prompt_builder(row):
    return build_prompt(item=row, standard="erst", formulation="normalized", fewshots=[])

positive_dataset = RSTPromptDataset(positive_rows, prompt_builder)
negative_dataset = RSTPromptDataset(negative_rows, prompt_builder)

pos_acts = compute_activation_stats(model, module_names, positive_dataset, tokenizer)
neg_acts = compute_activation_stats(model, module_names, negative_dataset, tokenizer)
steering_vectors = build_steering_vectors(pos_acts, neg_acts)
steering = apply_activation_steering(model, module_names, steering_vectors, c=1.0)

# Run generation here. Remove hooks afterwards.
steering.remove_hooks()
```

Recommended downstream generation tests include:

- coherent continuation with a target relation
- summarization with nucleus preservation
- argument reconstruction
- concession-aware rewriting
- causal explanation generation

## Recommended next improvements

For final experimental use, the following improvements are recommended.

1. Add a `requirements.txt` or `pyproject.toml`.
2. Add top-level `__init__.py` files if package-style execution is preferred.
3. Remove `__pycache__` before publication.
4. Add a CLI for balanced few-shot selection.
5. Add strict invalid-output accounting.
6. Add per-condition metric aggregation.
7. Add `summary_by_condition.csv` exactly as specified in the original plan.
8. Add a complete downstream generation script for the activation-steering utilities.
9. Add tests for prompt construction, parsing, mapping, and metrics.
10. Add a small synthetic test fixture to validate the complete run end-to-end without loading a real model.

## Minimal expected deliverables

A complete run should eventually produce:

```text
results/metrics/summary_by_condition.csv
results/metrics/native_validity.csv
results/metrics/coarse_accuracy_macro_f1.csv
results/metrics/self_consistency.csv
results/metrics/cross_model_agreement.csv
results/metrics/distributional_alignment_jsd.csv
results/figures/confusion_erst_normalized.pdf
results/figures/confusion_rstweb_normalized.pdf
results/figures/confusion_pcc_normalized.pdf
results/predictions/*.jsonl
```

The current repository already produces several of these, but some filenames and aggregation levels differ slightly from the initial plan.

## License and data

No license file is currently included. Add an explicit license before public release.

No real corpora are bundled. Add or generate corpus-derived JSONL files locally under `data/processed/` or `data/raw/` according to the data contract above.
