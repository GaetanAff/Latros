"""Exercise the real v0.7 HTTP route offline with isolated synthetic sessions."""

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
    raise AssertionError("HTTP smoke attempted an external network connection")


def _post(client: TestClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.post(path, json=payload)
    print(path, response.status_code, round(time.perf_counter() - started, 3), flush=True)
    response.raise_for_status()
    return response.json()


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
            raise AssertionError("HTTP smoke attempted a non-loopback connection")
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
    with tempfile.TemporaryDirectory(prefix="latros-f3-http-", dir=staging) as directory:
        if not Path(directory).resolve().is_relative_to(staging):
            raise ValueError("Temporary sessions must remain under data/staging")
        app = create_app(args.root)
        app.state.sessions = SessionStore(Path(directory))
        with TestClient(app) as client:
            assert client.get("/").status_code == 200
            assert client.get("/expert").status_code == 200
            session = _post(client, "/internal/v1/sessions", {"display_name": "F3 synthetic"})
            path = f"/internal/v1/sessions/{session['session_id']}"
            selected = client.put(
                f"{path}/selection",
                json={
                    "revision": session["revision"],
                    "snapshot_id": SNAPSHOT,
                    "strategy_id": "general_v1",
                },
            )
            selected.raise_for_status()
            session = selected.json()
            saved = client.put(
                f"{path}/case", json={"revision": session["revision"], "clinical_case": case}
            )
            saved.raise_for_status()
            session = saved.json()
            question = _post(client, f"{path}/questions/next", {"revision": session["revision"]})
            assert question["run"]["result"]["research_unreviewed"] is True
            session = question["session"]
            analysis = _post(client, f"{path}/analyses", {"revision": session["revision"]})
            result = analysis["run"]["result"]
            assert result["research_unreviewed"] is True
            assert result["safety"]["status"] == "not_evaluated"
            assert analysis["session"]["latest_diagnose"]["run_id"] == analysis["run"]["run_id"]
            print("candidates", len(result["candidates"]), "session resumed", flush=True)


if __name__ == "__main__":
    main()
