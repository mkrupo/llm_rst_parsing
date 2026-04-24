"""
prompt_templates.py
====================

This module provides a small helper around the Markdown prompt files stored
under the ``prompts/`` directory.  Each standard (e.g. ``erst``) and
formulation (``as_written`` or ``normalized``) has a corresponding ``.md``
file containing the instructions and relation definitions for that scheme.

The ``build_prompt`` function takes an annotation item as input and
constructs the final prompt text by concatenating the template with
an input description and optional few‑shot examples.  The final output is
intended to be passed to a language model for classification.

Usage::

    from prompt_templates import build_prompt
    prompt = build_prompt(item, standard="erst", formulation="as_written")

If ``fewshots`` is provided, it should be a list of dictionaries with the
same keys as the items in your benchmark data.  The build function will
append these examples with their gold labels to the prompt as demonstrations
of the expected input/output format.
"""

from __future__ import annotations

import json
import pathlib
from typing import Dict, Any, List


_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_template(standard: str, formulation: str) -> str:
    """Load the Markdown template for a given annotation scheme.

    Parameters
    ----------
    standard: str
        One of ``erst``, ``rstweb`` or ``pcc``.
    formulation: str
        Either ``as_written`` or ``normalized``.

    Returns
    -------
    str
        The contents of the corresponding Markdown file as a string.
    """
    template_path = _ROOT / "prompts" / f"{standard}_{formulation}.md"
    try:
        return template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt template not found: {template_path}")


def build_prompt(*, item: Dict[str, Any], standard: str, formulation: str, fewshots: List[Dict[str, Any]] | None = None) -> str:
    """Assemble the final prompt for an annotation task.

    The returned prompt consists of three parts:

    #. The instruction template loaded from the ``prompts`` directory.
    #. Zero or more few‑shot examples, each comprising an input description and
       the expected JSON output with native and coarse labels.  These examples
       help the language model see what kind of outputs are required.  If
       ``fewshots`` is ``None`` or empty, this section is omitted.
    #. The actual input for the current item, with placeholders filled in.

    Parameters
    ----------
    item: Dict[str, Any]
        The annotation item containing at least ``left`` and ``right`` fields.
    standard: str
        One of the standards: ``erst``, ``rstweb`` or ``pcc``.  Used to
        determine which template to load.
    formulation: str
        Either ``as_written`` or ``normalized``.  Controls whether the prompt
        uses the original guideline wording or the harmonised, cross‑standard
        wording.
    fewshots: List[Dict[str, Any]] | None
        Optional list of few‑shot examples.  Each example should contain
        ``left``, ``right``, optional context, and the keys ``gold_native``
        and ``gold_coarse``.  The examples will be appended to the prompt
        verbatim with their known gold labels to demonstrate the output
        format.

    Returns
    -------
    str
        The assembled prompt ready to be sent to a language model.
    """
    template = _load_template(standard, formulation)
    prompt_parts: List[str] = [template.strip(), "\n\n"]

    # Append few‑shot examples if provided
    if fewshots:
        prompt_parts.append("### Examples\n")
        for idx, fs in enumerate(fewshots, start=1):
            left = fs.get("left", "")
            right = fs.get("right", "")
            before = fs.get("context_before", "")
            after = fs.get("context_after", "")
            # Build input description
            example_section = [f"Example {idx}:",
                               f"Input:",
                               f"Left: {left}",
                               f"Right: {right}",]
            if before:
                example_section.append(f"Context before: {before}")
            if after:
                example_section.append(f"Context after: {after}")
            # Build expected JSON output
            output = {
                "native_label": fs.get("gold_native"),
                "coarse_label": fs.get("gold_coarse"),
                "nuclearity": fs.get("nuclearity", "unknown"),
                "confidence": 1.0,
                "evidence": [],
                "rejected_alternatives": [],
            }
            example_section.append("Output:")
            example_section.append(json.dumps(output, ensure_ascii=False))
            prompt_parts.append("\n".join(example_section) + "\n\n")

    # Append final task input
    prompt_parts.append("### Task\n")
    prompt_parts.append("Annotate the relation between the following spans. Provide your answer as a JSON object with keys 'native_label', 'coarse_label', 'nuclearity', 'confidence', 'evidence' and 'rejected_alternatives'.\n")
    prompt_parts.append("Input:")
    prompt_parts.append(f"Left: {item.get('left', '')}")
    prompt_parts.append(f"Right: {item.get('right', '')}")
    if item.get("context_before"):
        prompt_parts.append(f"Context before: {item['context_before']}")
    if item.get("context_after"):
        prompt_parts.append(f"Context after: {item['context_after']}")
    prompt_parts.append("Output:")

    return "\n".join(prompt_parts)
