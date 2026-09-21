"""Streaming parser for a locally pinned NLM MeSH descriptors distribution."""

import gzip
from pathlib import Path
from typing import Any

from lxml import etree
from pydantic import Field

from latros.common import LatrosError
from latros.sources.registry import Contract


class MeshDescriptorRecord(Contract):
    descriptor_ui: str = Field(pattern=r"^D\d+$")
    name: str = Field(min_length=1)
    terms: list[str] = Field(min_length=1)
    tree_numbers: list[str] = Field(default_factory=list)
    source_locator: str = Field(min_length=1)


def parse_mesh_descriptors(path: Path) -> list[MeshDescriptorRecord]:
    """Read XML or gzip XML without DTD/entity resolution or network access."""
    if not path.is_file():
        raise LatrosError(f"MeSH artifact is missing: {path}")
    try:
        if path.suffix.lower() == ".gz":
            with gzip.open(path, "rb") as source:
                return _parse(source)
        with path.open("rb") as source:
            return _parse(source)
    except (OSError, EOFError) as exc:
        raise LatrosError(f"Invalid MeSH artifact: {path}") from exc


def _parse(source: Any) -> list[MeshDescriptorRecord]:
    records: list[MeshDescriptorRecord] = []
    seen: set[str] = set()
    try:
        context = etree.iterparse(
            source,
            events=("end",),
            tag="DescriptorRecord",
            resolve_entities=False,
            load_dtd=False,
            no_network=True,
            huge_tree=True,
        )
        for _, element in context:
            descriptor_ui = _required(element.findtext("DescriptorUI"), "DescriptorUI")
            if descriptor_ui in seen:
                raise LatrosError(f"Duplicate MeSH descriptor: {descriptor_ui}")
            seen.add(descriptor_ui)
            name = _required(element.findtext("DescriptorName/String"), "descriptor name")
            terms = sorted(
                {
                    value
                    for node in element.findall("ConceptList/Concept/TermList/Term/String")
                    if (value := _clean(node.text))
                }
                | {name},
                key=lambda value: (value != name, value.casefold(), value),
            )
            records.append(
                MeshDescriptorRecord(
                    descriptor_ui=descriptor_ui,
                    name=name,
                    terms=terms,
                    tree_numbers=sorted(
                        value
                        for node in element.findall("TreeNumberList/TreeNumber")
                        if (value := _clean(node.text))
                    ),
                    source_locator=f"DescriptorRecord[DescriptorUI='{descriptor_ui}']",
                )
            )
            element.clear()
            while element.getprevious() is not None:
                del element.getparent()[0]
    except etree.XMLSyntaxError as exc:
        raise LatrosError("Invalid MeSH XML artifact") from exc
    if not records:
        raise LatrosError("MeSH XML contains no DescriptorRecord")
    return records


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _required(value: str | None, label: str) -> str:
    cleaned = _clean(value)
    if cleaned is None:
        raise LatrosError(f"Missing MeSH {label}")
    return cleaned
