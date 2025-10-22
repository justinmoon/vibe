from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _kill_tmux(socket_name: str) -> None:
    os.system(f"tmux -L {socket_name} kill-server > /dev/null 2>&1")


@pytest.fixture
def tmux_socket(monkeypatch: pytest.MonkeyPatch):
    socket_name = f"vibe-test-{uuid4().hex}"
    monkeypatch.setenv("VIBE_TMUX_SOCKET", socket_name)
    yield socket_name
    _kill_tmux(socket_name)


class _OpenAIStub(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self._responses: list[str] = []
        self._lock = threading.Lock()

    def queue(self, responses: list[str]) -> None:
        with self._lock:
            self._responses.extend(responses)

    def next_response(self) -> str:
        with self._lock:
            if self._responses:
                return self._responses.pop(0)
        return "stub-branch"


class _StubHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # type: ignore[override]
        length = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(length)
        response = self.server.next_response()  # type: ignore[attr-defined]
        body = json.dumps({"choices": [{"message": {"content": response}}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args):  # type: ignore[override]
        return


@pytest.fixture
def openai_stub(monkeypatch: pytest.MonkeyPatch):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
    server = _OpenAIStub((host, port), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://{host}:{port}"
    monkeypatch.setenv("VIBE_OPENAI_API_BASE", base_url)
    monkeypatch.setenv("VIBE_OPENAI_KEY", "test-key")
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.fixture
def cli_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmux_socket: str, openai_stub: _OpenAIStub):
    bin_dir = tmp_path / "tools"
    bin_dir.mkdir()
    logs = {}

    def _write_tool(name: str):
        log_path = tmp_path / f"{name}.log"
        logs[name] = log_path
        script_path = bin_dir / name
        script_path.write_text(
            "#!/usr/bin/env bash\n"
            f"echo \"PWD=$(pwd)\" >> {log_path}\n"
            f"echo \"ARGS:$*\" >> {log_path}\n"
        )
        script_path.chmod(0o755)

    for tool in ("claude", "codex"):
        _write_tool(tool)

    op_path = bin_dir / "op"
    op_path.write_text("#!/usr/bin/env bash\nif [ \"$1\" = \"read\" ]; then\n  echo test-key\nelse\n  exit 1\nfi\n")
    op_path.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    env["VIBE_TMUX_SOCKET"] = tmux_socket
    env.setdefault("VIBE_OPENAI_KEY", "test-key")
    env["VIBE_CLAUDE_BIN"] = str(bin_dir / "claude")
    env["VIBE_CODEX_BIN"] = str(bin_dir / "codex")

    monkeypatch.delenv("TMUX", raising=False)

    subprocess.run(
        [
            "tmux",
            "-L",
            tmux_socket,
            "new-session",
            "-d",
            "-s",
            "vibe-test-base",
            "-n",
            "base",
        ],
        check=True,
        env=env,
    )
    socket_path = subprocess.run(
        ["tmux", "-L", tmux_socket, "display-message", "-p", "#{socket_path}"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout.strip()
    env["TMUX"] = f"{socket_path},0,0"

    return SimpleNamespace(env=env, logs=logs, socket=tmux_socket, openai=openai_stub)


def run_cli(args: list[str], *, env: dict[str, str], cwd: Path, expect_failure: bool = False):
    import subprocess
    import sys

    cmd = [sys.executable, "-m", "vibe", *args]
    result = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        if expect_failure:
            return result
        raise RuntimeError(f"CLI failed: {result.stdout}\n{result.stderr}")
    return result
