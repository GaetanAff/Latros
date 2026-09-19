from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import orjson
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from latros.cli import app
from latros.clinical.v2 import ClinicalCaseV2, QuantityValue, SubjectContext, SymptomObservation
from latros.common import LatrosError, sha256
from latros.knowledge.curation import (
    CurationAssertionDraft,
    CurationMapping,
    CurationPackageManifest,
    ReviewDecision,
    ReviewerAttestation,
    audit_curation_package,
    export_approved_assertions,
    record_hash,
    write_review_workbook,
)
from latros.knowledge.research_unreviewed import build_unreviewed_research_snapshot
from latros.knowledge.store_v2 import read_knowledge_v2
from latros.reasoning.general_v1 import GeneralV1Strategy
from latros.reasoning.profiles import ReasoningProfile, reasoning_profile_hash


def _write_jsonl(path: Path, rows: Sequence[Any]) -> None:
    path.write_bytes(
        b"".join(
            orjson.dumps(
                row.model_dump(mode="json") if hasattr(row, "model_dump") else row,
                option=orjson.OPT_SORT_KEYS,
            )
            + b"\n"
            for row in rows
        )
    )


def _write_package(root: Path, *, approved: bool) -> Path:
    package = root / "curation/test-package"
    package.mkdir(parents=True)
    raw = root / "data/raw/test-curation"
    raw.mkdir(parents=True)
    terminology = raw / "terminology.json"
    clinical = raw / "clinical.html"
    segments = raw / "segments.json"
    terminology.write_bytes(b'{"fixture":"terminology"}\n')
    clinical.write_bytes(b"<html>invented clinical fixture</html>\n")
    segment_rows = [
        {
            "segment_id": "segment-1",
            "artifact_id": "clinical",
            "locator": "invented section 1",
            "text": "Invented finding 1.",
        },
        {
            "segment_id": "segment-2",
            "artifact_id": "clinical",
            "locator": "invented section 2",
            "text": "Invented finding 2.",
        },
    ]
    segments.write_bytes(
        orjson.dumps(
            {"schema_version": 1, "segments": segment_rows},
            option=orjson.OPT_SORT_KEYS,
        )
        + b"\n"
    )
    status = "approved" if approved else "pending_review"
    manifest = CurationPackageManifest(
        package_id="synthetic-curation-package",
        status="approved_for_snapshot" if approved else "pending_clinical_review",
        domain="invented test domain",
        population="invented adult population",
        candidate_codes=[{"system": "urn:latros:test", "code": "condition"}],
        segment_representation_path="data/raw/test-curation/segments.json",
        segment_representation_sha256=sha256(segments),
    )
    (package / "manifest.json").write_bytes(
        orjson.dumps(manifest.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS)
    )
    sources = [
        {
            "artifact_id": "terminology",
            "source_id": "invented-terminology",
            "role": "terminology",
            "title": "Invented terminology fixture",
            "source_url": "https://example.test/terminology",
            "release": "test-v1",
            "access_date": "2026-09-17",
            "local_path": "data/raw/test-curation/terminology.json",
            "sha256": sha256(terminology),
            "capture_kind": "full_capture",
            "license_name": "Synthetic fixture",
            "license_url": "https://example.test/license",
            "attribution": "Invented by Latros tests",
            "redistribution": "allowed_with_attribution",
            "legal_status": "approved_for_structured_reuse",
        },
        {
            "artifact_id": "clinical",
            "source_id": "invented-clinical",
            "role": "clinical_assertions",
            "title": "Invented clinical fixture",
            "source_url": "https://example.test/clinical",
            "release": "test-v1",
            "access_date": "2026-09-17",
            "local_path": "data/raw/test-curation/clinical.html",
            "sha256": sha256(clinical),
            "capture_kind": "full_capture",
            "license_name": "Synthetic fixture",
            "license_url": "https://example.test/license",
            "attribution": "Invented by Latros tests",
            "redistribution": "allowed_with_attribution",
            "legal_status": "approved_for_structured_reuse",
            "evidence_family_id": "invented-primary",
            "dependency_type": "primary",
            "upstream_reference": "invented-primary",
            "aggregatable": True,
        },
    ]
    (package / "sources.json").write_bytes(orjson.dumps(sources, option=orjson.OPT_SORT_KEYS))
    concepts = [
        {
            "concept": {"system": "urn:latros:test", "code": "condition"},
            "kind": "condition",
            "label": "Invented condition",
            "definition_scope": "Synthetic test only",
        },
        {
            "concept": {"system": "urn:latros:test", "code": "finding-1"},
            "kind": "symptom",
            "label": "Invented finding one",
            "definition_scope": "Synthetic test only",
        },
        {
            "concept": {"system": "urn:latros:test", "code": "finding-2"},
            "kind": "symptom",
            "label": "Invented finding two",
            "definition_scope": "Synthetic test only",
        },
    ]
    _write_jsonl(package / "concepts.jsonl", concepts)
    mapping = CurationMapping(
        mapping_id="mapping-1",
        source={"system": "urn:latros:test", "code": "condition"},
        target={"system": "urn:example:external", "code": "external-condition"},
        direction="source_to_target",
        relation="equivalent",
        resolution_status="resolved",
        source_artifact_id="terminology",
        record_locator="invented mapping record",
        provenance_note="Synthetic mapping for gate tests",
        confidence="high",
        review_status=status,
    )
    _write_jsonl(package / "mappings.jsonl", [mapping])
    assertions = [
        CurationAssertionDraft(
            assertion_id=f"assertion-{index}",
            condition_source="invented condition",
            subject={"system": "urn:latros:test", "code": "condition"},
            observation_source=f"invented finding {index}",
            object={"system": "urn:latros:test", "code": f"finding-{index}"},
            relation="has_symptom",
            population=["synthetic adults"],
            clinical_context="invented outpatient context",
            source_artifact_id="clinical",
            source_url="https://example.test/clinical",
            record_locator=f"invented section {index}",
            segment_id=f"segment-{index}",
            source_segment_sha256=sha256_text(f"Invented finding {index}."),
            access_date=date(2026, 9, 17),
            source_release="test-v1",
            evidence_family_id="invented-primary",
            dependency_type="primary",
            upstream_reference="invented-primary",
            curator={
                "curator_id": "synthetic-curator",
                "kind": "human",
                "method": "invented test curation",
            },
            review_status=status,
            mapping_notes="Synthetic mapping only",
            is_discriminating=index == 1,
            discriminating_against=["invented-comparator"] if index == 1 else [],
        )
        for index in (1, 2)
    ]
    _write_jsonl(package / "assertions.jsonl", assertions)
    reviewers: list[ReviewerAttestation] = []
    reviews: list[ReviewDecision] = []
    if approved:
        attestations = root / "review-attestations"
        attestations.mkdir()
        for reviewer_id in ("synthetic-clinician", "synthetic-mapper"):
            attestation = attestations / f"{reviewer_id}.txt"
            attestation.write_text("Synthetic attestation for automated tests.\n", encoding="utf-8")
            reviewers.append(
                ReviewerAttestation(
                    reviewer_id=reviewer_id,
                    roles=["clinical", "mapping"]
                    if reviewer_id == "synthetic-clinician"
                    else ["mapping"],
                    qualified_clinician=reviewer_id == "synthetic-clinician",
                    attestation_path=f"review-attestations/{reviewer_id}.txt",
                    attestation_sha256=sha256(attestation),
                    verified_by="synthetic-test-harness",
                    verification_date=date(2026, 9, 17),
                )
            )
        reviewed_at = datetime(2026, 9, 17, 12, tzinfo=UTC)
        reviews.append(
            ReviewDecision(
                item_type="mapping",
                item_id=mapping.mapping_id,
                item_sha256=record_hash(mapping),
                reviewer_id="synthetic-mapper",
                decision="approved",
                reviewed_at=reviewed_at,
            )
        )
        for assertion in assertions:
            for reviewer_id in ("synthetic-clinician", "synthetic-mapper"):
                reviews.append(
                    ReviewDecision(
                        item_type="assertion",
                        item_id=assertion.assertion_id,
                        item_sha256=record_hash(assertion),
                        reviewer_id=reviewer_id,
                        decision="approved",
                        reviewed_at=reviewed_at,
                    )
                )
    _write_jsonl(package / "reviewers.jsonl", reviewers)
    _write_jsonl(package / "reviews.jsonl", reviews)
    return package


def sha256_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_pending_package_is_technically_ready_but_not_publishable(tmp_path: Path) -> None:
    package = _write_package(tmp_path, approved=False)

    report = audit_curation_package(tmp_path, package)

    assert report.status == "blocked"
    assert report.technical_status == "ready_for_human_review"
    assert all(candidate.content_threshold_met for candidate in report.candidates)
    assert {blocker.code for blocker in report.blockers} >= {
        "assertion_review_incomplete",
        "mapping_review_incomplete",
        "package_status_pending",
    }
    with pytest.raises(LatrosError, match="not publishable"):
        export_approved_assertions(tmp_path, package, tmp_path / "approved.jsonl")
    workbook = tmp_path / "review.md"
    write_review_workbook(package, workbook)
    review_text = workbook.read_text(encoding="utf-8")
    assert "assertion-1" in review_text
    assert "Blank reviewer columns are intentional" in review_text


def test_attested_double_review_opens_gate_and_exports(tmp_path: Path) -> None:
    package = _write_package(tmp_path, approved=True)

    report = audit_curation_package(tmp_path, package)
    output = tmp_path / "approved.jsonl"
    exported = export_approved_assertions(tmp_path, package, output)

    assert report.status == "ready_for_publication"
    assert report.technical_status == "publication_ready"
    assert report.blockers == []
    assert len(exported) == 2
    assert len(output.read_bytes().splitlines()) == 2


def test_changed_record_or_artifact_closes_gate(tmp_path: Path) -> None:
    package = _write_package(tmp_path, approved=True)
    assertions = package / "assertions.jsonl"
    payload = orjson.loads(assertions.read_bytes().splitlines()[0])
    payload["mapping_notes"] = "Changed after review"
    payload["record_locator"] = "wrong section"
    payload["source_release"] = "wrong release"
    lines = assertions.read_bytes().splitlines()
    lines[0] = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    assertions.write_bytes(b"\n".join(lines) + b"\n")

    report = audit_curation_package(tmp_path, package)

    assert report.status == "blocked"
    assert any(item.code == "assertion_review_incomplete" for item in report.blockers)
    assert any(item.code == "assertion_segment_locator" for item in report.blockers)
    assert any(item.code == "assertion_source_version_mismatch" for item in report.blockers)

    clinical = tmp_path / "data/raw/test-curation/clinical.html"
    clinical.write_bytes(b"changed\n")
    report = audit_curation_package(tmp_path, package)
    assert any(item.code == "source_artifact_invalid" for item in report.blockers)


def test_therapeutic_assertion_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Therapeutic content"):
        CurationAssertionDraft.model_validate(
            {
                "assertion_id": "treatment",
                "condition_source": "invented",
                "subject": {"system": "urn:test", "code": "condition"},
                "observation_source": "invented",
                "object": {"system": "urn:test", "code": "finding"},
                "relation": "has_symptom",
                "population": ["adult"],
                "clinical_context": "test",
                "source_artifact_id": "clinical",
                "source_url": "https://example.test/clinical",
                "record_locator": "section",
                "segment_id": "segment",
                "source_segment_sha256": "0" * 64,
                "access_date": "2026-09-17",
                "source_release": "test",
                "evidence_family_id": "test",
                "dependency_type": "primary",
                "upstream_reference": "test",
                "curator": {
                    "curator_id": "test",
                    "kind": "human",
                    "method": "test",
                },
                "mapping_notes": "test",
                "therapeutic_content": True,
            }
        )


def test_cli_require_publishable_fails_for_pending_package(tmp_path: Path) -> None:
    package = _write_package(tmp_path, approved=False)
    result = CliRunner().invoke(
        app,
        [
            "--root",
            str(tmp_path),
            "curation",
            "audit",
            "--package",
            str(package),
            "--report",
            "gate-report.json",
            "--require-publishable",
        ],
    )

    assert result.exit_code != 0
    assert (tmp_path / "gate-report.json").is_file()
    assert isinstance(result.exception, LatrosError)
    assert "Curation publication gate is blocked" in str(result.exception)


def test_unreviewed_snapshot_requires_explicit_override_and_safe_id(tmp_path: Path) -> None:
    package = _write_package(tmp_path, approved=False)
    before_assertions = (package / "assertions.jsonl").read_bytes()
    before_mappings = (package / "mappings.jsonl").read_bytes()
    before_reviewers = (package / "reviewers.jsonl").read_bytes()
    before_reviews = (package / "reviews.jsonl").read_bytes()

    with pytest.raises(LatrosError, match="pass --allow-unreviewed"):
        build_unreviewed_research_snapshot(
            tmp_path,
            package,
            "synthetic-dev-unreviewed",
            allow_unreviewed_research_data=False,
        )
    with pytest.raises(LatrosError, match="ending in -dev-unreviewed"):
        build_unreviewed_research_snapshot(
            tmp_path,
            package,
            "v0.5.0",
            allow_unreviewed_research_data=True,
        )

    manifest = build_unreviewed_research_snapshot(
        tmp_path,
        package,
        "synthetic-dev-unreviewed",
        allow_unreviewed_research_data=True,
    )

    assert manifest.validation_status == "unreviewed"
    assert manifest.intended_use == "local_research_only"
    assert manifest.clinical_validation is False
    assert manifest.human_review_complete is False
    assert manifest.publishable is False
    assert manifest.research_override_used is True
    assert manifest.reviewer_count == 0
    assert manifest.unreviewed_assertion_ids == ["assertion-1", "assertion-2"]
    assert manifest.unreviewed_mapping_ids == ["mapping-1"]
    assert (package / "assertions.jsonl").read_bytes() == before_assertions
    assert (package / "mappings.jsonl").read_bytes() == before_mappings
    assert (package / "reviewers.jsonl").read_bytes() == before_reviewers == b""
    assert (package / "reviews.jsonl").read_bytes() == before_reviews == b""


def test_cli_separates_official_and_unreviewed_build_paths(tmp_path: Path) -> None:
    package = _write_package(tmp_path, approved=False)
    runner = CliRunner()
    common = ["--root", str(tmp_path), "data", "build"]

    default_refusal = runner.invoke(
        app,
        [*common, "--snapshot", "synthetic-dev-unreviewed", "--curation-package", str(package)],
    )
    official_override = runner.invoke(
        app,
        [
            *common,
            "--snapshot",
            "v0.5.0",
            "--curation-package",
            str(package),
            "--allow-unreviewed-research-data",
        ],
    )
    official_gate = runner.invoke(
        app,
        [*common, "--snapshot", "v0.5.0", "--curation-package", str(package)],
    )
    experimental = runner.invoke(
        app,
        [
            *common,
            "--snapshot",
            "synthetic-dev-unreviewed",
            "--curation-package",
            str(package),
            "--allow-unreviewed-research-data",
        ],
    )

    assert default_refusal.exit_code != 0
    assert "refused by default" in str(default_refusal.exception)
    assert official_override.exit_code != 0
    assert "never be used" in str(official_override.exception)
    assert official_gate.exit_code != 0
    assert "publication gate is blocked" in str(official_gate.exception)
    assert experimental.exit_code == 0
    assert "UNREVIEWED LOCAL RESEARCH DATA" in experimental.stderr
    assert orjson.loads(experimental.stdout)["publishable"] is False


def test_general_v1_result_and_question_cannot_hide_unreviewed_data(tmp_path: Path) -> None:
    package = _write_package(tmp_path, approved=False)
    snapshot = "synthetic-dev-unreviewed"
    build_unreviewed_research_snapshot(
        tmp_path,
        package,
        snapshot,
        allow_unreviewed_research_data=True,
    )
    manifest, knowledge = read_knowledge_v2(tmp_path, snapshot)
    profile_payload: dict[str, Any] = {
        "schema_version": 1,
        "profile_id": "general_v1-orl-unreviewed",
        "strategy_id": "general_v1",
        "strategy_version": "1",
        "accepted_observation_types": ["symptom", "sign", "exam", "vital"],
        "accepted_relations": ["has_symptom", "has_sign", "has_exam_finding"],
        "score_scale": {
            "scale_id": "general_v1.compatibility",
            "kind": "compatibility",
            "description": "Synthetic unreviewed compatibility, never a probability",
            "calibrated": False,
        },
        "parameters": {
            "minimum_age_years": 18,
            "minimum_assessed_findings": 2,
            "minimum_coverage_ratio": 0.5,
            "family_weights": {"invented-primary": 1.0},
            "allow_unlisted_evidence_families": False,
        },
        "aggregation_rules": [],
        "coverage_rules": [],
        "out_of_scope_rules": [],
        "abstention_rules": [],
        "compatible_snapshot_schema_versions": [2],
        "compatible_snapshot_ids": [snapshot],
        "profile_sha256": "0" * 64,
    }
    profile_payload["profile_sha256"] = reasoning_profile_hash(profile_payload)
    strategy = GeneralV1Strategy(
        tmp_path, snapshot, ReasoningProfile.model_validate(profile_payload)
    )
    observations = [
        _unreviewed_symptom(1, "finding-1"),
        _unreviewed_symptom(2, "finding-2"),
    ]
    case = ClinicalCaseV2(
        case_id="unreviewed-research-case",
        subject_context=SubjectContext(
            age=QuantityValue(
                value=30,
                unit="year",
                system="http://unitsofmeasure.org",
                code="a",
            )
        ),
        observations=observations,
    )

    result = strategy.diagnose(case)
    question = strategy.question(case)

    assert result.status == "ranked"
    assert result.research_unreviewed is True
    assert result.safety.status == "not_evaluated"
    assert result.candidates[0].aggregate.kind == "compatibility"
    assert result.candidates[0].aggregate.calibrated is False
    assert result.run_receipt.snapshot_id == snapshot
    assert result.run_receipt.knowledge_validation_status == "unreviewed"
    assert result.run_receipt.unreviewed_assertion_count == 2
    assert result.run_receipt.unreviewed_mapping_count == 1
    assert result.run_receipt.research_override_used is True
    assert question.research_unreviewed is True
    assert question.run_receipt.research_unreviewed is True
    assert question.safety.status == "not_evaluated"
    assert all(
        item.evidence["review_status"] == "pending_review" for item in knowledge.concept_mappings
    )
    assert all(
        item.raw_value["review_status"] == "pending_review" for item in knowledge.source_assertions
    )
    assert manifest.reviewer_count == 0


def _unreviewed_symptom(index: int, code: str) -> SymptomObservation:
    return SymptomObservation.model_validate(
        {
            "observation_id": f"unreviewed-observation-{index}",
            "concept": {
                "concept_id": f"orl:{code}",
                "coding": {"system": "urn:latros:test", "code": code},
            },
            "clinical_status": "present",
            "evaluation_status": "assessed",
            "acquisition_method": "reported",
            "provenance": {
                "provenance_id": f"unreviewed-provenance-{index}",
                "origin_type": "patient_report",
            },
        }
    )
