from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

from .config import Config, WORKTREE_BASE
from .gitops import determine_source_ref
from .output import error_exit, success, warning


def ensure_worktree_dir() -> None:
    if not WORKTREE_BASE.exists():
        WORKTREE_BASE.mkdir(parents=True)


def find_existing_worktree(branch_name: str) -> Optional[Path]:
    result = subprocess.run(["git", "worktree", "list", "--porcelain"], capture_output=True, text=True, check=True)
    lines = result.stdout.splitlines()
    current_worktree: Optional[Path] = None
    for line in lines:
        if line.startswith("worktree "):
            current_worktree = Path(line.split()[1])
        elif line.startswith("branch "):
            branch = line.split()[1].replace("refs/heads/", "")
            if branch == branch_name:
                return current_worktree
    return None


def branch_exists(branch_name: str) -> bool:
    result = subprocess.run(["git", "show-ref", "--verify", f"refs/heads/{branch_name}"], stdout=subprocess.DEVNULL)
    return result.returncode == 0


def validate_branch_name(branch_name: str) -> None:
    result = subprocess.run(["git", "check-ref-format", "--branch", branch_name])
    if result.returncode != 0:
        error_exit("Error: Invalid branch name provided")


def setup_worktree(branch_name: str, cfg: Config) -> Path:
    ensure_worktree_dir()
    worktree_path = WORKTREE_BASE / branch_name

    existing = find_existing_worktree(branch_name)
    if existing:
        warning("Branch '%s' already has a worktree at: %s", branch_name, existing)
        if existing.is_dir():
            success("Using existing worktree at: %s", existing)
            return existing
        warning("Worktree directory doesn't exist. Pruning and recreating...")
        subprocess.run(["git", "worktree", "prune"], check=True)
        subprocess.run(["git", "worktree", "add", str(worktree_path), branch_name], check=True)
        return worktree_path

    if branch_exists(branch_name):
        success("Adding worktree for existing branch: %s", branch_name)
        subprocess.run(["git", "worktree", "add", str(worktree_path), branch_name], check=True)
        return worktree_path

    source_ref = determine_source_ref(cfg)
    success("Creating new branch and worktree: %s from %s", branch_name, source_ref)
    try:
        subprocess.run([
            "git",
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_path),
            source_ref,
        ], check=True)
    except subprocess.CalledProcessError:
        if not sys.stdin.isatty():
            error_exit("Error: Cannot prompt for input in non-interactive mode. Try --no-worktree or a simpler prompt.")
        custom = input("Enter a custom branch name (or press Ctrl+C to cancel): ").strip()
        if not custom:
            error_exit("Error: No branch name provided")
        validate_branch_name(custom)
        worktree_path = WORKTREE_BASE / custom
        subprocess.run(["git", "worktree", "add", "-b", custom, str(worktree_path), "HEAD"], check=True)
        return worktree_path

    return worktree_path


def prepare_agent_worktree(agent_label: str, branch_name: str, source_ref: str) -> Path:
    validate_branch_name(branch_name)
    ensure_worktree_dir()
    worktree_path = WORKTREE_BASE / branch_name

    existing = find_existing_worktree(branch_name)
    if existing:
        warning("%s branch '%s' already has a worktree at: %s", agent_label, branch_name, existing)
        if existing.is_dir():
            success("Using existing %s worktree at: %s", agent_label, existing)
            return existing
        warning("Worktree directory missing for %s. Pruning and recreating...", agent_label)
        subprocess.run(["git", "worktree", "prune"], check=True)
        subprocess.run(["git", "worktree", "add", str(worktree_path), branch_name], check=True)
        return worktree_path

    if branch_exists(branch_name):
        success("Adding %s worktree for existing branch: %s", agent_label, branch_name)
        subprocess.run(["git", "worktree", "add", str(worktree_path), branch_name], check=True)
        return worktree_path

    success("Creating new %s branch/worktree: %s from %s", agent_label, branch_name, source_ref)
    subprocess.run(["git", "worktree", "add", "-b", branch_name, str(worktree_path), source_ref], check=True)
    return worktree_path
