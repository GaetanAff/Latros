"""Offline parser for a pre-fetched MedlinePlus Health Topics XML artifact."""

from pathlib import Path
from typing import Any, Self
from zipfile import BadZipFile, ZipFile

from lxml import etree
from pydantic import Field, model_validator

from latros.common import LatrosError
from latros.sources.registry import Contract


class MedlinePlusSiteRecord(Contract):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    organizations: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)


class MedlinePlusMeshHeading(Contract):
    descriptor_id: str = Field(min_length=1)
    label: str = Field(min_length=1)


class MedlinePlusRelatedTopic(Contract):
    topic_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)


class MedlinePlusTopicRecord(Contract):
    topic_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    language: str = Field(min_length=1)
    url: str = Field(min_length=1)
    date_created: str | None = None
    meta_description: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    mesh_headings: list[MedlinePlusMeshHeading] = Field(default_factory=list)
    summaries: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    related_topics: list[MedlinePlusRelatedTopic] = Field(default_factory=list)
    links: list[MedlinePlusSiteRecord] = Field(default_factory=list)
    source_locator: str = Field(min_length=1)

    @model_validator(mode="after")
    def stable_locator_matches_topic(self) -> Self:
        if self.source_locator != f"health-topic[@id='{self.topic_id}']":
            raise ValueError("MedlinePlus source locator must be derived from topic_id")
        return self


def parse_medlineplus_topics(path: Path) -> list[MedlinePlusTopicRecord]:
    """Parse a local XML file without resolving entities, DTDs, or network resources."""
    if not path.is_file():
        raise LatrosError(f"MedlinePlus artifact is missing: {path}")
    if path.suffix.lower() != ".zip":
        return _parse_xml_source(str(path))
    try:
        with ZipFile(path) as archive:
            members = [
                item
                for item in archive.infolist()
                if not item.is_dir() and Path(item.filename).suffix.lower() == ".xml"
            ]
            if len(members) != 1:
                raise LatrosError("MedlinePlus ZIP must contain exactly one XML artifact")
            member = members[0]
            if Path(member.filename).name != member.filename:
                raise LatrosError("MedlinePlus ZIP contains an unsafe XML path")
            with archive.open(member) as source:
                return _parse_xml_source(source)
    except BadZipFile as exc:
        raise LatrosError(f"Invalid MedlinePlus ZIP: {path}") from exc


def _parse_xml_source(source: Any) -> list[MedlinePlusTopicRecord]:
    records: list[MedlinePlusTopicRecord] = []
    seen: set[str] = set()
    try:
        context = etree.iterparse(
            source,
            events=("end",),
            tag="health-topic",
            resolve_entities=False,
            load_dtd=False,
            no_network=True,
            huge_tree=True,
        )
        for _, element in context:
            topic_id = _required(element.get("id"), "health-topic id")
            if topic_id in seen:
                raise LatrosError(f"Duplicate MedlinePlus topic id: {topic_id}")
            seen.add(topic_id)
            records.append(_topic(element, topic_id))
            element.clear()
            while element.getprevious() is not None:
                del element.getparent()[0]
    except etree.XMLSyntaxError as exc:
        raise LatrosError("Invalid MedlinePlus XML artifact") from exc
    if not records:
        raise LatrosError("MedlinePlus XML contains no health-topic records")
    return records


def _topic(element: etree._Element, topic_id: str) -> MedlinePlusTopicRecord:
    links = []
    for site in element.findall("site"):
        title = site.get("title") or _text(site.find("title"))
        url = site.get("url") or _text(site.find("url"))
        if not title or not url:
            continue
        links.append(
            MedlinePlusSiteRecord(
                title=title,
                url=url,
                organizations=_texts(site, "organization"),
                categories=_texts(site, "information-category"),
                descriptions=_texts(site, "standard-description"),
            )
        )
    return MedlinePlusTopicRecord(
        topic_id=topic_id,
        title=_required(element.get("title") or _text(element), "health-topic title"),
        language=_required(element.get("language"), "health-topic language"),
        url=_required(element.get("url"), "health-topic url"),
        date_created=element.get("date-created"),
        meta_description=element.get("meta-desc"),
        synonyms=_texts(element, "also-called"),
        mesh_headings=[
            MedlinePlusMeshHeading(
                descriptor_id=_required(child.get("id"), "MeSH descriptor id"),
                label=_required(_text(child), "MeSH descriptor label"),
            )
            for child in element.findall("mesh-heading/descriptor")
        ],
        summaries=_texts(element, "full-summary"),
        groups=_texts(element, "group"),
        related_topics=[
            MedlinePlusRelatedTopic(
                topic_id=_required(child.get("id"), "related-topic id"),
                title=_required(_text(child), "related-topic title"),
                url=_required(child.get("url"), "related-topic url"),
            )
            for child in element.findall("related-topic")
        ],
        links=links,
        source_locator=f"health-topic[@id='{topic_id}']",
    )


def _texts(element: etree._Element, path: str) -> list[str]:
    return [value for child in element.findall(path) if (value := _text(child))]


def _text(element: etree._Element | None) -> str | None:
    if element is None:
        return None
    parts = [item.decode() if isinstance(item, bytes) else item for item in element.itertext()]
    value = " ".join("".join(parts).split())
    return value or None


def _required(value: str | None, label: str) -> str:
    if value is None or not value.strip():
        raise LatrosError(f"Missing MedlinePlus {label}")
    return value.strip()
