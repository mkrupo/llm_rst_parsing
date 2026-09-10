"""Strict parsing and validation for model-produced compact RST trees."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Mapping, Sequence, Tuple, Union


_RELATION_LABEL = re.compile(r"(NN|NS|SN)-([A-Za-z][A-Za-z0-9_-]*)")


@dataclass(frozen=True)
class CompactNode:
    """One node in the deliberately small compact-tree grammar."""

    label: str
    children: Tuple[Union["CompactNode", str], ...]


def _tokenize(source: str) -> List[str]:
    tokens: List[str] = []
    offset = 0
    while offset < len(source):
        if source[offset].isspace():
            offset += 1
        elif source[offset] in "()":
            tokens.append(source[offset])
            offset += 1
        else:
            end = offset
            while end < len(source) and not source[end].isspace() and source[end] not in "()":
                end += 1
            tokens.append(source[offset:end])
            offset = end
    return tokens


def parse_compact_tree(source: str) -> CompactNode:
    """Parse exactly one parenthesized tree without accepting free-form prose."""
    tokens = _tokenize(source)
    if not tokens:
        raise ValueError("compact tree is empty")

    def parse_node(position: int) -> Tuple[CompactNode, int]:
        if position >= len(tokens) or tokens[position] != "(":
            got = tokens[position] if position < len(tokens) else "end of input"
            raise ValueError(f"expected '(' in compact tree, got {got!r}")
        if position + 1 >= len(tokens) or tokens[position + 1] in {"(", ")"}:
            raise ValueError("compact tree node is missing a label")
        label = tokens[position + 1]
        children: List[Union[CompactNode, str]] = []
        position += 2
        while position < len(tokens) and tokens[position] != ")":
            if tokens[position] == "(":
                child, position = parse_node(position)
                children.append(child)
            else:
                children.append(tokens[position])
                position += 1
        if position >= len(tokens):
            raise ValueError(f"compact tree node {label!r} is not closed")
        return CompactNode(label, tuple(children)), position + 1

    root, position = parse_node(0)
    if position != len(tokens):
        raise ValueError("compact tree contains content outside its root node")
    return root


def validate_compact_tree(
    root: CompactNode,
    expected_indices: Sequence[str],
    relation_types: Mapping[str, str],
) -> None:
    """Validate grammar, scheme membership, nuclearity, arity, and EDU coverage."""
    observed_indices: List[str] = []

    def visit(node: CompactNode) -> None:
        if node.label == "text":
            if len(node.children) != 1 or not isinstance(node.children[0], str):
                raise ValueError("each text node must contain exactly one index")
            observed_indices.append(node.children[0])
            return

        match = _RELATION_LABEL.fullmatch(node.label)
        if match is None:
            raise ValueError(
                f"relation node {node.label!r} must match NN|NS|SN-RELATION"
            )
        nuclearity, relation = match.groups()
        relation_type = relation_types.get(relation)
        if relation_type is None:
            raise ValueError(f"relation {relation!r} is not allowed by the scheme")
        expected_type = "multinuc" if nuclearity == "NN" else "rst"
        if relation_type != expected_type:
            raise ValueError(
                f"relation {relation!r} is {relation_type}, not {expected_type}"
            )
        if nuclearity == "NN" and len(node.children) < 2:
            raise ValueError(f"multinuclear node {node.label!r} needs at least two children")
        if nuclearity != "NN" and len(node.children) != 2:
            raise ValueError(f"mononuclear node {node.label!r} must have two children")
        if any(not isinstance(child, CompactNode) for child in node.children):
            raise ValueError(f"relation node {node.label!r} may contain only child nodes")
        for child in node.children:
            visit(child)

    visit(root)
    expected = list(expected_indices)
    if observed_indices != expected:
        missing = [index for index in expected if index not in observed_indices]
        unexpected = [index for index in observed_indices if index not in expected]
        duplicates = sorted(
            {index for index in observed_indices if observed_indices.count(index) > 1}
        )
        raise ValueError(
            "tree leaves do not exactly match input order: "
            f"expected={expected}, observed={observed_indices}, missing={missing}, "
            f"unexpected={unexpected}, duplicates={duplicates}"
        )
