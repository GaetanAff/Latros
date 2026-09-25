"""Audit real G2/candidate extraction signals before changing extraction rules."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from replay_v07_medlineplus_candidates import SNAPSHOT, replay

from latros.knowledge.medlineplus import parse_medlineplus_topics
from latros.knowledge.medlineplus_quality import (
    audit_signals,
    load_condition_terms,
    locator_parts,
)
from latros.knowledge.store_v2 import snapshot_path_v2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output", type=Path, default=Path("data/staging/v0.7-g4/baseline-audit.json")
    )
    args = parser.parse_args()
    root = args.root.resolve()
    candidates = replay(root)
    condition_terms = load_condition_terms(snapshot_path_v2(root, SNAPSHOT))
    topics = {
        item.topic_id: item
        for item in parse_medlineplus_topics(
            root / "data/raw/medlineplus/2026-09-19/mplus_topics_compressed_2026-09-19.zip"
        )
    }
    sample_path = root / "data/staging/v0.7-g/g2-medline-assertion-review.csv"
    with sample_path.open(encoding="utf-8", newline="") as handle:
        sample_ids = {row["candidate_assertion_id"] for row in csv.DictReader(handle)}
    if len(sample_ids) != 120:
        raise ValueError("Pinned G2 sample must contain 120 distinct assertions")
    by_class: Counter[str] = Counter()
    sample_by_class: Counter[str] = Counter()
    examples: dict[str, list[dict[str, str]]] = {}
    for candidate in candidates:
        topic_id, _ = locator_parts(candidate)
        flags, occurrences = audit_signals(
            candidate, topics[topic_id], condition_terms=condition_terms
        )
        for flag in flags:
            by_class[flag] += 1
            if candidate.candidate_assertion_id in sample_ids:
                sample_by_class[flag] += 1
            if len(examples.setdefault(flag, [])) < 5:
                examples[flag].append(
                    {
                        "candidate_id": candidate.candidate_assertion_id,
                        "topic_id": topic_id,
                        "topic": candidate.subject_text,
                        "finding": candidate.object_text,
                        "section": occurrences[0].section if occurrences else "",
                        "context": occurrences[0].text[:220] if occurrences else "",
                    }
                )
    report = {
        "baseline_candidate_count": len(candidates),
        "baseline_technically_eligible": sum(item.technically_eligible for item in candidates),
        "g2_sample_size": len(sample_ids),
        "signals_all_candidates": dict(sorted(by_class.items())),
        "signals_g2_sample": dict(sorted(sample_by_class.items())),
        "examples": dict(sorted(examples.items())),
        "note": "Signals overlap and are not clinical judgments or automatic approvals.",
    }
    output = (root / args.output).resolve()
    staging = (root / "data/staging").resolve()
    if not output.is_relative_to(staging):
        raise ValueError("Audit output must remain under data/staging")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "examples"}))


if __name__ == "__main__":
    main()
