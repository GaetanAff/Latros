"""Small HTTP projections and byte offsets for immutable local diagnosis runs.

The index is an auxiliary transport artifact.  The complete v2 result remains in
the run JSON, and neither this module nor the UI changes the reasoning contract.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import orjson

from latros.common import LatrosError, sha256, write_json
from latros.ui.models import StoredRun

SUMMARY_LIMIT = 20


def summary_projection(run: StoredRun) -> dict[str, Any]:
    """Return only fields consumed by the simple results screen."""
    result = run.result
    candidates = result.get("candidates", [])
    if not isinstance(candidates, list):
        raise LatrosError("Stored diagnosis candidates are invalid")
    top = []
    for candidate in candidates[:SUMMARY_LIMIT]:
        top.append(
            {
                "candidate_id": candidate["candidate_id"],
                "label": candidate["label"],
                "rank": candidate["rank"],
                "aggregate": candidate["aggregate"],
                "favorable": _brief_contributions(candidate.get("favorable", [])),
                "unfavorable": _brief_contributions(candidate.get("unfavorable", [])),
            }
        )
    return {
        "run_id": run.run_id,
        "session_id": run.session_id,
        "operation": run.operation,
        "created_at": run.created_at.isoformat(),
        "result": {
            "case_id": result.get("case_id"),
            "status": result.get("status"),
            "scope_status": result.get("scope_status"),
            "coverage": result.get("coverage"),
            "abstention": result.get("abstention"),
            "research_unreviewed": result.get("research_unreviewed"),
            "safety": result.get("safety"),
            "candidate_count": len(candidates),
            "candidates": top,
        },
    }


def _brief_contributions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"observation": item.get("observation")} for item in items[:2]]


def write_indexed_run(path: Path, run: StoredRun) -> dict[str, Any]:
    """Atomically write a complete compact run plus a small seek index.

    New runs have the same JSON value as the legacy pretty-printed run files.
    Historic files are not rewritten and remain readable through the fallback.
    """
    if path.exists():
        raise LatrosError("Immutable session run already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    digest = hashlib.sha256()
    offsets: dict[str, list[int]] = {}
    # Keep the already-serialized v2 result by reference: Pydantic would
    # otherwise duplicate the entire ~200 MB candidate tree before writing.
    payload = run.model_dump(mode="json", exclude={"result"})
    payload["result"] = run.result

    try:
        with temporary.open("wb") as handle:

            def emit(data: bytes) -> None:
                handle.write(data)
                digest.update(data)

            emit(b"{")
            for top_index, key in enumerate(sorted(payload)):
                if top_index:
                    emit(b",")
                emit(orjson.dumps(key) + b":")
                value = payload[key]
                if key != "result" or run.operation != "diagnose":
                    emit(orjson.dumps(value, option=orjson.OPT_SORT_KEYS))
                    continue
                emit(b"{")
                for result_index, result_key in enumerate(sorted(value)):
                    if result_index:
                        emit(b",")
                    emit(orjson.dumps(result_key) + b":")
                    if result_key != "candidates":
                        emit(orjson.dumps(value[result_key], option=orjson.OPT_SORT_KEYS))
                        continue
                    emit(b"[")
                    for candidate_index, candidate in enumerate(value[result_key]):
                        if candidate_index:
                            emit(b",")
                        candidate_id = str(candidate["candidate_id"])
                        if candidate_id in offsets:
                            raise LatrosError("Duplicate candidate ID in diagnosis run")
                        start = handle.tell()
                        data = orjson.dumps(candidate, option=orjson.OPT_SORT_KEYS)
                        emit(data)
                        offsets[candidate_id] = [start, len(data)]
                    emit(b"]")
                emit(b"}")
            emit(b"}\n")
        index = {
            "schema_version": 1,
            "run_id": run.run_id,
            "run_sha256": digest.hexdigest(),
            "run_size": temporary.stat().st_size,
            "summary": summary_projection(run),
            "detail_context": {
                "run_receipt": run.result.get("run_receipt"),
                "selection": payload["selection"],
                "research_unreviewed": run.result.get("research_unreviewed"),
                "safety": run.result.get("safety"),
            },
            "candidate_offsets": offsets,
        }
        temporary.replace(path)
        write_json(index_path(path), index)
        return cast(dict[str, Any], index["summary"])
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def index_path(run_path: Path) -> Path:
    return run_path.with_suffix(".index.json")


def read_index(run_path: Path) -> dict[str, Any] | None:
    index_file = index_path(run_path)
    if not index_file.is_file():
        return None
    index = cast(dict[str, Any], orjson.loads(index_file.read_bytes()))
    if index.get("run_id") != run_path.stem or index.get("run_size") != run_path.stat().st_size:
        raise LatrosError("Diagnosis transport index does not match the immutable run")
    if index.get("run_sha256") != sha256(run_path):
        raise LatrosError("Immutable diagnosis run failed transport integrity check")
    return index


def read_candidate(run_path: Path, index: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    location = index["candidate_offsets"].get(candidate_id)
    if location is None:
        raise LatrosError(f"Unknown diagnosis candidate: {candidate_id}")
    offset, length = location
    with run_path.open("rb") as handle:
        handle.seek(offset)
        candidate = orjson.loads(handle.read(length))
    if candidate.get("candidate_id") != candidate_id:
        raise LatrosError("Diagnosis candidate index is inconsistent")
    return {"candidate": candidate, **index["detail_context"]}
