"""Anatomical navigation configuration, never a clinical assertion or a body-site inference."""

from pathlib import Path
from typing import Any

import orjson

from latros.common import LatrosError

CONFIG_PATH = Path(__file__).parent / "assets/anatomy/navigation.json"


def load_navigation() -> dict[str, Any]:
    config: dict[str, Any] = orjson.loads(CONFIG_PATH.read_bytes())
    nodes = config["nodes"]
    if config["role"] != "navigation_only_not_clinical_knowledge" or len(nodes) > 64:
        raise LatrosError("Invalid or oversized anatomical navigation")
    for key, node in nodes.items():
        if node["id"] != key or node.get("parent") not in {None, *nodes}:
            raise LatrosError("Invalid anatomical navigation identity")
        if node["asset"] not in {"body-front.svg", "head-front.svg", "sinuses-front.svg"}:
            raise LatrosError("Invalid local anatomical asset")
        if len(node.get("codes", [])) > 100:
            raise LatrosError("Too many anatomical navigation references")
        if set(node["labels"]) != {"fr", "de", "en"} or any(
            child not in nodes or nodes[child].get("parent") != key for child in node["children"]
        ):
            raise LatrosError("Invalid anatomical labels or children")
        visited = {key}
        parent = node.get("parent")
        while parent:
            if parent in visited:
                raise LatrosError("Cyclic anatomical navigation")
            visited.add(parent)
            parent = nodes[parent].get("parent")
    return config
