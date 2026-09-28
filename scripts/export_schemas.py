"""Regenerate reviewable contract schemas, or fail if tracked schemas are stale."""

import argparse
from pathlib import Path

from latros.clinical.models import ClinicalCase
from latros.clinical.v2 import ClinicalCaseV2
from latros.common import encoded
from latros.knowledge.candidates import CandidateAssertion
from latros.knowledge.curation import (
    CurationAssertionDraft,
    CurationMapping,
    CurationPackageManifest,
    CurationPublicationReport,
    ReviewDecision,
    ReviewerAttestation,
    SourceArtifactReceipt,
)
from latros.knowledge.frequency import Frequency
from latros.knowledge.importers import TABLES
from latros.knowledge.importers_v2 import CuratedAssertionRecord
from latros.knowledge.manifest_v2 import KnowledgeSnapshotManifestV2
from latros.knowledge.medlineplus import MedlinePlusTopicRecord
from latros.knowledge.models_v2 import CANONICAL_TABLES_V2, CanonicalKnowledgeV2
from latros.reasoning.interfaces import ReasoningStrategyDescriptor
from latros.reasoning.profiles import ReasoningProfile
from latros.reasoning.results_v2 import DifferentialResultV2, QuestionResultV2, RunReceipt
from latros.sources.registry import Registry
from latros.sources.registry_v2 import RegistryV2
from latros.ui.models import ResearchSession
from latros.ui.patient_context import PatientContext
from latros.ui.refinements import RefinementAnswer, SymptomRefinementDefinition


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "schemas"
    documents = {
        "clinical-case.schema.json": ClinicalCase.model_json_schema(),
        "clinical-case-v2.schema.json": ClinicalCaseV2.model_json_schema(),
        "frequency.schema.json": Frequency.model_json_schema(),
        "source-registry.schema.json": Registry.model_json_schema(),
        "source-registry-v2.schema.json": RegistryV2.model_json_schema(),
        "canonical-tables.json": {"schema": "canonical_v1", "tables": TABLES},
        "knowledge-model-v2.schema.json": CanonicalKnowledgeV2.model_json_schema(),
        "knowledge-snapshot-manifest-v2.schema.json": (
            KnowledgeSnapshotManifestV2.model_json_schema()
        ),
        "curated-assertion-record-v1.schema.json": CuratedAssertionRecord.model_json_schema(),
        "candidate-assertion-v1.schema.json": CandidateAssertion.model_json_schema(),
        "medlineplus-topic-record-v1.schema.json": MedlinePlusTopicRecord.model_json_schema(),
        "curation-package-manifest-v1.schema.json": CurationPackageManifest.model_json_schema(),
        "curation-source-artifact-v1.schema.json": SourceArtifactReceipt.model_json_schema(),
        "curation-assertion-draft-v1.schema.json": CurationAssertionDraft.model_json_schema(),
        "curation-mapping-v1.schema.json": CurationMapping.model_json_schema(),
        "curation-reviewer-attestation-v1.schema.json": (ReviewerAttestation.model_json_schema()),
        "curation-review-decision-v1.schema.json": ReviewDecision.model_json_schema(),
        "curation-publication-report-v1.schema.json": (
            CurationPublicationReport.model_json_schema()
        ),
        "canonical-tables-v2.json": {
            "schema": "canonical_v2",
            "tables": CANONICAL_TABLES_V2,
        },
        "reasoning-profile.schema.json": ReasoningProfile.model_json_schema(),
        "reasoning-strategy-descriptor.schema.json": (
            ReasoningStrategyDescriptor.model_json_schema()
        ),
        "differential-result-v2.schema.json": DifferentialResultV2.model_json_schema(),
        "question-result-v2.schema.json": QuestionResultV2.model_json_schema(),
        "run-receipt.schema.json": RunReceipt.model_json_schema(),
        "ui-session-v1.schema.json": ResearchSession.model_json_schema(),
        "patient-context-v1.schema.json": PatientContext.model_json_schema(),
        "symptom-refinement-v1.schema.json": SymptomRefinementDefinition.model_json_schema(),
        "symptom-refinement-answer-v1.schema.json": RefinementAnswer.model_json_schema(),
    }
    for name, document in documents.items():
        path = root / name
        content = encoded(document)
        if args.check:
            if not path.exists() or path.read_bytes() != content:
                raise SystemExit(f"Outdated schema: {path}; run scripts/export_schemas.py")
        else:
            root.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


if __name__ == "__main__":
    main()
