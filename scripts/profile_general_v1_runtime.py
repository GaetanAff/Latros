"""Reproducible local performance profile of the immutable v0.7 DuckDB runtime.

Run in a fresh process on the actual locally built snapshot. Reports wall time,
retained Pydantic objects and process memory; never writes patient or source data.
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import hashlib
import json
import os
import socket
import time
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from latros.application.service import ResearchApplicationService
from latros.clinical.loading import load_clinical_case
from latros.clinical.v2 import ClinicalCaseV2
from latros.knowledge.store_v2 import load_manifest_v2

SNAPSHOT = "v0.7.0-general-dev-unreviewed"


def memory_mb() -> dict[str, float]:
    if os.name == "nt":

        class MemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        process_api = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        process_api.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(MemoryCounters),
            wintypes.DWORD,
        ]
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if not process_api.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise OSError(ctypes.get_last_error())
        scale = 1024 * 1024
        return {
            "rss": round(counters.WorkingSetSize / scale, 1),
            "peak_rss": round(counters.PeakWorkingSetSize / scale, 1),
            "private": round(counters.PagefileUsage / scale, 1),
        }
    rss_kib = 0
    peak_kib = 0
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            rss_kib = int(line.split()[1])
        elif line.startswith("VmHWM:"):
            peak_kib = int(line.split()[1])
    return {
        "rss": round(rss_kib / 1024, 1),
        "peak_rss": round(peak_kib / 1024, 1),
    }


def timed(report: dict[str, Any], name: str, action: Callable[[], Any]) -> Any:
    before = memory_mb()
    start = time.perf_counter()
    value = action()
    report[name] = {
        "seconds": round(time.perf_counter() - start, 3),
        "before_mb": before,
        "after_mb": memory_mb(),
    }
    print(name, report[name], flush=True)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    def reject_network(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("The profiled runtime attempted a network connection")

    socket.create_connection = reject_network
    socket.socket.connect = reject_network
    socket.socket.connect_ex = reject_network
    socket.getaddrinfo = reject_network
    case = load_clinical_case((args.root / "examples/general/rare-multisystem.json").read_bytes())
    assert isinstance(case, ClinicalCaseV2)
    report: dict[str, Any] = {
        "snapshot": SNAPSHOT,
        "platform": os.name,
        "initial_mb": memory_mb(),
        "phases": {},
    }
    phases = report["phases"]
    service = timed(phases, "service_startup", lambda: ResearchApplicationService(args.root))
    manifest = timed(
        phases, "integrity_verification", lambda: load_manifest_v2(args.root, SNAPSHOT)
    )
    report["snapshot_content_sha256"] = manifest.content_sha256
    options = timed(
        phases,
        "first_concept_search",
        lambda: service.search_concepts(SNAPSHOT, "general_v1", "cough", limit=20),
    )
    report["concept_results"] = len(options)
    timed(phases, "strategy_cached_lookup", lambda: service._general_strategy(SNAPSHOT))
    report["retained_models_after_open"] = sum(
        isinstance(item, BaseModel) for item in gc.get_objects()
    )
    diagnosis = timed(
        phases, "first_diagnose", lambda: service.diagnose(SNAPSHOT, case, "general_v1")
    )
    report["first_sha256"] = hashlib.sha256(diagnosis.model_dump_json().encode()).hexdigest()
    report["first_candidate_count"] = len(diagnosis.candidates)
    del diagnosis
    gc.collect()
    report["after_first_release_mb"] = memory_mb()
    diagnosis = timed(
        phases, "second_diagnose", lambda: service.diagnose(SNAPSHOT, case, "general_v1")
    )
    report["second_sha256"] = hashlib.sha256(diagnosis.model_dump_json().encode()).hexdigest()
    del diagnosis
    gc.collect()
    question = timed(
        phases, "question_next", lambda: service.next_question(SNAPSHOT, case, "general_v1")
    )
    report["question_sha256"] = hashlib.sha256(question.model_dump_json().encode()).hexdigest()
    del question
    gc.collect()
    report["retained_models_final"] = sum(isinstance(item, BaseModel) for item in gc.get_objects())
    report["final_mb"] = memory_mb()
    service.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
