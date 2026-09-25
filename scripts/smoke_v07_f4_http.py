"""Measure the real v0.7 local HTTP summary/detail path with network blocked.

The input must be a locally generated synthetic session/case.  Temporary runs
are kept under ignored data/staging only for the duration of this smoke test.
"""

from __future__ import annotations

import argparse
import json
import socket
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from latros.ui.server import create_app
from latros.ui.sessions import SessionStore

SNAPSHOT = "v0.7.0-general-dev-unreviewed"


def _block_network(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("F4 HTTP smoke attempted a non-loopback connection")


def _request(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    response = client.request(method, path, json=payload)
    elapsed = round(time.perf_counter() - started, 3)
    response.raise_for_status()
    return response.json(), {"seconds": elapsed, "bytes": len(response.content)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--case", type=Path, required=True)
    args = parser.parse_args()
    case_data = json.loads(args.case.read_text(encoding="utf-8"))
    case = case_data.get("clinical_case", case_data)
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def loopback_only(method: Any, address: Any) -> Any:
        if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise AssertionError("F4 HTTP smoke attempted a non-loopback connection")
        return method(address)

    socket.create_connection = _block_network
    socket.socket.connect = lambda self, address: loopback_only(
        lambda value: original_connect(self, value), address
    )
    socket.socket.connect_ex = lambda self, address: loopback_only(
        lambda value: original_connect_ex(self, value), address
    )
    socket.getaddrinfo = _block_network
    staging = (args.root / "data/staging").resolve()
    staging.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="latros-f4-http-", dir=staging) as directory:
        local_root = Path(directory).resolve()
        if not local_root.is_relative_to(staging):
            raise ValueError("Temporary sessions must remain under data/staging")
        app = create_app(args.root)
        app.state.sessions = SessionStore(local_root)
        with TestClient(app) as client:
            session, _ = _request(
                client, "POST", "/internal/v1/sessions", {"display_name": "F4 synthetic"}
            )
            path = f"/internal/v1/sessions/{session['session_id']}"
            session, _ = _request(
                client,
                "PUT",
                f"{path}/selection",
                {
                    "revision": session["revision"],
                    "snapshot_id": SNAPSHOT,
                    "strategy_id": "general_v1",
                },
            )
            session, _ = _request(
                client,
                "PUT",
                f"{path}/case",
                {
                    "revision": session["revision"],
                    "clinical_case": case,
                },
            )
            question, question_metric = _request(
                client,
                "POST",
                f"{path}/questions/next",
                {
                    "revision": session["revision"],
                },
            )
            analysis, summary_metric = _request(
                client,
                "POST",
                f"{path}/analyses?view=summary",
                {
                    "revision": question["session"]["revision"],
                },
            )
            run = analysis["run"]
            candidate = run["result"]["candidates"][0]
            detail, detail_metric = _request(
                client, "GET", f"{path}/runs/{run['run_id']}/candidates/{candidate['candidate_id']}"
            )
            resumed, resume_metric = _request(client, "GET", f"{path}/runs/{run['run_id']}/summary")
            assert detail["candidate"]["candidate_id"] == candidate["candidate_id"]
            assert resumed == run
            assert run["result"]["research_unreviewed"] is True
            assert run["result"]["safety"]["status"] == "not_evaluated"
            stored = app.state.sessions._run_path(session["session_id"], run["run_id"])
            print(
                json.dumps(
                    {
                        "question": question_metric,
                        "diagnosis_summary": summary_metric,
                        "candidate_detail": detail_metric,
                        "resume_summary": resume_metric,
                        "candidate_count": run["result"]["candidate_count"],
                        "stored_run_bytes": stored.stat().st_size,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
