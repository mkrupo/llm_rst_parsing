"""Deterministic RS3 serialization for validated compact RST trees."""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

from .compact_tree import CompactNode
from .schemes import Scheme


@dataclass
class _BodyNode:
    node_id: str
    kind: str
    text: Optional[str] = None
    group_type: Optional[str] = None
    parent: Optional[str] = None
    relname: Optional[str] = None


def write_rs3(
    compact_tree: CompactNode,
    edu_text: Mapping[str, str],
    scheme: Scheme,
    output_path: pathlib.Path,
) -> None:
    """Write a validated compact tree as an RS3 document."""
    segments: List[_BodyNode] = []
    groups: List[_BodyNode] = []
    next_segment_id = 1
    next_group_id = len(edu_text) + 1

    def build(node: CompactNode) -> _BodyNode:
        nonlocal next_segment_id, next_group_id
        if node.label == "text":
            index = node.children[0]
            body_node = _BodyNode(
                node_id=str(next_segment_id),
                kind="segment",
                text=edu_text[index],
            )
            next_segment_id += 1
            segments.append(body_node)
            return body_node

        nuclearity, relation = node.label.split("-", 1)
        group = _BodyNode(
            node_id=str(next_group_id),
            kind="group",
            group_type="multinuc" if nuclearity == "NN" else "span",
        )
        next_group_id += 1
        groups.append(group)
        children = [build(child) for child in node.children]

        if nuclearity == "NN":
            for child in children:
                child.parent = group.node_id
                child.relname = relation
        else:
            nucleus_position = nuclearity.index("N")
            satellite_position = nuclearity.index("S")
            nucleus = children[nucleus_position]
            satellite = children[satellite_position]
            nucleus.parent = group.node_id
            nucleus.relname = "span"
            satellite.parent = nucleus.node_id
            satellite.relname = relation
        return group

    build(compact_tree)

    root = ET.Element("rst")
    header = ET.SubElement(root, "header")
    relations = ET.SubElement(header, "relations")
    for relation, relation_type in scheme.relations.items():
        ET.SubElement(relations, "rel", {"name": relation, "type": relation_type})

    body = ET.SubElement(root, "body")
    for node in segments:
        attributes: Dict[str, str] = {"id": node.node_id}
        if node.parent is not None:
            attributes.update({"parent": node.parent, "relname": node.relname})
        element = ET.SubElement(body, "segment", attributes)
        element.text = node.text
    for node in groups:
        attributes = {"id": node.node_id, "type": node.group_type}
        if node.parent is not None:
            attributes.update({"parent": node.parent, "relname": node.relname})
        ET.SubElement(body, "group", attributes)

    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output_path, encoding="UTF-8", xml_declaration=True)
