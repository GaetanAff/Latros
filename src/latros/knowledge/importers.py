"""Source-specific importers. No inference of equivalence from a bare xref."""

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import orjson
from lxml import etree

from latros.common import LatrosError, stable_id
from latros.knowledge.frequency import Frequency, parse_frequency
from latros.sources.registry import Artifact, Registry, Source

Row = dict[str, Any]

TABLES: dict[str, dict[str, str]] = {
    "source_release": {
        "id": "VARCHAR",
        "source_id": "VARCHAR",
        "release": "VARCHAR",
        "metadata_json": "VARCHAR",
    },
    "concept": {
        "id": "VARCHAR",
        "external_id": "VARCHAR",
        "kind": "VARCHAR",
        "label": "VARCHAR",
        "obsolete": "BOOLEAN",
        "source_release_id": "VARCHAR",
    },
    "term": {
        "id": "VARCHAR",
        "concept_id": "VARCHAR",
        "language": "VARCHAR",
        "text": "VARCHAR",
        "scope": "VARCHAR",
        "source_release_id": "VARCHAR",
    },
    "external_identifier": {
        "id": "VARCHAR",
        "concept_id": "VARCHAR",
        "identifier": "VARCHAR",
        "relation": "VARCHAR",
        "source_release_id": "VARCHAR",
    },
    "hierarchy_edge": {
        "id": "VARCHAR",
        "child_id": "VARCHAR",
        "parent_id": "VARCHAR",
        "source_release_id": "VARCHAR",
    },
    "mapping": {
        "id": "VARCHAR",
        "subject_id": "VARCHAR",
        "target_external_id": "VARCHAR",
        "relation": "VARCHAR",
        "source_release_id": "VARCHAR",
        "evidence_json": "VARCHAR",
    },
    "disease_phenotype_assertion": {
        "id": "VARCHAR",
        "disease_id": "VARCHAR",
        "phenotype_id": "VARCHAR",
        "source_phenotype_id": "VARCHAR",
        "polarity": "VARCHAR",
        "frequency_json": "VARCHAR",
        "source_release_id": "VARCHAR",
        "source_record_id": "VARCHAR",
        "languages_json": "VARCHAR",
        "provenance_json": "VARCHAR",
    },
}


def compact(value: str) -> str:
    if match := re.search(r"(?:/obo/|^)(HP|MONDO)[_:](\d+)$", value):
        return f"{match[1]}:{match[2]}"
    if match := re.search(r"(?:Orphanet[_:]|ORPHA:)(\d+)$", value):
        return f"ORPHA:{match[1]}"
    return value


def json_text(value: Any) -> str:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS).decode()


class Knowledge:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Row]] = {table: {} for table in TABLES}
        self.concepts: dict[str, Row] = {}
        self.aliases: dict[str, set[str]] = defaultdict(set)
        self.replacements: dict[str, set[str]] = defaultdict(set)
        self.warnings: list[str] = []
        self.term_lookup: set[tuple[str, str, str]] = set()

    def add(self, table: str, row: Row, *, identical_ok: bool = False) -> None:
        existing = self.rows[table].get(row["id"])
        if existing is not None:
            if identical_ok and existing == row:
                return
            raise LatrosError(f"Duplicate {table} record: {row['id']}")
        self.rows[table][row["id"]] = row

    def concept(self, external: str, kind: str, label: str, obsolete: bool, source: str) -> str:
        key = stable_id("concept", external)
        if external not in self.concepts:
            row = dict(
                id=key,
                external_id=external,
                kind=kind,
                label=label,
                obsolete=obsolete,
                source_release_id=source,
            )
            self.add("concept", row)
            self.concepts[external] = row
            self.add(
                "external_identifier",
                dict(
                    id=stable_id("identifier", external, external),
                    concept_id=key,
                    identifier=external,
                    relation="primary",
                    source_release_id=source,
                ),
            )
        return key

    def term(self, key: str, text: str, language: str, scope: str, source: str) -> None:
        if not text.strip():
            raise LatrosError(f"Empty label for {key}")
        self.add(
            "term",
            dict(
                id=stable_id("term", key, language, text, scope, source),
                concept_id=key,
                language=language,
                text=text,
                scope=scope,
                source_release_id=source,
            ),
            identical_ok=True,
        )
        self.term_lookup.add((key, language, text))

    def resolve_hpo(self, external: str) -> str:
        visited: set[str] = set()
        current = external
        while True:
            if current in visited:
                raise LatrosError(f"Cyclic HPO replacement: {external}")
            visited.add(current)
            row = self.concepts.get(current)
            if row and not row["obsolete"]:
                return str(row["id"])
            targets = self.replacements[current] if row else self.aliases[current]
            if row and not targets:
                warning = f"Inactive HPO retained but excluded from reasoning: {external}"
                if warning not in self.warnings:
                    self.warnings.append(warning)
                return str(row["id"])
            if len(targets) != 1:
                raise LatrosError(f"Unresolved/ambiguous HPO identifier: {external}")
            current = next(iter(targets))


def source_key(source: Source) -> str:
    return f"{source.id}:{source.release}"


def import_ontology(kb: Knowledge, path: Path, source: Source, artifact: Artifact) -> None:
    document = orjson.loads(path.read_bytes())
    prefix = "HP:" if source.id == "hpo" else "MONDO:"
    sid = source_key(source)
    graphs = document["graphs"]
    for graph in graphs:
        for node in graph.get("nodes", []):
            external = compact(node["id"])
            if node.get("type") != "CLASS" or not external.startswith(prefix):
                continue
            meta = node.get("meta", {})
            key = kb.concept(
                external,
                "phenotype" if prefix == "HP:" else "disease",
                node.get("lbl", external),
                bool(meta.get("deprecated", False)),
                sid,
            )
            kb.term(key, node.get("lbl", external), artifact.language, "preferred", sid)
            for syn in meta.get("synonyms", []):
                kb.term(key, syn["val"], artifact.language, syn.get("pred", "related"), sid)
            for item in meta.get("basicPropertyValues", []):
                predicate, target = item["pred"], compact(item["val"])
                if predicate.endswith("hasAlternativeId"):
                    kb.aliases[target].add(external)
                    kb.add(
                        "external_identifier",
                        dict(
                            id=stable_id("identifier", external, target),
                            concept_id=key,
                            identifier=target,
                            relation="alternative",
                            source_release_id=sid,
                        ),
                    )
                elif predicate.endswith("IAO_0100001"):
                    kb.replacements[external].add(target)
                    add_mapping(kb, key, target, "replaced_by", sid, item)
                elif "Match" in predicate and target.startswith("ORPHA:"):
                    relation = predicate.rsplit("#", 1)[-1]
                    add_mapping(kb, key, target, relation, sid, item)
            for xref in meta.get("xrefs", []):
                target = compact(xref["val"])
                if target.startswith("ORPHA:"):
                    add_mapping(kb, key, target, "xref", sid, xref)
    for graph in graphs:
        for edge in graph.get("edges", []):
            child, parent = compact(edge["sub"]), compact(edge["obj"])
            if edge["pred"] != "is_a" or not child.startswith(prefix):
                continue
            # Cross-ontology edges are out of scope, never treated as HPO ancestry.
            if not parent.startswith(prefix):
                continue
            if child not in kb.concepts or parent not in kb.concepts:
                raise LatrosError(f"Unresolved hierarchy edge: {child} -> {parent}")
            kb.add(
                "hierarchy_edge",
                dict(
                    id=stable_id("edge", child, parent, sid),
                    child_id=kb.concepts[child]["id"],
                    parent_id=kb.concepts[parent]["id"],
                    source_release_id=sid,
                ),
                identical_ok=True,
            )


def add_mapping(
    kb: Knowledge, key: str, target: str, relation: str, sid: str, evidence: Row
) -> None:
    kb.add(
        "mapping",
        dict(
            id=stable_id("mapping", key, target, relation, sid),
            subject_id=key,
            target_external_id=target,
            relation=relation,
            source_release_id=sid,
            evidence_json=json_text(evidence),
        ),
        identical_ok=True,
    )


ORPHA_FREQUENCIES = {
    "28405": "HP:0040280",
    "28412": "HP:0040281",
    "28419": "HP:0040282",
    "28426": "HP:0040283",
    "28433": "HP:0040284",
    "28440": "HP:0040285",
}


def import_orphadata(kb: Knowledge, path: Path, source: Source, artifact: Artifact) -> set[str]:
    sid = source_key(source)
    seen: set[str] = set()
    # No entity expansion, DTD fetching or network access while parsing XML.
    tree = etree.parse(str(path), etree.XMLParser(resolve_entities=False, no_network=True))
    if getattr(tree.docinfo, "doctype", ""):
        raise LatrosError("DTDs are not accepted in Orphadata input")
    for disorder in tree.iter("Disorder"):
        code = disorder.findtext("OrphaCode")
        name = disorder.findtext("Name")
        if not code or not code.isdigit() or not name:
            raise LatrosError("Orphadata disease requires code and label")
        external = f"ORPHA:{code}"
        disease = kb.concept(external, "disease", name, False, sid)
        kb.term(disease, name, artifact.language, "preferred", sid)
        for entry in disorder.findall("./HPODisorderAssociationList/HPODisorderAssociation"):
            record_id = entry.get("id")
            raw_hpo = entry.findtext("./HPO/HPOId")
            label = entry.findtext("./HPO/HPOTerm")
            if not record_id or not raw_hpo or not label:
                raise LatrosError("Orphadata assertion missing identifier/phenotype/label")
            if record_id in seen:
                raise LatrosError(
                    f"Duplicate Orphadata assertion in {artifact.filename}: {record_id}"
                )
            seen.add(record_id)
            phenotype = kb.resolve_hpo(raw_hpo)
            # FR disease names can coexist with untranslated English HPO labels.
            # Preserve the source document locale separately in provenance.
            language = artifact.language
            if language == "fr" and (phenotype, "en", label) in kb.term_lookup:
                language = "en"
            kb.term(phenotype, label, language, "source_label", sid)
            frequency_node = entry.find("HPOFrequency")
            fid = frequency_node.get("id") if frequency_node is not None else None
            if fid and fid not in ORPHA_FREQUENCIES:
                raise LatrosError(f"Unrecognized Orphadata frequency: {fid}")
            frequency = parse_frequency(ORPHA_FREQUENCIES.get(fid or ""))
            assertion_id = stable_id("assertion", source.id, record_id)
            provenance = dict(
                original_source=source.id,
                source_release=sid,
                source_record_id=record_id,
                artifact=artifact.filename,
                sha256=artifact.sha256,
                language=artifact.language,
                source_disease_id=external,
                source_phenotype_id=raw_hpo,
                frequency_id=fid,
                frequency_label=entry.findtext("./HPOFrequency/Name"),
                diagnostic_criteria=entry.findtext("./DiagnosticCriteria/Name"),
                reference=disorder.findtext("ExpertLink"),
                ingestion_chain=[source.id, "latros:orphadata-product4-v1"],
            )
            row = dict(
                id=assertion_id,
                disease_id=disease,
                phenotype_id=phenotype,
                source_phenotype_id=raw_hpo,
                polarity="excluded" if frequency.kind == "excluded" else "present",
                frequency_json=json_text(frequency.model_dump()),
                source_release_id=sid,
                source_record_id=record_id,
                languages_json=json_text([artifact.language]),
                provenance_json=json_text([provenance]),
            )
            existing = kb.rows["disease_phenotype_assertion"].get(assertion_id)
            if existing is None:
                kb.add("disease_phenotype_assertion", row)
            else:
                for field in row.keys() - {"languages_json", "provenance_json"}:
                    if existing[field] != row[field]:
                        raise LatrosError(f"Conflicting EN/FR assertion: {record_id} ({field})")
                languages = orjson.loads(existing["languages_json"])
                if artifact.language in languages:
                    raise LatrosError(f"Duplicate language for assertion: {record_id}")
                existing["languages_json"] = json_text(sorted([*languages, artifact.language]))
                existing["provenance_json"] = json_text(
                    sorted(
                        [*orjson.loads(existing["provenance_json"]), provenance],
                        key=lambda p: p["language"],
                    )
                )
    if not seen:
        raise LatrosError(f"No assertions imported from {artifact.filename}")
    return seen


def import_registry(root: Path, registry: Registry) -> Knowledge:
    kb = Knowledge()
    if {s.id for s in registry.sources} != {"hpo", "mondo", "orphadata"}:
        raise LatrosError("Snapshot v1 requires exactly HPO, Mondo and Orphadata")
    for source in sorted(registry.sources, key=lambda s: s.id):
        kb.add(
            "source_release",
            dict(
                id=source_key(source),
                source_id=source.id,
                release=source.release,
                metadata_json=json_text(source.model_dump(mode="json")),
            ),
        )
    for source in sorted(registry.sources, key=lambda s: s.id):
        if source.id == "orphadata":
            continue
        for artifact in source.artifacts:
            if artifact.format != "obographs-json":
                raise LatrosError("Ontology artifact must use OBOGraphs JSON")
            import_ontology(
                kb,
                root / "data/raw" / source.id / source.release / artifact.filename,
                source,
                artifact,
            )
    source = next(s for s in registry.sources if s.id == "orphadata")
    if {a.language for a in source.artifacts} != {"en", "fr"} or len(source.artifacts) != 2:
        raise LatrosError("Orphadata requires one English and one French artifact")
    record_sets = []
    for artifact in sorted(source.artifacts, key=lambda a: a.language):
        if artifact.format != "orphadata-product4-xml":
            raise LatrosError("Orphadata requires product4 XML")
        record_sets.append(
            import_orphadata(
                kb,
                root / "data/raw" / source.id / source.release / artifact.filename,
                source,
                artifact,
            )
        )
    if record_sets[0] != record_sets[1]:
        raise LatrosError("English and French Orphadata releases have different assertion sets")
    validate_knowledge(kb)
    return kb


def validate_knowledge(kb: Knowledge) -> None:
    concepts, sources = kb.rows["concept"], kb.rows["source_release"]
    for table, records in kb.rows.items():
        for row in records.values():
            if table != "source_release" and row["source_release_id"] not in sources:
                raise LatrosError(f"Missing provenance: {table}/{row['id']}")
            for field in (
                "concept_id",
                "child_id",
                "parent_id",
                "subject_id",
                "disease_id",
                "phenotype_id",
            ):
                if field in row and row[field] not in concepts:
                    raise LatrosError(f"Unresolved reference: {table}/{field}/{row[field]}")
    frequencies: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in kb.rows["disease_phenotype_assertion"].values():
        Frequency.model_validate_json(row["frequency_json"])
        if not row["source_record_id"] or not orjson.loads(row["provenance_json"]):
            raise LatrosError("Missing assertion provenance")
        frequencies[row["disease_id"], row["phenotype_id"]].add(row["frequency_json"])
    for (disease, phenotype), values in frequencies.items():
        if len(values) > 1:
            kb.warnings.append(
                "Conflicting frequencies; retained, not usable for penalties/questions: "
                f"{concepts[disease]['external_id']} / {concepts[phenotype]['external_id']}"
            )
    # DAG verification also rejects cycles unrelated to the current example case.
    parents: dict[str, set[str]] = defaultdict(set)
    for edge in kb.rows["hierarchy_edge"].values():
        parents[edge["child_id"]].add(edge["parent_id"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise LatrosError(f"Hierarchy cycle at {node}")
        if node in visited:
            return
        visiting.add(node)
        for parent in parents.get(node, set()):
            visit(parent)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(parents):
        visit(node)
