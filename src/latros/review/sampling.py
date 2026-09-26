"""Deterministic structural sampling, never a clinical sensitivity estimate."""

import hashlib
from collections import defaultdict


def _structural_sample(rows: list[dict[str, str]], size: int) -> list[str]:
    buckets: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        strata = (
            row.get("domains", "unclassified"),
            row.get("medlineplus_only", "false"),
            row.get("subject_mapping_status", ""),
            row.get("finding_frequency_band", ""),
            row.get("topic_id", ""),
        )
        buckets[strata].append(row)

    def digest(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    for values in buckets.values():
        values.sort(key=lambda row: digest(row["candidate_assertion_id"]))
    ordered = sorted(buckets, key=lambda key: digest("|".join(key)))
    selected: list[str] = []
    # Round-robin across structural strata rather than selecting only prolific diseases.
    while ordered and len(selected) < size:
        remaining = []
        for key in ordered:
            if len(selected) == size:
                break
            selected.append(buckets[key].pop(0)["candidate_assertion_id"])
            if buckets[key]:
                remaining.append(key)
        ordered = remaining
    return sorted(selected)


def control_sample(rows: list[dict[str, str]], status: str, size: int = 180) -> list[str]:
    eligible = [row for row in rows if row["auto_filter_decision"] == status]
    if status != "reject_from_auto_extraction":
        return _structural_sample(eligible, size)
    rules = sorted({row["auto_filter_rule"] for row in eligible})
    selected = []
    for index, rule in enumerate(rules):
        quota = size // len(rules) + (index < size % len(rules))
        selected.extend(
            _structural_sample([row for row in eligible if row["auto_filter_rule"] == rule], quota)
        )
    # Small synthetic strata may not meet their quota; fill without duplicates.
    remaining = [row for row in eligible if row["candidate_assertion_id"] not in selected]
    selected.extend(_structural_sample(remaining, size - len(selected)))
    return sorted(selected)
