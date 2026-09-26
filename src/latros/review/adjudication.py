"""Human-only G5 decisions and adjudication, isolated from clinical knowledge."""

from __future__ import annotations

import os
import secrets
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import orjson
from fastapi import FastAPI, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from latros.common import LatrosError
from latros.review.g07 import (
    EXPORTS,
    SNAPSHOT,
    SNAPSHOT_SHA256,
    DecisionInput,
    ReviewStore,
    _canonical,
    _digest,
    create_review_app,
)

Category = Literal[
    "correct_clinical_manifestation",
    "wrong_semantic_role",
    "disease_self_reference",
    "modifier",
    "negated",
    "family_history",
    "risk_or_prevention",
    "treatment_or_procedure_context",
    "other_disease_mention",
    "mapping_problem",
    "ambiguous",
    "insufficient_context",
    "other",
]
FinalDecision = Literal["approve", "reject", "defer", "needs_second_review"]
G5_EXPORTS = {
    **EXPORTS,
    "g4": (
        "g4-adjudication-review.csv",
        "dd246087f88e36ff549aff5d626afc43888aab9c3290301fd8c0fcc71b112ca0",
    ),
}
SAMPLES_SHA256 = "4ce7ffd24e2a1c7bf72e3c08a071ff85f2c054f8646bc252a9d456f2e13f43d6"


class HumanDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    dataset: Literal["g1", "g2_medline", "g2_upstream", "g4"]
    index: int = Field(ge=0)
    row_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    stage: Literal["review", "adjudication"]
    category: Category
    final_decision: FinalDecision
    reviewer_name: str = Field(min_length=3, max_length=160)
    reviewer_id: str = Field(min_length=2, max_length=160)
    attests_identity: Literal[True]
    qualification_self_attested: str = Field(default="", max_length=500)
    comment: str = Field(default="", max_length=2000)
    mapping_relation: Literal["exact", "equivalent"] | None = None
    basis_event_hashes: list[str] = Field(default_factory=list)


def _latest_reviews(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = {
        event["reviewer_id"]: event
        for event in events
        if event.get("schema_version") == 2 and event.get("stage") == "review"
    }
    return [current[key] for key in sorted(current)]


def agreement(events: list[dict[str, Any]]) -> dict[str, Any]:
    reviews = _latest_reviews(events)
    basis = sorted(event["event_hash"] for event in reviews)
    adjudications = [
        event
        for event in events
        if event.get("stage") == "adjudication" and sorted(event["basis_event_hashes"]) == basis
    ]
    decisions = {event["final_decision"] for event in reviews}
    categories = {event["category"] for event in reviews}
    mappings = {event.get("mapping_relation") for event in reviews}
    deferred = bool(decisions & {"defer", "needs_second_review"})
    agreed = (
        len(reviews) >= 2
        and len(decisions) == len(categories) == len(mappings) == 1
        and not deferred
    )
    disagreed = len(reviews) >= 2 and not agreed and not deferred
    final = adjudications[-1] if adjudications else None
    return {
        "reviewed": bool(reviews),
        "reviewer_count": len(reviews),
        "agreement": agreed,
        "disagreement": disagreed,
        "deferred": deferred
        or bool(final and final["final_decision"] in {"defer", "needs_second_review"}),
        "adjudicated": final is not None,
        "unresolved": not agreed
        and (final is None or final["final_decision"] in {"defer", "needs_second_review"}),
        "basis_event_hashes": basis,
        "adjudication": final,
    }


def _search_text(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )


class AdjudicationStore(ReviewStore):
    def record(self, decision: DecisionInput) -> dict[str, Any]:
        raise LatrosError("G5 requires the explicit v2 taxonomy and final decision")

    def export(self) -> bytes:
        return self.export_kind("individual_decisions")

    def __init__(
        self,
        root: Path,
        exports_dir: Path,
        *,
        expected_exports: dict[str, tuple[str, str]] | None = None,
        expected_samples_sha256: str = SAMPLES_SHA256,
    ) -> None:
        super().__init__(root, exports_dir, expected_exports=expected_exports or G5_EXPORTS)
        self.samples_path = self.exports_dir / "control-samples.json"
        self.samples_hash = expected_samples_sha256
        if _digest(self.samples_path.read_bytes()) != self.samples_hash:
            raise LatrosError("G5 control sample hash mismatch")
        self.samples: dict[str, list[str]] = orjson.loads(self.samples_path.read_bytes())
        ids = {row["candidate_assertion_id"] for row in self.rows["g4"]}
        for values in self.samples.values():
            if len(set(values)) != len(values) or not set(values) <= ids:
                raise LatrosError("G5 sample has duplicate or unknown candidates")

    def _assert_exports_unchanged(self) -> None:
        super()._assert_exports_unchanged()
        if _digest(self.samples_path.read_bytes()) != self.samples_hash:
            raise LatrosError("G5 control sample changed after startup")

    def _events(self) -> list[dict[str, Any]]:
        events = super()._events()
        for event in events:
            if event.get("schema_version") == 2:
                HumanDecisionInput.model_validate(
                    {key: event[key] for key in HumanDecisionInput.model_fields if key in event}
                )
                if (
                    event["source_csv_sha256"]
                    != self.hashes[self.expected_exports[event["dataset"]][0]]
                ):
                    raise LatrosError("G5 audit source hash mismatch")
        return events

    def _grouped_events(self) -> dict[tuple[str, int], list[dict[str, Any]]]:
        grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
        for event in self._events():
            grouped[(event["dataset"], event["index"])].append(event)
        return grouped

    def human_item(self, dataset: str, index: int, reviewer_id: str, stage: str) -> dict[str, Any]:
        with self.lock:
            item = super().item(dataset, index)
            events = item["history"]
            state = agreement(events)
            # Blinding is procedural in a self-attested local tool, not authentication.
            item["history"] = (
                events
                if stage == "adjudication"
                else [event for event in events if event.get("reviewer_id") == reviewer_id]
            )
            item["reviewer_count"] = state["reviewer_count"]
            item["basis_event_hashes"] = (
                state["basis_event_hashes"] if stage == "adjudication" else []
            )
            return item

    def record_human(self, decision: HumanDecisionInput) -> dict[str, Any]:
        with self.lock:
            self._assert_exports_unchanged()
            dataset, index = decision.dataset, decision.index
            if (
                dataset not in self.rows
                or index >= len(self.rows[dataset])
                or decision.row_id != self.row_ids[dataset][index]
            ):
                raise LatrosError("G5 review item changed or is stale")
            if dataset == "g1" and decision.final_decision == "approve":
                if (
                    not self.rows[dataset][index].get("candidate_disease_code")
                    or decision.mapping_relation is None
                ):
                    raise LatrosError(
                        "G1 approval requires a candidate code and an explicit "
                        "exact/equivalent decision"
                    )
            if dataset != "g1" and decision.mapping_relation is not None:
                raise LatrosError("A mapping relation is only valid for G1")
            events = self._events()
            history = [
                event for event in events if event["dataset"] == dataset and event["index"] == index
            ]
            reviews = _latest_reviews(history)
            basis = sorted(event["event_hash"] for event in reviews)
            if decision.stage == "adjudication":
                state = agreement(history)
                if len(reviews) < 2 or state["agreement"]:
                    raise LatrosError("Adjudication requires two independent unresolved reviews")
                if decision.reviewer_id in {event["reviewer_id"] for event in reviews}:
                    raise LatrosError("The adjudicator must be distinct from the reviewers")
                if sorted(decision.basis_event_hashes) != basis or not decision.comment:
                    raise LatrosError(
                        "Adjudication needs the current review hashes and a justification"
                    )
            elif decision.basis_event_hashes:
                raise LatrosError("Independent review must not refer to adjudication hashes")
            event: dict[str, Any] = {
                **decision.model_dump(mode="json"),
                "schema_version": 2,
                "action": decision.final_decision,
                "sequence": len(events) + 1,
                "previous_hash": events[-1]["event_hash"] if events else "0" * 64,
                "source_csv_sha256": self.hashes[self.expected_exports[dataset][0]],
                "timestamp_utc": datetime.now(UTC).isoformat(),
            }
            event["event_hash"] = _digest(_canonical(event))
            with self.audit_path.open("ab") as stream:
                stream.write(_canonical(event) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            return event

    def queue(self, dataset: str, filters: dict[str, str]) -> dict[str, Any]:
        if dataset not in self.rows:
            raise LatrosError("Unknown review dataset")
        with self.lock:
            self._assert_exports_unchanged()
            grouped = self._grouped_events()
            indices = []
            states = []
            for index, row in enumerate(self.rows[dataset]):
                if any(
                    value and _search_text(value) not in _search_text(row.get(key, ""))
                    for key, value in filters.items()
                    if key not in {"sample", "multiple_occurrences"}
                ):
                    continue
                if (
                    filters.get("multiple_occurrences") == "true"
                    and int(row.get("occurrence_count", "0")) < 2
                ):
                    continue
                if filters.get("sample") and row.get(
                    "candidate_assertion_id"
                ) not in self.samples.get(filters["sample"], []):
                    continue
                indices.append(index)
                states.append(agreement(grouped.get((dataset, index), [])))
            return {
                "indices": indices,
                "total": len(indices),
                "progress": {
                    key: sum(bool(state[key]) for state in states)
                    for key in (
                        "reviewed",
                        "agreement",
                        "disagreement",
                        "deferred",
                        "unresolved",
                        "adjudicated",
                    )
                },
            }

    def export_kind(self, kind: str) -> bytes:
        with self.lock:
            self._assert_exports_unchanged()
            events = self._events()
            grouped = self._grouped_events()
            payload: dict[str, Any] = {
                "schema_version": 2,
                "snapshot": SNAPSHOT,
                "snapshot_sha256": SNAPSHOT_SHA256,
                "source_exports_sha256": self.hashes,
                "samples_sha256": self.samples_hash,
                "clinical_validation": False,
                "publishable": False,
                "research_unreviewed": True,
                "safety_status": "not_evaluated",
                "applies_to_snapshot": False,
                "export_kind": kind,
            }
            if kind == "individual_decisions":
                payload["events"] = [
                    event for event in events if event.get("stage") != "adjudication"
                ]
            elif kind == "adjudications":
                payload["events"] = [
                    event for event in events if event.get("stage") == "adjudication"
                ]
            elif kind == "summary":
                payload["datasets"] = {dataset: self.queue(dataset, {}) for dataset in self.rows}
                payload["sample_sizes"] = {key: len(values) for key, values in self.samples.items()}
            elif kind in {"disagreements", "rejected_control", "retained_control"}:
                items: list[dict[str, Any]] = []
                for dataset, rows in self.rows.items():
                    for index, row in enumerate(rows):
                        history = grouped.get((dataset, index), [])
                        state = agreement(history)
                        if kind == "disagreements":
                            include = state["disagreement"]
                        else:
                            include = (
                                dataset == "g4"
                                and row.get("candidate_assertion_id") in self.samples[kind]
                            )
                        if include:
                            items.append(
                                {
                                    "dataset": dataset,
                                    "index": index,
                                    "row": row,
                                    "reviews": history,
                                    "state": state,
                                }
                            )
                payload["items"] = items
                if kind != "disagreements":
                    payload["reviewed_count"] = sum(item["state"]["reviewed"] for item in items)
                    payload["total"] = len(items)
                    payload["human_decision_counts"] = dict(
                        Counter(
                            event["final_decision"]
                            for item in items
                            for event in _latest_reviews(item["reviews"])
                        )
                    )
                    payload["note"] = (
                        "Structural control sample, not clinical sensitivity or specificity."
                    )
            else:
                raise LatrosError("Unknown G5 export kind")
            return _canonical(payload) + b"\n"


def create_adjudication_app(
    root: Path,
    exports_dir: Path,
    *,
    expected_exports: dict[str, tuple[str, str]] | None = None,
    expected_samples_sha256: str = SAMPLES_SHA256,
) -> FastAPI:
    store = AdjudicationStore(
        root,
        exports_dir,
        expected_exports=expected_exports,
        expected_samples_sha256=expected_samples_sha256,
    )
    app = create_review_app(root, exports_dir, review_store=store, home_asset="adjudication.html")
    token = secrets.token_urlsafe(32)

    def authorized(request: Request) -> None:
        if not secrets.compare_digest(request.headers.get("x-latros-review-token", ""), token):
            raise LatrosError("G5 review token is required")

    @app.get("/api/v2/token")
    async def get_token() -> dict[str, str]:
        return {"token": token}

    @app.get("/api/v2/queue")
    async def queue(request: Request, dataset: str = "g4") -> dict[str, Any]:
        allowed = {
            "auto_filter_decision",
            "domains",
            "auto_filter_rule",
            "disease_label",
            "finding_label",
            "subject_mapping_status",
            "medlineplus_only",
            "multiple_occurrences",
            "source_context",
            "sample",
        }
        return store.queue(
            dataset, {key: value for key, value in request.query_params.items() if key in allowed}
        )

    @app.get("/api/v2/item")
    async def item(
        dataset: str,
        index: int,
        reviewer_id: str = "",
        stage: Literal["review", "adjudication"] = "review",
    ) -> dict[str, Any]:
        return store.human_item(dataset, index, reviewer_id, stage)

    @app.post("/api/v2/decision")
    async def record(request: Request, decision: HumanDecisionInput) -> dict[str, Any]:
        authorized(request)
        return store.record_human(decision)

    @app.get("/api/v2/export/{kind}")
    async def export(request: Request, kind: str) -> Response:
        authorized(request)
        return Response(store.export_kind(kind), media_type="application/json")

    return app
