"""Opt-in llama.cpp transport. Only a private loopback server may receive case text."""

from __future__ import annotations

import asyncio
import os
import secrets
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from latros.common import LatrosError

ModelName = Literal["qwen", "huatuo"]


@dataclass(frozen=True)
class LocalModelSettings:
    server: Path
    qwen: Path
    huatuo: Path
    qwen_gpu_layers: int = 99
    huatuo_gpu_layers: int = 20

    @classmethod
    def from_environment(cls) -> LocalModelSettings:
        # Defaults are the user's local installation, not repository dependencies.
        return cls(
            server=Path(
                os.environ.get(
                    "LATROS_LLAMA_SERVER",
                    r"C:\Users\gaeta\Models\software\llama-bonsai-mtp-windows-cuda13.3-x64\bin\llama-server.exe",
                )
            ),
            qwen=Path(
                os.environ.get(
                    "LATROS_QWEN_MODEL",
                    r"C:\Users\gaeta\Models\models\gguf\Qwen3.5\Qwen3.5-9B-UD-Q5_K_XL.gguf",
                )
            ),
            huatuo=Path(
                os.environ.get(
                    "LATROS_HUATUO_MODEL",
                    r"D:\.huggingface\HuatuoGPT-3-27B\HuatuoGPT-3-27B.i1-IQ4_XS.gguf",
                )
            ),
            qwen_gpu_layers=int(os.environ.get("LATROS_QWEN_GPU_LAYERS", "99")),
            huatuo_gpu_layers=int(os.environ.get("LATROS_HUATUO_GPU_LAYERS", "20")),
        )

    def model(self, name: ModelName) -> Path:
        return self.qwen if name == "qwen" else self.huatuo

    def available(self, name: ModelName) -> bool:
        return self.server.is_file() and self.model(name).is_file()


class LocalLlamaServer:
    """One model/process at a time; never talks to a non-loopback address."""

    def __init__(self, root: Path, settings: LocalModelSettings | None = None) -> None:
        self.settings = settings or LocalModelSettings.from_environment()
        self.key_path = (
            root.resolve() / "sessions" / f".llama-api-key-{os.getpid()}-{secrets.token_hex(8)}"
        )
        self._process: subprocess.Popen[bytes] | None = None
        self._model: ModelName | None = None
        self._port: int | None = None
        self._token: str | None = None
        self._lock = asyncio.Lock()

    def status(self) -> dict[str, bool]:
        return {
            "qwen": self.settings.available("qwen"),
            "huatuo": self.settings.available("huatuo"),
        }

    async def complete(self, model: ModelName, messages: list[dict[str, str]]) -> str:
        if not self.settings.available(model):
            raise LatrosError(f"Local {model} model or llama-server is unavailable")
        async with self._lock:
            await self._ensure_started(model)
            assert self._port is not None and self._token is not None
            url = f"http://127.0.0.1:{self._port}/v1/chat/completions"
            async with httpx.AsyncClient(trust_env=False, timeout=300.0) as client:
                try:
                    response = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {self._token}"},
                        json={
                            "model": str(self.settings.model(model)),
                            "messages": messages,
                            "temperature": 0,
                            "stream": False,
                            "max_tokens": 1200 if model == "qwen" else 2200,
                        },
                    )
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                    raise LatrosError(f"Local {model} inference failed") from exc
            if not isinstance(content, str) or not content.strip():
                raise LatrosError("Local model returned an empty response")
            return content

    async def _ensure_started(self, model: ModelName) -> None:
        if self._model == model and self._process is not None and self._process.poll() is None:
            return
        self.close()
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self._token = secrets.token_urlsafe(32)
        self.key_path.write_text(self._token + "\n", encoding="utf-8")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self._port = int(listener.getsockname()[1])
        args = [
            str(self.settings.server),
            "--host",
            "127.0.0.1",
            "--port",
            str(self._port),
            "--no-webui",
            "--model",
            str(self.settings.model(model)),
            "--parallel",
            "1",
            "--ctx-size",
            "8192" if model == "qwen" else "16384",
            "--n-gpu-layers",
            str(
                self.settings.qwen_gpu_layers
                if model == "qwen"
                else self.settings.huatuo_gpu_layers
            ),
            "--api-key-file",
            str(self.key_path),
        ]
        if model == "qwen":
            args.extend(
                [
                    "--spec-type",
                    "draft-mtp",
                    "--spec-draft-n-max",
                    "4",
                    "--reasoning",
                    "off",
                    "--reasoning-budget",
                    "0",
                ]
            )
        # CREATE_NO_WINDOW exists only on Windows; Linux mypy checks the same source.
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        try:
            self._process = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
        except OSError as exc:
            self.close()
            raise LatrosError("Cannot start the local llama-server") from exc
        self._model = model
        assert self._port is not None
        async with httpx.AsyncClient(trust_env=False, timeout=2.0) as client:
            for _ in range(180):
                if self._process.poll() is not None:
                    self.close()
                    raise LatrosError("Local llama-server stopped while loading the model")
                try:
                    response = await client.get(
                        f"http://127.0.0.1:{self._port}/health",
                        headers={"Authorization": f"Bearer {self._token}"},
                    )
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(1)
        self.close()
        raise LatrosError("Timed out waiting for the local model")

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._process = None
        self._model = None
        self._port = None
        self._token = None
        self.key_path.unlink(missing_ok=True)
