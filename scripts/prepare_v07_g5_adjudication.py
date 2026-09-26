"""Prepare pinned G1/G2/G4 human-review inputs offline without making decisions."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import duckdb
import orjson
from audit_v07_general_quality import _prepare
from build_v07_g4_medlineplus_candidates import _csv, _write_once
from lxml import html
from replay_v07_medlineplus_candidates import BASELINE_SHA256, CONTENT_SHA256, SNAPSHOT

from latros.common import LatrosError, sha256
from latros.knowledge.candidates import CandidateAssertion
from latros.knowledge.medlineplus import parse_medlineplus_topics
from latros.knowledge.medlineplus_quality import locator_parts, visible_occurrences
from latros.knowledge.store_v2 import load_manifest_v2, snapshot_path_v2
from latros.review.g07 import EXPORTS
from latros.review.sampling import control_sample

G4_SHA256 = "cf4938f0ded4c341137cf2fb6f24571779c5018d50fcde8728a3e8aa0e8824d6"
RAW_SHA256 = "4b52e1a2c4c499d363dfbff1776875b53a695b315e7761e1c283b223b675ed74"


def prepare(root: Path, destination: Path) -> dict[str, object]:
    root = root.resolve()
    destination = (root / destination).resolve()
    if not destination.is_relative_to((root / "data/staging").resolve()):
        raise LatrosError("G5 exports must remain under data/staging")
    if load_manifest_v2(root, SNAPSHOT).content_sha256 != CONTENT_SHA256:
        raise LatrosError("G5 snapshot mismatch")
    baseline = root / "data/staging/general" / SNAPSHOT / "candidate_assertions.jsonl"
    ledger = root / "data/staging/v0.7-g4/quality-v2-experimental/candidate_decisions.jsonl"
    raw = root / "data/raw/medlineplus/2026-09-19/mplus_topics_compressed_2026-09-19.zip"
    for path, expected in ((baseline, BASELINE_SHA256), (ledger, G4_SHA256), (raw, RAW_SHA256)):
        if not path.is_file() or sha256(path) != expected:
            raise LatrosError(f"G5 pinned input mismatch: {path.name}")
    candidates = {
        item.candidate_assertion_id: item
        for item in (
            CandidateAssertion.model_validate_json(line)
            for line in baseline.read_bytes().splitlines()
        )
    }
    decisions = [orjson.loads(line) for line in ledger.read_bytes().splitlines()]
    if len(candidates) != 7736 or len(decisions) != 7736:
        raise LatrosError("G5 requires all 7736 historical/G4 candidates")
    topics = {topic.topic_id: topic for topic in parse_medlineplus_topics(raw)}
    domains: dict[str, set[str]] = defaultdict(set)
    with duckdb.connect(str(snapshot_path_v2(root, SNAPSHOT)), read_only=True) as connection:
        _prepare(connection, baseline)
        labels = dict(connection.execute("SELECT concept_id,label_text FROM labels").fetchall())
        for disease_id, domain in connection.execute(
            "SELECT disease_id,domain FROM domain_assignment"
        ).fetchall():
            domains[disease_id].add(domain)
        medline_only = {
            row[0]
            for row in connection.execute(
                "SELECT disease_id FROM sa GROUP BY disease_id "
                "HAVING count(DISTINCT source_release)=1 "
                "AND min(source_release)='medlineplus:2026-09-19'"
            ).fetchall()
        }
    finding_counts = Counter(item.object_text for item in candidates.values())
    rows: list[dict[str, str]] = []
    for decision in decisions:
        item = candidates[decision["candidate_assertion_id"]]
        topic_id, summary_index = locator_parts(item)
        topic = topics[topic_id]
        occurrences = visible_occurrences(topic, summary_index, item.object_text)
        subject = item.subject_mapping
        finding = item.object_mapping
        row = {key: str(value) for key, value in decision.items() if key != "signals"}
        row.update(
            {
                "finding_code": finding.code if finding else "",
                "finding_source_label": labels.get(finding.concept_id or "", "") if finding else "",
                "disease_code": subject.code if subject else "",
                "historical_state": item.review_status,
                "historical_extractor": orjson.dumps(item.extraction.model_dump()).decode(),
                "subject_mapping_provenance": orjson.dumps(subject.model_dump()).decode()
                if subject
                else "",
                "object_mapping_provenance": orjson.dumps(finding.model_dump()).decode()
                if finding
                else "",
                "historical_candidate": orjson.dumps(item.model_dump(mode="json")).decode(),
                "g4_signals": orjson.dumps(decision["signals"]).decode(),
                "match_contexts": orjson.dumps(
                    [{"text": match.text, "section": match.section} for match in occurrences]
                ).decode(),
                "source_text": " ".join(
                    html.fragment_fromstring(topic.summaries[summary_index], create_parent="div")
                    .text_content()
                    .split()
                ),
                "occurrence_count": str(len(occurrences)),
                "domains": "|".join(sorted(domains.get(subject.concept_id or "", {"unclassified"})))
                if subject
                else "unclassified",
                "medlineplus_only": str(
                    bool(subject and subject.concept_id in medline_only)
                ).lower(),
                "finding_frequency_band": "frequent_in_candidates"
                if finding_counts[item.object_text] >= 20
                else "less_frequent_in_candidates",
            }
        )
        # Identity, taxonomy and final decisions are never supplied by preparation.
        for key in row:
            if key.startswith("human_"):
                row[key] = ""
        rows.append(row)
    priority = {"needs_human_review": 0, "auto_keep": 1, "reject_from_auto_extraction": 2}
    rows.sort(
        key=lambda row: (priority[row["auto_filter_decision"]], row["candidate_assertion_id"])
    )
    counts = Counter(row["auto_filter_decision"] for row in rows)
    if dict(counts) != {
        "needs_human_review": 4056,
        "auto_keep": 2212,
        "reject_from_auto_extraction": 1468,
    }:
        raise LatrosError("G5 G4 status counts mismatch")
    samples = {
        "rejected_control": control_sample(rows, "reject_from_auto_extraction"),
        "retained_control": control_sample(rows, "auto_keep"),
    }
    hashes = {}
    for filename, expected in EXPORTS.values():
        content = (root / "data/staging/v0.7-g" / filename).read_bytes()
        if sha256(root / "data/staging/v0.7-g" / filename) != expected:
            raise LatrosError(f"G1/G2 source export mismatch: {filename}")
        hashes[filename] = _write_once(destination / filename, content)
    hashes["g4-adjudication-review.csv"] = _write_once(
        destination / "g4-adjudication-review.csv", _csv(rows, tuple(rows[0]))
    )
    sampling_hash = _write_once(
        destination / "control-samples.json",
        orjson.dumps(samples, option=orjson.OPT_SORT_KEYS) + b"\n",
    )
    summary = {
        "schema_version": 2,
        "snapshot": SNAPSHOT,
        "snapshot_sha256": CONTENT_SHA256,
        "files_sha256": hashes,
        "sampling_sha256": sampling_hash,
        "g4_counts": dict(counts),
        "sample_sizes": {key: len(values) for key, values in samples.items()},
        "rejected_sample_rules": dict(
            Counter(
                row["auto_filter_rule"]
                for row in rows
                if row["candidate_assertion_id"] in samples["rejected_control"]
            )
        ),
        "clinical_validation": False,
        "publishable": False,
        "research_unreviewed": True,
        "applies_to_snapshot": False,
        "human_decisions": 0,
    }
    _write_once(
        destination / "summary.json", orjson.dumps(summary, option=orjson.OPT_SORT_KEYS) + b"\n"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=Path("data/staging/v0.7-g5"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.output_dir), sort_keys=True))
