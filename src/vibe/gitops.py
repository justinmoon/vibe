from __future__ import annotations

import subprocess
from pathlib import Path

from .config import Config
from .output import error_exit, success, warning


def ensure_git_repo() -> None:
    result = subprocess.run(["git", "rev-parse", "--git-dir"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        error_exit("Error: Not in a git repository")


def pull_latest_changes(cfg: Config) -> None:
    if cfg.from_branch:
        success("Using --from branch: %s (skipping pull from origin)", cfg.from_branch)
        return
    success("Pulling latest changes from origin...")
    result = subprocess.run(["git", "pull", "--rebase"], capture_output=True, text=True)
    if result.returncode != 0:
        warning(
            "Warning: Could not pull latest changes. This might be due to:\n  - Uncommitted changes\n  - Network issues\n  - Remote repository issues\nContinuing anyway..."
        )


def current_branch() -> str:
    result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    if result.returncode != 0:
        warning("Error: Could not determine current branch")
        return "detached"
    return result.stdout.strip()


def run_init_script(path: Path) -> None:
    init_script = path / "scripts" / "init.sh"
    if not init_script.is_file():
        return
    success("Running worktree initialization script...")
    result = subprocess.run(["bash", str(init_script)], cwd=path)
    if result.returncode != 0:
        warning("Warning: Initialization script failed, continuing anyway...")


def determine_source_ref(cfg: Config) -> str:
    if cfg.from_branch:
        return cfg.from_branch
    cwd_str = str(Path.cwd())
    if "/worktree" in cwd_str:
        if cfg.from_master:
            return "master"
        result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
        if result.returncode == 0:
            current = result.stdout.strip() or "HEAD"
            success("In worktree on '%s' - branching from current branch", current)
            return "HEAD"
    return "HEAD"
