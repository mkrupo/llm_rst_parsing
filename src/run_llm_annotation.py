"""
run_llm_annotation.py
=====================

This script orchestrates the generation of relation labels for pre‑segmented
annotation items using one or more language models.  It reads a YAML
configuration file describing the datasets, prompt conditions and model
specifications, constructs prompts using :mod:`prompt_templates`, and
collects the raw and parsed responses.  The outputs are written as JSONL
files into the configured results directory.

The design aims to be simple and extensible: you can add new models by
editing the ``models`` section of ``configs/models.yaml`` and implement
custom behaviour in the ``LocalHFModel`` class below.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Dict, Any, Iterable, List, Optional

import yaml

from .prompt_templates import build_prompt
from .parse_outputs import safe_parse_json


class LocalHFModel:
    """A thin wrapper around HuggingFace text generation models.

    This class attempts to lazily load a local model via the ``transformers``
    library when instantiated.  If loading fails, calls to ``generate`` will
    fall back to a deterministic dummy output.  This behaviour makes the
    benchmark runnable in environments without GPU access or without the
    required model files installed.

    Parameters
    ----------
    model_id: str
        The HuggingFace model identifier or local path to load.  See the
        examples in ``configs/models.yaml``.
    """

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.pipe = None
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            model = AutoModelForCausalLM.from_pretrained(model_id)
            model.eval()
            # Device choice is automatic; set to CPU if GPU unavailable
            device = 0 if torch.cuda.is_available() else -1
            from transformers import pipeline
            self.pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, device=device)
        except Exception as exc:
            # Could not load model; fallback to dummy mode
            print(f"Warning: failed to load model {model_id}: {exc}\nFalling back to dummy output.")
            self.pipe = None

    def generate(self, prompt: str, max_new_tokens: int = 512, temperature: float = 0.0) -> str:
        """Generate a response from the model given a prompt.

        The returned string should contain the raw text output from the model.
        If the model failed to initialise, this method returns a dummy JSON
        object with unknown labels.  When using a real model, the prompt is
        passed through the pipeline with deterministic generation settings.

        Parameters
        ----------
        prompt: str
            The input prompt to send to the language model.
        max_new_tokens: int
            Maximum number of tokens to generate beyond the prompt.
        temperature: float
            Sampling temperature.  A value of 0.0 produces deterministic
            output; values above zero enable stochasticity.

        Returns
        -------
        str
            The raw generated text from the model.
        """
        if self.pipe is None:
            # Return a minimal valid JSON for dummy output
            dummy_output = {
                "native_label": None,
                "coarse_label": None,
                "nuclearity": "unknown",
                "confidence": 0.0,
                "evidence": [],
                "rejected_alternatives": [],
            }
            return json.dumps(dummy_output)
        # Real generation
        try:
            outputs = self.pipe(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0.0,
                num_return_sequences=1,
                pad_token_id=self.pipe.tokenizer.eos_token_id,
            )
            return outputs[0]["generated_text"][len(prompt):].strip()
        except Exception as exc:
            print(f"Generation failed: {exc}")
            dummy_output = {
                "native_label": None,
                "coarse_label": None,
                "nuclearity": "unknown",
                "confidence": 0.0,
                "evidence": [],
                "rejected_alternatives": [],
            }
            return json.dumps(dummy_output)


def load_jsonl(path: pathlib.Path) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dictionaries."""
    items: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def run(config_path: str = "configs/experiment.yaml") -> None:
    """Run the annotation experiment based on a YAML configuration file."""
    cfg_path = pathlib.Path(config_path)
    cfg = yaml.safe_load(open(cfg_path, "r", encoding="utf-8"))

    items = load_jsonl(pathlib.Path(cfg["data"]["input_jsonl"]))
    fewshots = load_jsonl(pathlib.Path(cfg["data"]["fewshot_jsonl"]))

    out_dir = pathlib.Path(cfg["data"]["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    # Loop over model specs
    for model_cfg in cfg.get("models", []):
        model_name = model_cfg.get("name")
        model_id = model_cfg.get("model_id")
        print(f"Loading model {model_name} ({model_id})...")
        model = LocalHFModel(model_id)

        # Loop over conditions
        for standard in cfg["conditions"]["standards"]:
            for formulation in cfg["conditions"]["formulations"]:
                for shot in cfg["conditions"]["shots"]:
                    # Determine decoding parameters
                    if shot == "zero":
                        temperature = cfg["decoding"]["zero_shot"].get("temperature", 0.0)
                        repeats = cfg["decoding"]["zero_shot"].get("n_repeats", 1)
                    else:
                        temperature = cfg["decoding"]["self_consistency"].get("temperature", 0.7)
                        repeats = cfg["decoding"]["self_consistency"].get("n_repeats", 5)
                    max_new_tokens = cfg["decoding"].get("max_new_tokens", 512)

                    fewshot_examples = fewshots if shot == "few" else []
                    outfile = out_dir / f"{model_name}_{standard}_{formulation}_{shot}.jsonl"
                    with open(outfile, "w", encoding="utf-8") as out:
                        for item in items:
                            prompt = build_prompt(
                                item=item,
                                standard=standard,
                                formulation=formulation,
                                fewshots=fewshot_examples,
                            )
                            # For each repeat, call the model and parse output
                            for _ in range(repeats):
                                raw_response = model.generate(prompt, max_new_tokens=max_new_tokens, temperature=temperature)
                                parsed = safe_parse_json(raw_response)
                                out.write(json.dumps({
                                    "item_id": item.get("item_id"),
                                    "model": model_name,
                                    "standard": standard,
                                    "formulation": formulation,
                                    "shot": shot,
                                    "gold_native": item.get("gold_native"),
                                    "gold_coarse": item.get("gold_coarse"),
                                    "raw": raw_response,
                                    "parsed": parsed,
                                }, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the LLM annotation experiment.")
    parser.add_argument("--config", type=str, default="configs/experiment.yaml", help="Path to the experiment YAML configuration file.")
    args = parser.parse_args()
    run(args.config)