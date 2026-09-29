"""Rebuild the versioned UI atlas registry from local, generated PNG plates.

Navigation references are editorial UI links to existing HPO identifiers, never
clinical body-site relations. This script does not read or modify a snapshot.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Any

ATLAS = Path(__file__).resolve().parents[1] / "src/latros/ui/assets/anatomy"
NEW_PLATES = (
    "thorax",
    "lungs",
    "heart",
    "abdomen",
    "stomach",
    "liver",
    "intestines",
    "urinary",
    "kidneys",
    "ureters",
    "bladder",
    "arms",
    "shoulder",
    "arm",
    "elbow",
    "forearm",
    "wrist",
    "hand",
    "legs",
    "hip",
    "thigh",
    "knee",
    "lower-leg",
    "ankle",
    "foot",
    "back",
    "spine",
    "cervical",
    "thoracic-back",
    "lumbar",
)


def plate(name: str) -> str:
    return f"{name}-atlas-v2.png"


def dimensions(path: Path) -> list[int]:
    payload = path.read_bytes()[:24]
    if payload[:8] != b"\x89PNG\r\n\x1a\n" or payload[12:16] != b"IHDR":
        raise ValueError(f"Not a PNG: {path}")
    return list(struct.unpack(">II", payload[16:24]))


def box(canvas: list[int], x: float, y: float, width: float, height: float) -> list[int]:
    w, h = canvas
    return [round(x * w), round(y * h), round(width * w), round(height * h)]


def create_node(
    nodes: dict[str, Any],
    key: str,
    parent: str,
    labels: tuple[str, str, str],
    image: str,
    regions: list[tuple[float, float, float, float]],
    *,
    codes: tuple[str, ...] = (),
    children: tuple[str, ...] = (),
) -> None:
    parent_canvas = nodes[parent]["canvas"]
    filename = image if image.endswith(".png") else plate(image)
    nodes[key] = {
        "id": key,
        "parent": parent,
        "labels": dict(zip(("fr", "de", "en"), labels, strict=True)),
        "asset": "atlas-overlay.svg",
        "image": filename,
        "canvas": dimensions(ATLAS / filename),
        "children": list(children),
        "codes": list(codes),
        "implemented": True,
        "hitboxes": [box(parent_canvas, *region) for region in regions],
        "focus_box": [0, 0, *dimensions(ATLAS / filename)],
    }
    if key not in nodes[parent]["children"]:
        nodes[parent]["children"].append(key)


def main() -> None:
    registry_path = ATLAS / "illustrations.json"
    navigation_path = ATLAS / "navigation.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    config = json.loads(navigation_path.read_text(encoding="utf-8"))
    if config["version"] not in {"ui-anatomy-2", "ui-anatomy-3"}:
        raise ValueError("Unexpected navigation version")
    old = {item["filename"]: item for item in registry["images"]}
    for name in NEW_PLATES:
        filename = plate(name)
        path = ATLAS / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        old[filename] = {
            "id": name,
            "filename": filename,
            "version": 2,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "canvas": dimensions(path),
            "view": "frontal or indicated cutaway",
            "review_status": "not_anatomically_validated",
            "human_reviewer": None,
            "brief": f"Isolated {name} navigation plate; no clinical interpretation.",
            "generator": "OpenAI built-in image generation",
            "prompt_family": "Latros semi-realistic atlas, isolated anatomy, transparent alpha, "
            "natural tissue colours, no labels/text/watermark; per-asset subject: " + name,
            "created": "2026-09-28",
        }
    registry["version"] = "latros-atlas-2"
    registry["created"] = "2026-09-28"
    registry["images"] = [old[name] for name in sorted(old)]
    config["version"] = "ui-anatomy-3"
    nodes = config["nodes"]
    # All navigation changes below are independent of clinical scoring and snapshots.
    for key, image in {
        "thorax": "thorax",
        "lungs": "lungs",
        "heart": "heart",
        "chest-wall": "thorax",
        "abdomen": "abdomen",
        "epigastrium": "stomach",
        "intestines": "intestines",
        "liver": "liver",
        "urinary": "urinary",
        "arms": "arms",
        "shoulder": "shoulder",
        "elbow": "elbow",
        "wrist": "wrist",
        "hands": "hand",
        "legs": "legs",
        "hip": "hip",
        "thigh": "thigh",
        "knee": "knee",
        "lower-leg": "lower-leg",
        "ankle": "ankle",
        "feet": "foot",
    }.items():
        canvas = dimensions(ATLAS / plate(image))
        nodes[key]["image"] = plate(image)
        nodes[key]["canvas"] = canvas
        nodes[key]["focus_box"] = [0, 0, *canvas]

    # Hitboxes belong to the *parent* plate, not the individual organ art.
    target_boxes: dict[str, list[tuple[float, float, float, float]]] = {
        "lungs": [(0.08, 0.34, 0.35, 0.43), (0.57, 0.34, 0.35, 0.43)],
        "heart": [(0.40, 0.50, 0.21, 0.32)],
        "chest-wall": [(0.17, 0.20, 0.66, 0.14)],
        "epigastrium": [(0.47, 0.24, 0.37, 0.27)],
        "intestines": [(0.19, 0.48, 0.63, 0.40)],
        "liver": [(0.12, 0.12, 0.41, 0.31)],
        "shoulder": [(0.05, 0.05, 0.25, 0.18), (0.70, 0.05, 0.25, 0.18)],
        "elbow": [(0.05, 0.44, 0.26, 0.13), (0.69, 0.44, 0.26, 0.13)],
        "wrist": [(0.05, 0.72, 0.26, 0.12), (0.69, 0.72, 0.26, 0.12)],
        "hip": [(0.22, 0.06, 0.24, 0.16), (0.54, 0.06, 0.24, 0.16)],
        "thigh": [(0.24, 0.20, 0.23, 0.31), (0.53, 0.20, 0.23, 0.31)],
        "knee": [(0.25, 0.48, 0.22, 0.14), (0.53, 0.48, 0.22, 0.14)],
        "lower-leg": [(0.25, 0.61, 0.22, 0.23), (0.53, 0.61, 0.22, 0.23)],
        "ankle": [(0.25, 0.83, 0.22, 0.09), (0.53, 0.83, 0.22, 0.09)],
    }
    for key, regions in target_boxes.items():
        parent = nodes[key]["parent"]
        nodes[key]["hitboxes"] = [box(nodes[parent]["canvas"], *region) for region in regions]

    create_node(
        nodes,
        "kidneys",
        "urinary",
        ("Reins", "Nieren", "Kidneys"),
        "kidneys",
        [(0.17, 0.26, 0.27, 0.32), (0.56, 0.26, 0.27, 0.32)],
    )
    create_node(
        nodes,
        "ureters",
        "urinary",
        ("Uretères", "Harnleiter", "Ureters"),
        "ureters",
        [(0.36, 0.49, 0.13, 0.29), (0.52, 0.49, 0.13, 0.29)],
    )
    create_node(
        nodes,
        "bladder",
        "urinary",
        ("Vessie", "Harnblase", "Bladder"),
        "bladder",
        [(0.36, 0.77, 0.29, 0.16)],
    )
    create_node(
        nodes,
        "upper-arm",
        "arms",
        ("Bras", "Oberarm", "Upper arm"),
        "arm",
        [(0.08, 0.21, 0.25, 0.23), (0.67, 0.21, 0.25, 0.23)],
    )
    create_node(
        nodes,
        "forearm",
        "arms",
        ("Avant-bras", "Unterarm", "Forearm"),
        "forearm",
        [(0.06, 0.56, 0.25, 0.18), (0.69, 0.56, 0.25, 0.18)],
    )
    create_node(
        nodes,
        "back",
        "body",
        ("Dos (vue postérieure)", "Rücken (Rückansicht)", "Back (posterior view)"),
        "back",
        [(0.47, 0.22, 0.09, 0.25)],
    )
    create_node(
        nodes,
        "spine",
        "back",
        ("Colonne", "Wirbelsäule", "Spine"),
        "spine",
        [(0.42, 0.10, 0.16, 0.80)],
    )
    create_node(
        nodes,
        "cervical-back",
        "back",
        ("Cervicales", "Halswirbelsäule", "Neck spine"),
        "cervical",
        [(0.36, 0.08, 0.28, 0.20)],
    )
    create_node(
        nodes,
        "thoracic-back",
        "back",
        ("Dos thoracique", "Brustwirbelsäule", "Upper back"),
        "thoracic-back",
        [(0.29, 0.28, 0.42, 0.36)],
    )
    create_node(
        nodes,
        "lumbar-back",
        "back",
        ("Lombaires", "Lendenwirbelsäule", "Lower back"),
        "lumbar",
        [(0.30, 0.65, 0.40, 0.25)],
    )
    create_node(
        nodes,
        "skin",
        "body",
        ("Peau", "Haut", "Skin"),
        "body-atlas-v1.png",
        [(0.24, 0.27, 0.12, 0.18), (0.64, 0.27, 0.12, 0.18)],
    )
    create_node(
        nodes,
        "general",
        "body",
        ("Symptômes généraux", "Allgemeine Symptome", "General symptoms"),
        "body-atlas-v1.png",
        [(0.37, 0.53, 0.28, 0.12)],
    )

    # Explicit UX navigation references only. Every code is resolved against the
    # active snapshot; absent/ambiguous concepts remain invisible. Multiple
    # regions may point at one identifier without creating a body-site assertion.
    additions: dict[str, tuple[str, ...]] = {
        "head": ("HP:0002315", "HP:0002321", "HP:0012199", "HP:0001251", "HP:0000731"),
        "sinuses": (
            "HP:0001742",
            "HP:0031417",
            "HP:0004409",
            "HP:0000458",
            "HP:0002315",
            "HP:0025095",
            "HP:0000421",
        ),
        "nose": (
            "HP:0001742",
            "HP:0031417",
            "HP:0025095",
            "HP:0000421",
            "HP:0004409",
            "HP:0000458",
        ),
        "ears": ("HP:0030766", "HP:0000365", "HP:0000360", "HP:0010780"),
        "eyes": (
            "HP:0200026",
            "HP:0000622",
            "HP:0000651",
            "HP:0000613",
            "HP:0000509",
            "HP:0031731",
            "HP:0030786",
            "HP:0000575",
        ),
        "mouth": ("HP:0000217", "HP:0000224", "HP:0041051", "HP:0010280", "HP:0000230"),
        "throat": (
            "HP:0033050",
            "HP:0032043",
            "HP:0002015",
            "HP:0001609",
            "HP:0001618",
            "HP:0010307",
        ),
        "neck": ("HP:0030833", "HP:0002716", "HP:0002015"),
        "thorax": (
            "HP:0012735",
            "HP:0002094",
            "HP:0100749",
            "HP:0031352",
            "HP:0030828",
            "HP:0001962",
            "HP:0002789",
            "HP:0031245",
            "HP:0031246",
            "HP:0034315",
        ),
        "lungs": (
            "HP:0012735",
            "HP:0002094",
            "HP:0030828",
            "HP:0031245",
            "HP:0012764",
            "HP:0002789",
            "HP:0002105",
            "HP:0010307",
            "HP:0031246",
            "HP:0034315",
            "HP:0033121",
        ),
        "heart": (
            "HP:0100749",
            "HP:0001962",
            "HP:0001649",
            "HP:0001656",
            "HP:0001662",
            "HP:0001279",
            "HP:0031352",
        ),
        "abdomen": (
            "HP:0002027",
            "HP:0002018",
            "HP:0002013",
            "HP:0002014",
            "HP:0002019",
            "HP:0001542",
            "HP:0410281",
            "HP:0002020",
            "HP:0033589",
            "HP:0004396",
            "HP:0410019",
            "HP:0032155",
            "HP:0002574",
        ),
        "epigastrium": (
            "HP:0002027",
            "HP:0410281",
            "HP:0002020",
            "HP:0002018",
            "HP:0002013",
            "HP:0410019",
        ),
        "intestines": (
            "HP:0002027",
            "HP:0002014",
            "HP:0002019",
            "HP:0033589",
            "HP:0001542",
            "HP:0002255",
            "HP:0002249",
            "HP:0032155",
        ),
        "liver": ("HP:0000952", "HP:0001393"),
        "pelvis": ("HP:0034267", "HP:0100518", "HP:0000012"),
        "urinary": (
            "HP:0100518",
            "HP:0000012",
            "HP:0000790",
            "HP:0000016",
            "HP:0000020",
            "HP:0000017",
            "HP:0000103",
            "HP:0100520",
            "HP:0030157",
            "HP:0031504",
            "HP:0000019",
        ),
        "kidneys": ("HP:0000790", "HP:0000093", "HP:0100520", "HP:0100519", "HP:0030157"),
        "ureters": ("HP:0000790", "HP:0100518"),
        "bladder": (
            "HP:0100518",
            "HP:0000012",
            "HP:0000016",
            "HP:0000020",
            "HP:0000017",
            "HP:0000019",
        ),
        "arms": ("HP:0012513", "HP:0003326", "HP:0002829", "HP:0001324", "HP:0002082"),
        "shoulder": ("HP:0030834", "HP:0002829", "HP:0001387"),
        "upper-arm": ("HP:0012513", "HP:0003326", "HP:0002082"),
        "elbow": ("HP:0030835", "HP:0002829", "HP:0001386"),
        "forearm": ("HP:0012513", "HP:0003326", "HP:0002082"),
        "wrist": ("HP:0030836", "HP:0002829", "HP:0001387", "HP:0001386", "HP:0034392"),
        "hands": ("HP:0046505", "HP:0025131", "HP:0002082", "HP:0001295", "HP:0002829"),
        "legs": ("HP:0012514", "HP:0003326", "HP:0001288", "HP:0001324"),
        "hip": ("HP:0030838", "HP:0002829", "HP:0001387"),
        "thigh": ("HP:0012514", "HP:0003326", "HP:0001324"),
        "knee": ("HP:0030839", "HP:0002829", "HP:0001386", "HP:0001387"),
        "lower-leg": ("HP:0012514", "HP:0003326", "HP:0000969"),
        "ankle": ("HP:0030840", "HP:0001785", "HP:0002829", "HP:0000969"),
        "feet": ("HP:0025238", "HP:0002829", "HP:0002082"),
        "back": ("HP:0003418", "HP:0003419", "HP:0030833", "HP:0003552"),
        "spine": ("HP:0003418", "HP:0003419", "HP:0030833"),
        "cervical-back": ("HP:0030833", "HP:0003418"),
        "thoracic-back": ("HP:0003418", "HP:0003326"),
        "lumbar-back": ("HP:0003419", "HP:0003418"),
        "skin": (
            "HP:0000988",
            "HP:0000989",
            "HP:0000958",
            "HP:0001025",
            "HP:0010783",
            "HP:0000967",
            "HP:0000979",
            "HP:0000959",
            "HP:0200042",
            "HP:0000969",
            "HP:0200036",
            "HP:0200037",
            "HP:0001053",
        ),
        "general": (
            "HP:0001945",
            "HP:0012378",
            "HP:0025143",
            "HP:0001824",
            "HP:0030166",
            "HP:0000975",
            "HP:0004396",
            "HP:0001959",
        ),
    }
    # HP:0001676 is ambiguous against an obsolete identity in the current
    # snapshot; the active Palpitations concept uses primary HP:0001962.
    for key in ("thorax", "heart"):
        nodes[key]["codes"] = [code for code in nodes[key]["codes"] if code != "HP:0001676"]
    for key, codes in additions.items():
        nodes[key]["codes"] = list(dict.fromkeys((*codes, *nodes[key]["codes"])))

    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    navigation_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
