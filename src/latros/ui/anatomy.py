"""Anatomical navigation configuration, never a clinical assertion or a body-site inference."""

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import orjson

from latros.common import LatrosError

CONFIG_PATH = Path(__file__).parent / "assets/anatomy/navigation.json"


@lru_cache(maxsize=8)
def _verify_image(path: Path, size: int, mtime: int, ctime: int, digest: str) -> None:
    # Metadata participates in cache invalidation; hashes never mutate the asset.
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise LatrosError("Anatomical illustration integrity mismatch")


def _valid_box(box: list[int], canvas: list[int]) -> bool:
    return (
        len(box) == 4
        and all(type(value) is int for value in box)
        and box[0] >= 0
        and box[1] >= 0
        and box[2] > 0
        and box[3] > 0
        and box[0] + box[2] <= canvas[0]
        and box[1] + box[3] <= canvas[1]
    )


def load_navigation() -> dict[str, Any]:
    config: dict[str, Any] = orjson.loads(CONFIG_PATH.read_bytes())
    manifest = orjson.loads((CONFIG_PATH.parent / "illustrations.json").read_bytes())
    images = {image["filename"]: image for image in manifest["images"]}
    for filename, image in images.items():
        if Path(filename).name != filename or not re.fullmatch(
            r"[a-z0-9-]+-atlas-v[12]\.png", filename
        ):
            raise LatrosError("Invalid illustration path")
        path = CONFIG_PATH.parent / filename
        stat = path.stat()
        if stat.st_size != image["bytes"]:
            raise LatrosError("Invalid illustration size")
        _verify_image(path, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, image["sha256"])
    nodes = config["nodes"]
    if config["role"] != "navigation_only_not_clinical_knowledge" or len(nodes) > 64:
        raise LatrosError("Invalid or oversized anatomical navigation")
    for key, node in nodes.items():
        if node["id"] != key or node.get("parent") not in {None, *nodes}:
            raise LatrosError("Invalid anatomical navigation identity")
        if node["asset"] != "atlas-overlay.svg" or node.get("image") not in images:
            raise LatrosError("Invalid local anatomical asset")
        if node.get("canvas") != images[node["image"]]["canvas"]:
            raise LatrosError("Invalid illustration dimensions")
        if "focus_box" in node and not _valid_box(node["focus_box"], node["canvas"]):
            raise LatrosError("Invalid anatomical viewport")
        if node.get("parent") and (
            not node.get("hitboxes")
            or any(not _valid_box(box, nodes[node["parent"]]["canvas"]) for box in node["hitboxes"])
        ):
            raise LatrosError("Invalid anatomical overlay")
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
