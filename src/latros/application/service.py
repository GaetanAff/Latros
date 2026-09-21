"""Single orchestration layer for deterministic Latros research operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

from latros.application.models import (
    ApplicationCapabilities,
    CompatibleSelection,
    ConceptOption,
    SnapshotCapability,
    StrategyCapability,
)
from latros.clinical.loading import ClinicalCaseDocument
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import LatrosError, safe_id
from latros.knowledge.loading import load_manifest_document
from latros.knowledge.manifest_v2 import KnowledgeSnapshotManifestV2
from latros.knowledge.models_v2 import DesignationV2, ExternalIdentifierV2
from latros.knowledge.store import snapshot_path
from latros.knowledge.store_v2 import read_knowledge_v2, snapshot_path_v2
from latros.reasoning.engine import Engine
from latros.reasoning.general_v1 import GENERAL_V1_DESCRIPTOR, GeneralV1Strategy
from latros.reasoning.profiles import ReasoningProfile, load_reasoning_profile
from latros.reasoning.results_v2 import (
    DifferentialResultV2,
    QuestionResultV2,
    build_differential_v2,
    build_question_v2,
)
from latros.reasoning.semantic_v1_adapter import (
    HPO_SYSTEM,
    SEMANTIC_V1_DESCRIPTOR,
    SemanticV1Adapter,
)

OutputContractName = Literal["auto", "v1", "v2"]


class ResearchApplicationService:
    """Expose existing engines without moving clinical logic into the UI."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._catalog_cache: dict[tuple[str, str], list[ConceptOption]] = {}
        self._general_cache: dict[str, GeneralV1Strategy] = {}

    def diagnose(
        self,
        snapshot: str,
        case: ClinicalCaseDocument,
        strategy: str,
        output_contract: OutputContractName = "auto",
    ) -> dict[str, Any] | DifferentialResultV2:
        safe_id(snapshot)
        if strategy == "general_v1":
            if not isinstance(case, ClinicalCaseV2):
                raise LatrosError("general_v1 accepts only ClinicalCaseV2")
            if output_contract == "v1":
                raise LatrosError("general_v1 has no v1 output contract")
            return self._general_strategy(snapshot).diagnose(case)
        adapter = self._semantic_strategy(snapshot, strategy)
        if self._v2_output(case, output_contract):
            return build_differential_v2(self.root, case, adapter, self.profile(strategy, snapshot))
        return adapter.diagnose_legacy(case)

    def next_question(
        self,
        snapshot: str,
        case: ClinicalCaseDocument,
        strategy: str,
        output_contract: OutputContractName = "auto",
    ) -> dict[str, Any] | QuestionResultV2:
        safe_id(snapshot)
        if strategy == "general_v1":
            if not isinstance(case, ClinicalCaseV2):
                raise LatrosError("general_v1 accepts only ClinicalCaseV2")
            if output_contract == "v1":
                raise LatrosError("general_v1 has no v1 output contract")
            return self._general_strategy(snapshot).question(case)
        adapter = self._semantic_strategy(snapshot, strategy)
        if self._v2_output(case, output_contract):
            return build_question_v2(self.root, case, adapter, self.profile(strategy, snapshot))
        return adapter.next(case).payload

    def _general_strategy(self, snapshot: str) -> GeneralV1Strategy:
        """Load a large general snapshot once per application service process."""
        strategy = self._general_cache.get(snapshot)
        if strategy is None:
            strategy = GeneralV1Strategy(
                self.root,
                snapshot,
                self.profile("general_v1", snapshot),
            )
            self._general_cache[snapshot] = strategy
        return strategy

    def capabilities(self) -> ApplicationCapabilities:
        snapshots = self._snapshot_capabilities()
        strategies = [
            self._strategy_capability(SEMANTIC_V1_DESCRIPTOR),
            self._strategy_capability(GENERAL_V1_DESCRIPTOR),
        ]
        selections: list[CompatibleSelection] = []
        for snapshot in snapshots:
            if snapshot.schema_version is None:
                continue
            for strategy in ("semantic_v1", "general_v1"):
                try:
                    profile = self.profile(strategy, snapshot.snapshot_id)
                    compatible = profile.accepts_snapshot(
                        snapshot.snapshot_id, snapshot.schema_version
                    )
                except (LatrosError, OSError, ValueError):
                    compatible = False
                    profile = None
                if not compatible or profile is None:
                    continue
                available = snapshot.runtime_status == "available"
                selections.append(
                    CompatibleSelection(
                        snapshot_id=snapshot.snapshot_id,
                        strategy_id=strategy,
                        profile_id=profile.profile_id,
                        profile_sha256=profile.profile_sha256,
                        available=available,
                        reason=None if available else f"snapshot_runtime_{snapshot.runtime_status}",
                    )
                )
        return ApplicationCapabilities(
            snapshots=snapshots,
            strategies=strategies,
            compatible_selections=sorted(
                selections, key=lambda item: (item.snapshot_id, item.strategy_id)
            ),
        )

    def require_compatible(self, snapshot: str, strategy: str) -> CompatibleSelection:
        safe_id(snapshot)
        for item in self.capabilities().compatible_selections:
            if (item.snapshot_id, item.strategy_id) == (snapshot, strategy):
                if not item.available:
                    raise LatrosError(
                        f"Snapshot runtime is unavailable for {snapshot} + {strategy}"
                    )
                return item
        raise LatrosError(f"Incompatible snapshot and strategy: {snapshot} + {strategy}")

    def search_concepts(
        self, snapshot: str, strategy: str, query: str, *, limit: int = 20
    ) -> list[ConceptOption]:
        self.require_compatible(snapshot, strategy)
        if limit < 1 or limit > 50:
            raise LatrosError("Concept result limit must be between 1 and 50")
        normalized = query.strip().casefold()
        catalog = self._catalog(snapshot, strategy)
        matches = [
            item
            for item in catalog
            if not normalized
            or normalized in item.label.casefold()
            or normalized in item.code.casefold()
        ]
        return sorted(matches, key=lambda item: (item.label.casefold(), item.code))[:limit]

    def resolve_question_concept(
        self, snapshot: str, strategy: str, system: str, code: str
    ) -> ConceptOption:
        matches = [
            item
            for item in self._catalog(snapshot, strategy)
            if item.system == system and item.code == code
        ]
        if len(matches) != 1:
            raise LatrosError("Question concept has no unambiguous supported observation type")
        return matches[0]

    def profile(self, strategy: str, snapshot: str | None = None) -> ReasoningProfile:
        if strategy == "general_v1" and snapshot == "v0.5.0-dev-unreviewed":
            name = "general_v1-orl-unreviewed.json"
        elif strategy == "general_v1" and snapshot == "v0.7.0-general-dev-unreviewed":
            name = "general_v1-general-unreviewed.json"
        else:
            name = f"{strategy}.json"
        candidates = [
            Path(__file__).resolve().parents[3] / "profiles" / name,
            Path(__file__).resolve().parents[1] / "profiles" / name,
        ]
        for path in candidates:
            if path.is_file():
                return load_reasoning_profile(path)
        raise LatrosError(f"Reasoning profile is missing: {strategy}")

    def _snapshot_capabilities(self) -> list[SnapshotCapability]:
        manifest_root = self.root / "manifests"
        if not manifest_root.is_dir():
            return []
        capabilities: list[SnapshotCapability] = []
        for path in sorted(manifest_root.glob("*.json")):
            snapshot_id = path.stem
            try:
                safe_id(snapshot_id)
                manifest = load_manifest_document(self.root, snapshot_id)
                schema_version = (
                    manifest.schema_version
                    if isinstance(manifest, KnowledgeSnapshotManifestV2)
                    else int(manifest["schema_version"])
                )
                runtime = (
                    snapshot_path_v2(self.root, snapshot_id)
                    if schema_version == 2
                    else snapshot_path(self.root, snapshot_id)
                )
                runtime_status: Literal["available", "missing", "corrupt"] = (
                    "available" if runtime.is_file() else "missing"
                )
                payload = (
                    manifest.model_dump(mode="json")
                    if isinstance(manifest, KnowledgeSnapshotManifestV2)
                    else manifest
                )
                scope = payload.get("scope") or {}
                validation_status = payload.get("validation_status")
                research_unreviewed = validation_status == "unreviewed"
                capabilities.append(
                    SnapshotCapability(
                        snapshot_id=snapshot_id,
                        schema_version=schema_version,
                        runtime_status=runtime_status,
                        domain=scope.get("domain"),
                        population=scope.get("population"),
                        validation_status=validation_status,
                        intended_use=payload.get("intended_use"),
                        clinical_validation=payload.get("clinical_validation"),
                        human_review_complete=payload.get("human_review_complete"),
                        publishable=payload.get("publishable"),
                        research_unreviewed=research_unreviewed,
                        unreviewed_assertion_count=len(payload.get("unreviewed_assertion_ids", [])),
                        unreviewed_mapping_count=len(payload.get("unreviewed_mapping_ids", [])),
                        warnings=list(payload.get("warnings", [])),
                    )
                )
            except (LatrosError, OSError, ValueError, KeyError) as exc:
                capabilities.append(
                    SnapshotCapability(
                        snapshot_id=snapshot_id,
                        runtime_status="corrupt",
                        error=str(exc),
                    )
                )
        return capabilities

    def _catalog(self, snapshot: str, strategy: str) -> list[ConceptOption]:
        key = (snapshot, strategy)
        cached = self._catalog_cache.get(key)
        if cached is not None:
            return cached
        if strategy == "semantic_v1":
            engine = Engine(self.root, snapshot)
            catalog = []
            for concept_id, row in engine.concepts.items():
                if row["kind"] != "phenotype" or row["obsolete"]:
                    continue
                code = str(row["external_id"])
                label = engine.labels.get((concept_id, "fr")) or engine.labels.get(
                    (concept_id, "en"), str(row["label"])
                )
                catalog.append(
                    ConceptOption(
                        snapshot_id=snapshot,
                        strategy_id=strategy,
                        concept_id=concept_id,
                        system=HPO_SYSTEM,
                        code=code,
                        label=label,
                        language="fr" if (concept_id, "fr") in engine.labels else "en",
                        observation_kind="phenotype",
                    )
                )
        elif strategy == "general_v1":
            _, knowledge = read_knowledge_v2(self.root, snapshot)
            labels: dict[str, DesignationV2] = {}
            for designation_item in sorted(
                knowledge.designations,
                key=lambda item: (item.scope != "preferred", item.language != "en", item.text),
            ):
                labels.setdefault(designation_item.concept_id, designation_item)
            identifiers: dict[str, ExternalIdentifierV2] = {}
            for identifier_item in sorted(
                knowledge.external_identifiers,
                key=lambda item: (item.relation not in {"identity", "source_code"}, item.code),
            ):
                identifiers.setdefault(identifier_item.concept_id, identifier_item)
            kinds: dict[str, set[str]] = {}
            relation_kinds = {
                "has_symptom": "symptom",
                "has_sign": "sign",
                "has_exam_finding": "exam",
            }
            for assertion in knowledge.canonical_assertions:
                kind = relation_kinds.get(assertion.relation)
                if kind is not None and assertion.object.kind == "concept":
                    kinds.setdefault(assertion.object.concept_id, set()).add(kind)
            catalog = []
            for concept in knowledge.concepts:
                inferred = kinds.get(concept.concept_id, set())
                identifier = identifiers.get(concept.concept_id)
                designation = labels.get(concept.concept_id)
                if concept.status != "active" or not inferred or identifier is None:
                    continue
                # An HPO feature may be asserted as both reported symptom and observed sign.
                # Prefer the aggregatable sign path while keeping the concept searchable.
                kind = "sign" if "sign" in inferred else sorted(inferred)[0]
                if kind not in {"symptom", "sign", "exam", "vital"}:
                    continue
                catalog.append(
                    ConceptOption(
                        snapshot_id=snapshot,
                        strategy_id=strategy,
                        concept_id=concept.concept_id,
                        system=identifier.system,
                        code=identifier.code,
                        label=designation.text if designation else concept.primary_code,
                        language=designation.language if designation else "und",
                        observation_kind=cast(
                            Literal["phenotype", "symptom", "sign", "exam", "vital"], kind
                        ),
                    )
                )
        else:
            raise LatrosError(f"Unknown reasoning strategy: {strategy}")
        self._catalog_cache[key] = catalog
        return catalog

    @staticmethod
    def _strategy_capability(descriptor: Any) -> StrategyCapability:
        return StrategyCapability(
            strategy_id=descriptor.strategy_id,
            strategy_version=descriptor.strategy_version,
            accepted_case_versions=descriptor.accepted_case_versions,
            accepted_observation_types=descriptor.accepted_observation_types,
            score_scale_id=descriptor.score_scale_id,
            score_kind=descriptor.score_kind,
        )

    def _semantic_strategy(self, snapshot: str, strategy: str) -> SemanticV1Adapter:
        if strategy != "semantic_v1":
            raise LatrosError(f"Unknown reasoning strategy: {strategy}")
        return SemanticV1Adapter(Engine(self.root, snapshot))

    @staticmethod
    def _v2_output(case: ClinicalCaseDocument, output_contract: OutputContractName) -> bool:
        return output_contract == "v2" or (
            output_contract == "auto" and isinstance(case, ClinicalCaseV2)
        )
