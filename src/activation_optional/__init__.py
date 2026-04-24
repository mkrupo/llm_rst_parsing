"""Optional utilities for activation steering experiments.

This subpackage contains lightweight helper classes and functions that
wrap the more sophisticated activation capture and steering
implementations provided by the external `steering_content_effects`
repository. These utilities are not needed for the core relation
classification benchmark, but they enable researchers to experiment
with activation steering techniques on downstream generation tasks.

To avoid pulling large dependencies into the main package, the
utilities here conditionally import the steering helpers from
``repos/steering_content_effects`` at runtime. If the repository is
not available or cannot be imported, the import will fail with a
helpful error message instructing users to clone the repository into
``rst_prompt_adequacy/repos`` as described in the project README.
"""

from .rst_dataset import RSTPromptDataset  # noqa: F401
from .activation_utils import (
    prepare_activation_capture,
    compute_activation_stats,
    build_steering_vectors,
    apply_activation_steering,
)

__all__ = [
    "RSTPromptDataset",
    "prepare_activation_capture",
    "compute_activation_stats",
    "build_steering_vectors",
    "apply_activation_steering",
]