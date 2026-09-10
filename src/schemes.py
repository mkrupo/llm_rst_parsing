"""Load and validate scheme profiles used by e2e inference and conversion."""

from __future__ import annotations

import hashlib
import pathlib
import re
from dataclasses import dataclass
from typing import Dict, Mapping

import yaml


_RELATION_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_PROMPT_NAME = re.compile(r"ICL_.+_e2e\.txt")
_RELATION_TYPES = {"rst", "multinuc"}
_SCHEME_KEYS = {"name", "version", "description", "prompt", "relations"}


@dataclass(frozen=True)
class Scheme:
    """A versioned relation inventory and its default e2e prompt."""

    name: str
    version: str
    description: str
    prompt: str
    relations: Mapping[str, str]
    sha256: str
    path: pathlib.Path

    def metadata(self) -> Dict[str, str]:
        """Return stable provenance fields suitable for a prediction record."""
        return {
            "name": self.name,
            "version": self.version,
            "sha256": self.sha256,
        }


def load_scheme(path: pathlib.Path) -> Scheme:
    """Load a strict YAML scheme profile and return its normalized form."""
    raw_bytes = path.read_bytes()
    try:
        data = yaml.safe_load(raw_bytes)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid scheme YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"scheme must be a YAML object: {path}")
    unknown_keys = set(data) - _SCHEME_KEYS
    if unknown_keys:
        raise ValueError(f"unknown scheme keys: {sorted(unknown_keys)}")

    name = data.get("name")
    if not isinstance(name, str) or not _RELATION_NAME.fullmatch(name):
        raise ValueError("scheme name must be a nonempty identifier")

    version_value = data.get("version")
    if not isinstance(version_value, (str, int)) or isinstance(version_value, bool):
        raise ValueError("scheme version must be a string or integer")
    version = str(version_value).strip()
    if not version:
        raise ValueError("scheme version must not be blank")

    description = data.get("description", "")
    if not isinstance(description, str):
        raise ValueError("scheme description must be a string")

    prompt = data.get("prompt")
    if (
        not isinstance(prompt, str)
        or pathlib.Path(prompt).name != prompt
        or not _PROMPT_NAME.fullmatch(prompt)
    ):
        raise ValueError("scheme prompt must be an ICL_*_e2e.txt filename")

    relation_data = data.get("relations")
    if not isinstance(relation_data, dict) or not relation_data:
        raise ValueError("scheme relations must be a nonempty mapping")
    relations: Dict[str, str] = {}
    for relation, relation_type in relation_data.items():
        if not isinstance(relation, str) or not _RELATION_NAME.fullmatch(relation):
            raise ValueError(
                f"relation names must be compact tree identifiers, got {relation!r}"
            )
        if relation_type not in _RELATION_TYPES:
            raise ValueError(
                f"relation {relation!r} must have type 'rst' or 'multinuc'"
            )
        relations[relation] = relation_type

    return Scheme(
        name=name,
        version=version,
        description=description.strip(),
        prompt=prompt,
        relations=relations,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        path=path,
    )
