"""Dataset wrapper for activation steering experiments.

This module defines a small ``RSTPromptDataset`` class that wraps the
benchmark items used in the relation classification experiments into a
format suitable for activation steering. Each dataset element is a
dictionary containing a prompt, its gold coarse label, and the item
identifier. The prompts are built on the fly using a user-provided
``prompt_builder`` function so that steering experiments can reuse
exactly the same prompt formats as the core benchmark.

Typical usage:

.. code-block:: python

    from rst_prompt_adequacy.src.activation_optional import RSTPromptDataset
    from rst_prompt_adequacy.src.prompt_templates import build_prompt

    # Assume ``items`` is a list of benchmark rows read from JSONL
    # and ``fewshots`` is a list of few-shot examples.  We want to
    # build prompts for the eRST standard in its native formulation.
    def my_prompt_builder(row):
        return build_prompt(
            item=row,
            standard="erst",
            formulation="as_written",
            fewshots=[]  # no few-shots for steering
        )
    dataset = RSTPromptDataset(items, prompt_builder=my_prompt_builder)
    prompt = dataset[0]["prompt"]
    label = dataset[0]["label"]

This class can be passed to a torch ``DataLoader`` if desired. The
dataset is intentionally simple to minimise dependencies and to
encourage reuse of existing prompt-building logic.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Any

from torch.utils.data import Dataset


class RSTPromptDataset(Dataset):
    """A thin dataset wrapper for RST prompts used in activation steering.

    Parameters
    ----------
    rows : List[Dict[str, Any]]
        A list of dictionaries representing benchmark items. Each
        dictionary should contain at least an ``item_id`` and a
        ``gold_coarse`` label.
    prompt_builder : Callable[[Dict[str, Any]], str]
        A callable that takes a row and returns the full prompt string
        to be fed into the language model. The builder should embed
        all necessary instruction text and, if needed, few-shot
        examples. See ``prompt_templates.build_prompt`` for details.
    """

    def __init__(self, rows: List[Dict[str, Any]], prompt_builder: Callable[[Dict[str, Any]], str]):
        self.rows = rows
        self.prompt_builder = prompt_builder

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        row = self.rows[idx]
        prompt = self.prompt_builder(row)
        return {
            "prompt": prompt,
            "label": row.get("gold_coarse", None),
            "item_id": row.get("item_id", None),
        }