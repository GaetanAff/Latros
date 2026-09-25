"""Profile one synthetic v0.7 HTTP diagnosis without changing the runtime.

Run each case in a fresh process.  Only timings/counts/sizes are written; the
case and the medical result stay in an ignored temporary local session.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import socket
import tempfile
import time
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from profile_general_v1_runtime import memory_mb

import latros.ui.server as server_module
import latros.ui.sessions as sessions_module
from latros.reasoning.results_v2 import DifferentialResultV2
from latros.ui.server import create_app
from latros.ui.sessions import SessionStore

SNAPSHOT = "v0.7.0-general-dev-unreviewed"


class QueryProbe:
    """Timing-only wrapper around the existing read-only DuckDB connection."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self.calls: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None

    def execute(self, sql: str, parameters: Any = None) -> QueryProbe:
        current: dict[str, Any] = {"sql": " ".join(sql.split())[:160]}
        started = time.perf_counter()
        if parameters is None:
            self.connection.execute(sql)
        else:
            self.connection.execute(sql, parameters)
        current["execute_s"] = round(time.perf_counter() - started, 3)
        self.calls.append(current)
        self.current = current
        return self

    def fetchall(self) -> list[Any]:
        started = time.perf_counter()
        rows = self.connection.fetchall()
        if self.current is not None:
            self.current["fetch_s"] = round(time.perf_counter() - started, 3)
            self.current["rows"] = len(rows)
        return rows

    def fetchone(self) -> Any:
        started = time.perf_counter()
        row = self.connection.fetchone()
        if self.current is not None:
            self.current["fetch_s"] = round(time.perf_counter() - started, 3)
            self.current["rows"] = int(row is not None)
        return row

    def __getattr__(self, name: str) -> Any:
        return getattr(self.connection, name)


def _block_network(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("F5 profile attempted an external network connection")


def _offline() -> None:
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def loopback_only(method: Callable[[Any], Any], address: Any) -> Any:
        if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise AssertionError("F5 profile attempted a non-loopback connection")
        return method(address)

    socket.create_connection = _block_network
    socket.socket.connect = lambda self, address: loopback_only(
        lambda value: original_connect(self, value), address
    )
    socket.socket.connect_ex = lambda self, address: loopback_only(
        lambda value: original_connect_ex(self, value), address
    )
    socket.getaddrinfo = _block_network


def _wrap(target: Any, name: str, key: str, phases: dict[str, dict[str, float | int]]) -> None:
    original = getattr(target, name)

    def measured(*args: Any, **kwargs: Any) -> Any:
        wall = time.perf_counter()
        cpu = time.process_time()
        try:
            return original(*args, **kwargs)
        finally:
            item = phases[key]
            item["calls"] += 1
            item["wall_s"] += time.perf_counter() - wall
            item["cpu_s"] += time.process_time() - cpu

    setattr(target, name, measured)


def _request(client: TestClient, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.request(method, path, json=payload)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cprofile", action="store_true")
    args = parser.parse_args()
    _offline()
    case_data = json.loads(args.case.read_text(encoding="utf-8"))
    case = case_data.get("clinical_case", case_data)
    staging = (args.root / "data/staging").resolve()
    staging.mkdir(parents=True, exist_ok=True)
    phases: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"calls": 0, "wall_s": 0.0, "cpu_s": 0.0}
    )
    with tempfile.TemporaryDirectory(prefix="latros-f5-profile-", dir=staging) as directory:
        local_root = Path(directory).resolve()
        if not local_root.is_relative_to(staging):
            raise ValueError("Temporary sessions must remain under data/staging")
        app = create_app(args.root)
        app.state.sessions = SessionStore(local_root)
        with TestClient(app) as client:
            session = _request(
                client, "POST", "/internal/v1/sessions", {"display_name": "F5 synthetic"}
            )
            path = f"/internal/v1/sessions/{session['session_id']}"
            session = _request(
                client,
                "PUT",
                f"{path}/selection",
                {
                    "revision": session["revision"],
                    "snapshot_id": SNAPSHOT,
                    "strategy_id": "general_v1",
                },
            )
            session = _request(
                client,
                "PUT",
                f"{path}/case",
                {
                    "revision": session["revision"],
                    "clinical_case": case,
                },
            )
            service = app.state.service
            strategy = service._general_strategy(SNAPSHOT)
            # A preceding question reflects the interactive post-question path and
            # warms the same repository without changing the submitted case.
            question = _request(
                client,
                "POST",
                f"{path}/questions/next",
                {
                    "revision": session["revision"],
                },
            )
            revision = question["session"]["revision"]
            query_probe = QueryProbe(strategy.repository.connection)
            strategy.repository.connection = query_probe
            for name in ("_project", "generate", "_compute", "_result_candidate", "_receipt"):
                _wrap(strategy, name, f"strategy.{name}", phases)
            for name in ("matching_candidate_ids", "candidate_rows", "resolve_observation"):
                _wrap(strategy.repository, name, f"repository.{name}", phases)
            profiler = cProfile.Profile() if args.cprofile else None
            if profiler is not None:
                original_rows = strategy.repository.candidate_rows

                def profiled_rows(*a: Any, **kw: Any) -> Any:
                    profiler.enable()
                    try:
                        return original_rows(*a, **kw)
                    finally:
                        profiler.disable()

                strategy.repository.candidate_rows = profiled_rows
            _wrap(app.state.sessions, "record_run", "session.record_run", phases)
            _wrap(sessions_module, "write_indexed_run", "storage.write_indexed_run", phases)
            _wrap(server_module, "summary_projection", "transport.summary_projection", phases)
            original_replace = Path.replace
            _wrap(Path, "replace", "storage.atomic_rename", phases)
            original_dump = DifferentialResultV2.model_dump

            def measured_dump(self: DifferentialResultV2, *a: Any, **kw: Any) -> Any:
                wall = time.perf_counter()
                cpu = time.process_time()
                try:
                    return original_dump(self, *a, **kw)
                finally:
                    item = phases["pydantic.result_model_dump"]
                    item["calls"] += 1
                    item["wall_s"] += time.perf_counter() - wall
                    item["cpu_s"] += time.process_time() - cpu

            DifferentialResultV2.model_dump = measured_dump
            rss_before = memory_mb()
            wall = time.perf_counter()
            cpu = time.process_time()
            try:
                response = client.post(f"{path}/analyses?view=summary", json={"revision": revision})
                elapsed = time.perf_counter() - wall
                cpu_elapsed = time.process_time() - cpu
            finally:
                DifferentialResultV2.model_dump = original_dump
                Path.replace = original_replace
            response.raise_for_status()
            document = response.json()
            run_id = document["run"]["run_id"]
            stored = app.state.sessions._run_path(session["session_id"], run_id)
            index = stored.with_suffix(".index.json")
            report: dict[str, Any] = {
                "schema_version": 1,
                "snapshot": SNAPSHOT,
                "case_name": args.case.name,
                "observation_count": len(case.get("observations", [])),
                "candidate_count": document["run"]["result"]["candidate_count"],
                "http_s": round(elapsed, 3),
                "cpu_s": round(cpu_elapsed, 3),
                "rss_before_mb": rss_before,
                "rss_after_mb": memory_mb(),
                "http_response_bytes": len(response.content),
                "run_bytes": stored.stat().st_size,
                "index_bytes": index.stat().st_size,
                "queries": query_probe.calls,
                "phases": {
                    key: {metric: round(value, 3) for metric, value in item.items()}
                    for key, item in sorted(phases.items())
                },
            }
            if profiler is not None:
                output = io.StringIO()
                pstats.Stats(profiler, stream=output).sort_stats("cumtime").print_stats(40)
                report["cprofile_top40"] = output.getvalue()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            print(
                json.dumps(
                    {key: value for key, value in report.items() if key != "cprofile_top40"},
                    sort_keys=True,
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
