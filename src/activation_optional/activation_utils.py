"""Activation steering utilities.

This module provides convenience functions for setting up activation
capture and steering on HuggingFace transformer models. These helpers
wrap the classes defined in the external
``steering_content_effects`` repository and offer simple APIs for
capturing hidden state activations, computing average activation
statistics over groups of examples, building steering vectors, and
applying steering during generation.

Because activation steering is optional in the context of the
relation-labeling benchmark, all imports from the
``steering_content_effects`` repository are performed lazily. If the
repository has not been cloned into ``rst_prompt_adequacy/repos``,
functions that depend on it will raise an informative error. See the
project README for cloning instructions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

import torch

try:
    # Dynamically add the steering_content_effects repo to sys.path if present
    _root = Path(__file__).resolve().parents[2]
    _steering_repo = _root / "repos" / "steering_content_effects"
    if _steering_repo.exists():
        sys.path.append(str(_steering_repo))
    from hook_utils import ActivationCapture, ActivationSteering  # type: ignore
except Exception as e:
    # Delay raising import error until functions are actually called
    ActivationCapture = None  # type: ignore
    ActivationSteering = None  # type: ignore
    _import_error = e


def _check_steering_imports():
    """Raise an error if the steering utilities are not available."""
    if ActivationCapture is None or ActivationSteering is None:
        raise ImportError(
            "The steering_content_effects repository is not available. "
            "Please clone it into `rst_prompt_adequacy/repos` as described "
            "in the project README. Underlying error: %s" % _import_error
        )


def prepare_activation_capture(model: torch.nn.Module, module_names: List[str]) -> Any:
    """Initialise an ``ActivationCapture`` for a given model and modules.

    Parameters
    ----------
    model : torch.nn.Module
        The transformer model whose hidden activations should be captured.
    module_names : List[str]
        A list of module names (e.g. ``["model.layers.0", "model.layers.1"]``) from
        which to capture the last-token activations. These names must
        correspond to modules in ``model.named_modules()``.

    Returns
    -------
    ActivationCapture
        An instance that has hooks registered on the specified modules.
    """
    _check_steering_imports()
    return ActivationCapture(model, module_names)


def compute_activation_stats(
    model: torch.nn.Module,
    module_names: List[str],
    dataset: Any,
    tokenizer: Any,
    device: Optional[torch.device] = None,
    max_length: int = 512,
) -> Dict[str, List[torch.Tensor]]:
    """Compute hidden state activations for a dataset across specified layers.

    This function iterates over the dataset and captures the last-token
    hidden activations from the modules listed in ``module_names``. It
    returns a dictionary mapping each module name to a list of tensors
    (one per example). The model is set to evaluation mode and the
    activation capture hooks are removed when finished.

    Parameters
    ----------
    model : torch.nn.Module
        The transformer model to evaluate. It should accept keyword
        arguments compatible with the HuggingFace model API, such as
        ``input_ids`` and ``attention_mask``.
    module_names : List[str]
        Names of modules within ``model`` to capture activations from.
    dataset : Iterable
        An iterable of items. Each item must be a dictionary with a
        ``"prompt"`` key containing the text to feed into the model.
    tokenizer : Any
        A tokenizer compatible with the model. It should implement
        ``__call__`` and return a dictionary with keys ``input_ids`` and
        optionally ``attention_mask``.
    device : torch.device, optional
        The device on which to run the model. If ``None``, the model's
        own device is used.
    max_length : int
        Maximum number of tokens to keep from the tokenised input.

    Returns
    -------
    Dict[str, List[torch.Tensor]]
        A dictionary mapping module names to lists of tensors, where each
        tensor corresponds to the captured activation for a single
        example.
    """
    _check_steering_imports()

    capture = ActivationCapture(model, module_names)
    model_device = device if device is not None else next(model.parameters()).device
    model.eval()

    # Initialise storage for activations
    activations: Dict[str, List[torch.Tensor]] = {name: [] for name in module_names}

    for example in dataset:
        prompt = example["prompt"]
        # Tokenise and trim to maximum length
        enc = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=max_length,
        )
        enc = {k: v.to(model_device) for k, v in enc.items()}
        with torch.no_grad():
            _ = model(**enc)
        # Extract activations from capture
        for name in module_names:
            act = capture.get_activations().get(name)
            if act is not None:
                # Flatten to 1D vector for easier averaging
                activations[name].append(act.squeeze(0).detach().cpu())
        # Reset capture for the next example
        capture.reset_activations()

    capture.remove_hooks()
    return activations


def build_steering_vectors(
    activations_pos: Dict[str, List[torch.Tensor]],
    activations_neg: Dict[str, List[torch.Tensor]],
) -> Dict[str, Dict[str, torch.Tensor]]:
    """Construct steering vectors from positive and negative activation sets.

    Given two dictionaries of activations (one for positive examples and
    one for negative examples), this function computes the average
    activation for each module in both sets and constructs a set of
    steering vectors appropriate for the ``ActivationSteering`` class.
    The returned dictionary has four top-level keys: ``contrastive``,
    ``random``, ``positive``, and ``negative``. Each value is itself a
    dictionary mapping module names to 1D tensors. The contrastive
    vectors are simply ``positive - negative``. Random vectors are
    sampled from a standard normal distribution with the same shape as
    the contrastive vectors. Positive and negative vectors hold the
    averages for the respective groups.

    Parameters
    ----------
    activations_pos : Dict[str, List[torch.Tensor]]
        Module-wise activations for examples belonging to the positive class.
    activations_neg : Dict[str, List[torch.Tensor]]
        Module-wise activations for examples belonging to the negative class.

    Returns
    -------
    Dict[str, Dict[str, torch.Tensor]]
        A dictionary of steering vectors keyed by ``contrastive``,
        ``random``, ``positive``, and ``negative``.
    """
    # Helper to compute the mean vector for each module
    def _mean_dict(acts: Dict[str, List[torch.Tensor]]) -> Dict[str, torch.Tensor]:
        mean_dict: Dict[str, torch.Tensor] = {}
        for name, tensors in acts.items():
            if len(tensors) == 0:
                raise ValueError(f"No activations recorded for module {name}")
            stacked = torch.stack(tensors, dim=0)
            mean_dict[name] = stacked.mean(dim=0)
        return mean_dict

    pos_mean = _mean_dict(activations_pos)
    neg_mean = _mean_dict(activations_neg)

    steering_vectors: Dict[str, Dict[str, torch.Tensor]] = {
        "contrastive": {},
        "random": {},
        "positive": {},
        "negative": {},
    }
    for name in pos_mean.keys():
        diff = pos_mean[name] - neg_mean[name]
        steering_vectors["contrastive"][name] = diff
        # Random vector with same shape as diff
        steering_vectors["random"][name] = torch.randn_like(diff)
        steering_vectors["positive"][name] = pos_mean[name]
        steering_vectors["negative"][name] = neg_mean[name]
    return steering_vectors


def apply_activation_steering(
    model: torch.nn.Module,
    module_names: List[str],
    steering_vectors: Dict[str, Dict[str, torch.Tensor]],
    c: float = 1.0,
    transformation: str = "addition",
    conditional: bool = False,
    valid_condition_vector: Optional[Dict[str, Any]] = None,
    invalid_condition_vector: Optional[Dict[str, Any]] = None,
    multi_steering: bool = False,
    is_random: bool = False,
    is_retrieval_based: bool = False,
    top_k: int = 3,
) -> Any:
    """Instantiate an ``ActivationSteering`` object to modify model activations.

    This function returns an ``ActivationSteering`` instance configured
    with the provided steering vectors and parameters. Users can
    register this steering on a model prior to generation. When using
    unconditional steering (``conditional=False``), only the
    ``contrastive`` or ``random`` vectors are used depending on the
    ``is_random`` flag. When conditional steering is enabled,
    ``valid_condition_vector`` and ``invalid_condition_vector`` must be
    provided. See the documentation in ``hook_utils.py`` for details on
    the available steering modes and arguments.

    Parameters
    ----------
    model : torch.nn.Module
        The transformer model to steer. Hooks will be registered on
        modules whose names appear in ``module_names``.
    module_names : List[str]
        Names of modules within the model on which to apply steering.
    steering_vectors : Dict[str, Dict[str, torch.Tensor]]
        Steering vectors as returned by ``build_steering_vectors``.
    c : float
        Scaling constant for the steering vector.
    transformation : str
        Transformation type: ``"addition"`` (default), ``"scaling"``,
        ``"non-linear"``, or ``"patching"``.
    conditional : bool
        Whether to apply conditional steering. See ``hook_utils.py``.
    valid_condition_vector : Optional[Dict[str, Any]]
        Module-wise valid condition vectors for conditional steering.
    invalid_condition_vector : Optional[Dict[str, Any]]
        Module-wise invalid condition vectors for conditional steering.
    multi_steering : bool
        Whether to steer multiple modules simultaneously with different
        condition vectors.
    is_random : bool
        If ``True``, use the random steering vectors instead of the
        contrastive vectors.
    is_retrieval_based : bool
        If ``True`` and conditional steering is enabled, use retrieval
        based condition evaluation. See ``hook_utils.py``.
    top_k : int
        Top-k parameter used for retrieval based steering.

    Returns
    -------
    ActivationSteering
        An instance with hooks registered on the specified modules.
    """
    _check_steering_imports()
    # Select the appropriate steering vectors: contrastive (default) or random
    vec_key = "random" if is_random else "contrastive"
    selected_vectors = {name: steering_vectors[vec_key][name] for name in module_names}
    # Build dictionaries for positive and negative vectors when conditional
    pos_vectors = {name: steering_vectors["positive"][name] for name in module_names}
    neg_vectors = {name: steering_vectors["negative"][name] for name in module_names}
    # If valid/invalid condition vectors are not provided but conditional is
    # requested, fall back to using the positive and negative averages.
    if conditional and (valid_condition_vector is None or invalid_condition_vector is None):
        valid_condition_vector = pos_vectors
        invalid_condition_vector = neg_vectors
    # Compose the steering vector dict required by ActivationSteering
    steering_vector_dict = {
        "contrastive": selected_vectors,
        "random": selected_vectors,  # Not used when is_random=False
        "positive": pos_vectors,
        "negative": neg_vectors,
    }
    return ActivationSteering(
        model=model,
        module_names=module_names,
        steering_vector=steering_vector_dict,
        c=c,
        transformation=transformation,
        conditional=conditional,
        valid_condition_vector=valid_condition_vector,
        invalid_condition_vector=invalid_condition_vector,
        multi_steering=multi_steering,
        is_random=is_random,
        is_retrieval_based=is_retrieval_based,
        top_k=top_k,
    )