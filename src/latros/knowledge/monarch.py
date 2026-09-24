"""Offline reader for disease-to-phenotype rows in a pinned Monarch KG archive."""

import csv
import io
import tarfile
from collections.abc import Iterator
from pathlib import Path

from pydantic import Field

from latros.common import LatrosError
from latros.sources.registry import Contract

EDGES_MEMBER = "monarch-kg_edges.tsv"


class MonarchDiseasePhenotypeRecord(Contract):
    edge_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    object: str = Field(pattern=r"^HP:\d+$")
    predicate: str = "biolink:has_phenotype"
    category: str = "biolink:DiseaseToPhenotypicFeatureAssociation"
    primary_knowledge_source: str = Field(min_length=1)
    aggregator_knowledge_source: str = Field(min_length=1)
    file_source: str = Field(min_length=1)
    publications: str | None = None
    evidence: str | None = None
    negated: bool = False
    frequency_qualifier: str | None = None
    has_count: int | None = None
    has_percentage: float | None = None
    has_quotient: float | None = None
    has_total: int | None = None
    onset_qualifier: str | None = None
    sex_qualifier: str | None = None
    original_subject: str | None = None
    original_object: str | None = None
    source_locator: str = Field(min_length=1)


def iter_monarch_disease_phenotypes(
    path: Path, *, accepted_subjects: set[str], accepted_objects: set[str]
) -> Iterator[MonarchDiseasePhenotypeRecord]:
    """Yield only directly resolvable human disease/HPO associations from the local tarball."""
    if not path.is_file():
        raise LatrosError(f"Monarch artifact is missing: {path}")
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            try:
                member = archive.getmember(EDGES_MEMBER)
            except KeyError as exc:
                raise LatrosError(f"Monarch archive is missing {EDGES_MEMBER}") from exc
            binary = archive.extractfile(member)
            if binary is None:
                raise LatrosError(f"Monarch archive cannot read {EDGES_MEMBER}")
            with binary, io.TextIOWrapper(binary, encoding="utf-8", newline="") as text:
                reader = csv.DictReader(text, delimiter="\t")
                required = {
                    "id",
                    "predicate",
                    "category",
                    "subject",
                    "object",
                    "primary_knowledge_source",
                    "aggregator_knowledge_source",
                    "file_source",
                }
                if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                    raise LatrosError("Monarch KG edge columns do not satisfy the importer")
                for ordinal, row in enumerate(reader, 2):
                    if (
                        row["predicate"] != "biolink:has_phenotype"
                        or row["category"] != "biolink:DiseaseToPhenotypicFeatureAssociation"
                        or row["subject"] not in accepted_subjects
                        or row["object"] not in accepted_objects
                    ):
                        continue
                    yield MonarchDiseasePhenotypeRecord(
                        edge_id=_required(row.get("id"), "id"),
                        subject=row["subject"],
                        object=row["object"],
                        primary_knowledge_source=_required(
                            row.get("primary_knowledge_source"), "primary knowledge source"
                        ),
                        aggregator_knowledge_source=_required(
                            row.get("aggregator_knowledge_source"),
                            "aggregator knowledge source",
                        ),
                        file_source=_required(row.get("file_source"), "file source"),
                        publications=_optional(row.get("publications")),
                        evidence=_optional(row.get("has_evidence")),
                        negated=str(row.get("negated", "")).casefold() == "true",
                        frequency_qualifier=_optional(row.get("frequency_qualifier")),
                        has_count=_integer(row.get("has_count")),
                        has_percentage=_number(row.get("has_percentage")),
                        has_quotient=_number(row.get("has_quotient")),
                        has_total=_integer(row.get("has_total")),
                        onset_qualifier=_optional(row.get("onset_qualifier")),
                        sex_qualifier=_optional(row.get("sex_qualifier")),
                        original_subject=_optional(row.get("original_subject")),
                        original_object=_optional(row.get("original_object")),
                        source_locator=f"{EDGES_MEMBER}:row={ordinal}:id={row['id']}",
                    )
    except (tarfile.TarError, UnicodeDecodeError, csv.Error) as exc:
        raise LatrosError(f"Invalid Monarch KG archive: {path}") from exc


def _required(value: str | None, label: str) -> str:
    cleaned = _optional(value)
    if cleaned is None:
        raise LatrosError(f"Monarch association missing {label}")
    return cleaned


def _optional(value: str | None) -> str | None:
    value = value.strip() if value else ""
    return value or None


def _integer(value: str | None) -> int | None:
    return int(value) if value and value.strip() else None


def _number(value: str | None) -> float | None:
    return float(value) if value and value.strip() else None
