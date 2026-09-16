import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import orjson

from latros.clinical.models import ClinicalCase, Status
from latros.common import LatrosError
from latros.knowledge.frequency import Frequency
from latros.knowledge.store import read_tables


class Engine:
    def __init__(self, root: Path, snapshot: str) -> None:
        self.manifest, tables = read_tables(root, snapshot)
        self.snapshot = snapshot
        self.concepts = {row["id"]: row for row in tables["concept"]}
        self.external = {row["external_id"]: row["id"] for row in tables["concept"]}
        self.parents: dict[str, set[str]] = defaultdict(set)
        self._ancestor_cache: dict[str, frozenset[str]] = {}
        for edge in tables["hierarchy_edge"]:
            self.parents[edge["child_id"]].add(edge["parent_id"])
        self.aliases: dict[str, set[str]] = defaultdict(set)
        for row in tables["external_identifier"]:
            self.aliases[row["identifier"]].add(row["concept_id"])
        self.replacements: dict[str, set[str]] = defaultdict(set)
        self.exact_mondo: dict[str, set[str]] = defaultdict(set)
        for row in tables["mapping"]:
            if row["relation"] == "replaced_by" and row["target_external_id"] in self.external:
                self.replacements[row["subject_id"]].add(self.external[row["target_external_id"]])
            if row["relation"] == "exactMatch" and row["target_external_id"].startswith("ORPHA:"):
                node = self.concepts[row["subject_id"]]
                if not node["obsolete"]:
                    self.exact_mondo[row["target_external_id"]].add(node["external_id"])
        self.labels: dict[tuple[str, str], str] = {}
        for row in sorted(tables["term"], key=lambda r: (r["scope"] != "preferred", r["text"])):
            self.labels.setdefault((row["concept_id"], row["language"]), row["text"])
        self.assertions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in tables["disease_phenotype_assertion"]:
            if self.concepts[row["phenotype_id"]]["obsolete"]:
                continue
            row["frequency"] = Frequency.model_validate_json(row["frequency_json"])
            self.assertions[row["disease_id"]].append(row)
        self.conflicts: set[tuple[str, str]] = set()
        for disease, rows in self.assertions.items():
            frequencies: dict[str, set[str]] = defaultdict(set)
            for row in rows:
                frequencies[row["phenotype_id"]].add(row["frequency_json"])
            self.conflicts.update(
                (disease, key) for key, values in frequencies.items() if len(values) > 1
            )
        self.positive = {
            d: [a for a in rows if a["polarity"] == "present"]
            for d, rows in self.assertions.items()
        }
        self.annotated_diseases: dict[str, set[str]] = defaultdict(set)
        self.direct_diseases: dict[str, set[str]] = defaultdict(set)
        for disease, rows in self.positive.items():
            for row in rows:
                self.direct_diseases[row["phenotype_id"]].add(disease)
                for ancestor in self.ancestors(row["phenotype_id"]):
                    self.annotated_diseases[ancestor].add(disease)
        corpus_size = sum(bool(rows) for rows in self.positive.values())
        if not corpus_size:
            raise LatrosError("Snapshot has no positively annotated diseases")
        self.ic = {
            key: -math.log(len(diseases) / corpus_size)
            for key, diseases in self.annotated_diseases.items()
        }

    def ancestors(self, node: str) -> frozenset[str]:
        if node not in self._ancestor_cache:
            self._ancestor_cache[node] = frozenset(
                {node}.union(*(self.ancestors(p) for p in self.parents.get(node, set())))
            )
        return self._ancestor_cache[node]

    def resolve(self, external: str) -> str:
        options = self.aliases.get(external, set())
        if len(options) != 1:
            raise LatrosError(f"Unknown or ambiguous phenotype: {external}")
        node = next(iter(options))
        seen: set[str] = set()
        while self.concepts[node]["obsolete"]:
            if node in seen or len(self.replacements[node]) != 1:
                raise LatrosError(f"Unresolved obsolete phenotype: {external}")
            seen.add(node)
            node = next(iter(self.replacements[node]))
        root = self.external.get("HP:0000118")
        if root is None or root not in self.ancestors(node) or root == node:
            raise LatrosError(f"Not a specific phenotypic abnormality: {external}")
        return node

    def observations(self, case: ClinicalCase) -> dict[str, Status]:
        result: dict[str, Status] = {}
        for external, status in case.effective_observations().items():
            key = self.resolve(external)
            if key in result:
                raise LatrosError("Observations resolve to the same phenotype via aliases")
            result[key] = status
        for present, status in result.items():
            if status == "present":
                for ancestor in self.ancestors(present):
                    if result.get(ancestor) == "absent":
                        raise LatrosError(
                            "Present phenotype contradicts explicitly absent ancestor"
                        )
        return result

    def resnik(self, left: str, right: str) -> tuple[float, str]:
        common = self.ancestors(left) & self.ancestors(right)
        if not common:
            return 0.0, ""
        ancestor = min(
            common, key=lambda key: (-self.ic.get(key, 0.0), self.concepts[key]["external_id"])
        )
        return self.ic.get(ancestor, 0.0), ancestor

    def evidence(
        self, assertion: dict[str, Any], observation: str, magnitude: float, match: str, reason: str
    ) -> dict[str, Any]:
        frequency: Frequency = assertion["frequency"]
        return dict(
            observation=self.concepts[observation]["external_id"],
            phenotype=self.concepts[assertion["phenotype_id"]]["external_id"],
            source_phenotype=assertion["source_phenotype_id"],
            matched_ancestor=self.concepts[match]["external_id"] if match else None,
            contribution=magnitude,
            reason=reason,
            assertion_ids=[assertion["id"]],
            frequency=frequency.model_dump(),
            frequency_estimate=frequency.estimate(),
            source_release=assertion["source_release_id"],
            provenance=orjson.loads(assertion["provenance_json"]),
        )

    def rank(self, case: ClinicalCase) -> list[dict[str, Any]]:
        observations = self.observations(case)
        present = sorted(k for k, value in observations.items() if value == "present")
        absent = sorted(k for k, value in observations.items() if value == "absent")
        if not present:
            return []
        # At least one direct ancestor/descendant annotation, never merely a shared root.
        candidates: set[str] = set()
        for query in present:
            candidates.update(self.annotated_diseases.get(query, set()))
            for ancestor in self.ancestors(query):
                candidates.update(self.direct_diseases.get(ancestor, set()))
        result: list[dict[str, Any]] = []
        for disease in sorted(candidates):
            rows = self.positive[disease]
            support: list[dict[str, Any]] = []
            contradictions: list[dict[str, Any]] = []
            for query in present:
                scored = [(self.resnik(query, a["phenotype_id"]), a) for a in rows]
                (score, match), best = min(scored, key=lambda pair: (-pair[0][0], pair[1]["id"]))
                if score > 0:
                    support.append(
                        self.evidence(
                            best,
                            query,
                            score / len(present),
                            match,
                            "maximum_resnik_divided_by_present_count",
                        )
                    )
                excluded = [
                    a
                    for a in self.assertions[disease]
                    if a["polarity"] == "excluded"
                    and (disease, a["phenotype_id"]) not in self.conflicts
                    and a["phenotype_id"] in self.ancestors(query)
                ]
                if excluded:
                    best = min(
                        excluded, key=lambda a: (-self.ic.get(a["phenotype_id"], 0), a["id"])
                    )
                    penalty = self.ic.get(query, 0.0) / len(present)
                    contradictions.append(
                        self.evidence(
                            best, query, -penalty, best["phenotype_id"], "source_exclusion"
                        )
                    )
            for query in absent:
                matches = [
                    a
                    for a in rows
                    if query in self.ancestors(a["phenotype_id"])
                    and (disease, a["phenotype_id"]) not in self.conflicts
                    and a["frequency"].estimate() is not None
                ]
                if matches:
                    best = min(matches, key=lambda a: (-a["frequency"].estimate(), a["id"]))
                    # Additive penalties: an unrelated absence with no frequency
                    # must not dilute an existing contradiction.
                    penalty = self.ic.get(query, 0.0) * best["frequency"].estimate()
                    contradictions.append(
                        self.evidence(
                            best, query, -penalty, query, "explicit_absence_frequency_penalty"
                        )
                    )
            unknowns = []
            for assertion in rows:
                key = assertion["phenotype_id"]
                if observations.get(key, "unknown") == "unknown":
                    unknowns.append(
                        dict(
                            concept_id=self.concepts[key]["external_id"],
                            information_content=self.ic.get(key, 0.0),
                            assertion_id=assertion["id"],
                        )
                    )
            unknowns.sort(key=lambda a: (-a["information_content"], a["concept_id"]))
            external = self.concepts[disease]["external_id"]
            result.append(
                dict(
                    _key=disease,
                    disease=external,
                    exact_mondo_mappings=sorted(self.exact_mondo[external]),
                    label=self.labels.get((disease, "fr"), self.concepts[disease]["label"]),
                    score=sum(e["contribution"] for e in support + contradictions),
                    score_type="compatibility",
                    supporting_evidence=support,
                    contradicting_evidence=contradictions,
                    important_unknowns=unknowns[:10],
                    frequency_conflicts=sorted(
                        self.concepts[key]["external_id"]
                        for d, key in self.conflicts
                        if d == disease
                    ),
                )
            )
        result.sort(key=lambda row: (-row["score"], row["disease"]))
        return result

    def diagnose(self, case: ClinicalCase) -> dict[str, Any]:
        ranked = self.rank(case)
        differential = []
        for rank, item in enumerate(ranked[:20], start=1):
            differential.append({k: v for k, v in item.items() if k != "_key"} | {"rank": rank})
        return dict(
            case_id=case.case_id,
            snapshot=self.snapshot,
            method="semantic_v1",
            score_type="compatibility",
            safety_status="not_evaluated",
            status="ranked" if ranked else "insufficient_supported_findings",
            ignored_context=["age", "sex"],
            candidate_count=len(ranked),
            differential=differential,
        )
