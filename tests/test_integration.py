from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def run_cli(args: list[str], *, env: dict[str, str], cwd: Path, expect_failure: bool = False):
    cmd = [sys.executable, "-m", "vibe", *args]
    result = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        if expect_failure:
            return result
        raise RuntimeError(f"CLI failed: {result.stdout}\n{result.stderr}")
    if expect_failure:
        raise RuntimeError("CLI succeeded but failure was expected")
    return result


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    (repo / "README.md").write_text("test\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    return repo


def _read_log(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text()

def _wait_for_log(path: Path, needle: str, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if needle in _read_log(path):
            return True
        time.sleep(0.1)
    return False


def _list_pane_titles(socket: str) -> list[str]:
    result = subprocess.run(
        ["tmux", "-L", socket, "list-panes", "-F", "#{pane_title}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _worktree_paths(repo: Path) -> list[str]:
    result = subprocess.run(["git", "worktree", "list"], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def test_duo_worktree_launches_agents(cli_environment, git_repo):
    cli_environment.openai.queue(["phase one", "phase-one"])

    run_cli(["--duo", "implement phase"], env=cli_environment.env, cwd=git_repo)

    assert _wait_for_log(cli_environment.logs["claude"], "implement phase")
    assert _wait_for_log(cli_environment.logs["codex"], "implement phase")
    assert _wait_for_log(cli_environment.logs["claude"], "phase-one-claude")
    assert _wait_for_log(cli_environment.logs["codex"], "phase-one-codex")

    worktree_lines = _worktree_paths(git_repo)
    assert any("phase-one-claude" in line for line in worktree_lines)
    assert any("phase-one-codex" in line for line in worktree_lines)

    titles = _list_pane_titles(cli_environment.socket)
    assert len(titles) == 2


def test_requires_tmux_session(cli_environment, git_repo):
    env = dict(cli_environment.env)
    env.pop("TMUX", None)

    result = run_cli(["--duo", "no session"], env=env, cwd=git_repo, expect_failure=True)
    assert result.returncode != 0
    assert "vibe must be run inside an existing tmux session" in result.stderr

