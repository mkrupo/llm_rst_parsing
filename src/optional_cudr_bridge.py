"""
optional_cudr_bridge.py
=======================

This module provides a thin wrapper around the external Discursive‑Circuits
repository for the optional circuit discovery experiments described in the
extended benchmark plan.  It is **not** required for the core relation
labeling benchmark and is intentionally designed to be invoked only when
the necessary dependencies and data are available.

The primary entry point is the function :func:`run_cudr_patch`, which calls
the ``circuit_discovery.py`` script from the Discursive‑Circuits repo.
Arguments mirror those of the upstream script where relevant.  You can also
invoke this module directly from the command line::

    python -m rst_prompt_adequacy.src.optional_cudr_bridge \
        --repo ../repos/Discursive-Circuits \
        --relation causal-result_r \
        --source_relation Contingency.Cause.Result \
        --dataset_name RST \
        --dataset_name_source PDTB

This will attempt to run the patching mode of the upstream script with
default options.

Note that the Discursive‑Circuits experiments require significant GPU
resources and additional data.  If these are not present the invocation
may fail.  Use this bridge at your own discretion.
"""

from __future__ import annotations

import argparse
import subprocess
import pathlib
from typing import Optional


def run_cudr_patch(
    repo_dir: pathlib.Path,
    relation: str,
    source_relation: str,
    dataset_name: str = "RST",
    dataset_name_source: str = "PDTB",
    mode: str = "patch",
    level: int = 3,
    gentype: str = "gendataset",
    n_samples: int = 32,
    seed: int = 42,
) -> subprocess.CompletedProcess:
    """Call the circuit discovery script from the Discursive‑Circuits repo.

    Parameters
    ----------
    repo_dir: pathlib.Path
        Path to the cloned Discursive‑Circuits repository.
    relation: str
        Target relation name in the target dataset.
    source_relation: str
        Source relation name in the source dataset (e.g. PDTB relation).
    dataset_name: str
        Name of the target dataset (e.g. RST, GDTB, PDTB, SDRT).
    dataset_name_source: str
        Name of the source dataset (e.g. PDTB when patching an RST relation).
    mode: str
        Mode for the discovery script (e.g. 'learn' or 'patch').
    level: int
        Level of analysis: 0 (random), 1 (layer), 3 (feature).  See
        upstream documentation for details.
    gentype: str
        Generation type used by the script (e.g. own, gendataset, genrel).
    n_samples: int
        Number of samples to generate.
    seed: int
        Random seed.

    Returns
    -------
    subprocess.CompletedProcess
        The result of running the subprocess.
    """
    script = repo_dir / "scripts" / "circuit_discovery.py"
    cmd = [
        "python",
        str(script),
        "--relation", relation,
        "--source_relation", source_relation,
        "--dataset_name", dataset_name,
        "--dataset_name_source", dataset_name_source,
        "--batch_size", "1",
        "--N_sample", str(n_samples),
        "--mode", mode,
        "--level", str(level),
        "--gentype", gentype,
        "--seed", str(seed),
    ]
    print(f"Running command: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=repo_dir, check=False, capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge to Discursive‑Circuits circuit discovery script.")
    parser.add_argument("--repo", type=str, required=True, help="Path to the Discursive‑Circuits repository.")
    parser.add_argument("--relation", type=str, required=True, help="Target relation name (e.g. causal-result_r).")
    parser.add_argument("--source_relation", type=str, required=True, help="Source relation name (e.g. Contingency.Cause.Result).")
    parser.add_argument("--dataset_name", type=str, default="RST", help="Target dataset name.")
    parser.add_argument("--dataset_name_source", type=str, default="PDTB", help="Source dataset name.")
    parser.add_argument("--mode", type=str, default="patch", help="Mode for the discovery script (learn/patch).")
    parser.add_argument("--level", type=int, default=3, help="Level of analysis (0, 1, or 3).")
    parser.add_argument("--gentype", type=str, default="gendataset", help="Generation type for the script.")
    parser.add_argument("--n_samples", type=int, default=32, help="Number of samples.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()
    result = run_cudr_patch(
        repo_dir=pathlib.Path(args.repo),
        relation=args.relation,
        source_relation=args.source_relation,
        dataset_name=args.dataset_name,
        dataset_name_source=args.dataset_name_source,
        mode=args.mode,
        level=args.level,
        gentype=args.gentype,
        n_samples=args.n_samples,
        seed=args.seed,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)


if __name__ == "__main__":
    main()