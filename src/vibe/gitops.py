from __future__ import annotations

import subprocess
import sys
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


def _list_local_branches() -> list[str]:
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        warning("Warning: Unable to list local branches; defaulting to HEAD.")
        return []
    branches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return branches


def _prompt_for_branch_selection(branches: list[str], default_branch: str, current: str | None) -> str:
    ordered: list[str] = []
    seen: set[str] = set()

    def add_option(name: str | None) -> None:
        if not name:
            return
        if name in branches and name not in seen:
            ordered.append(name)
            seen.add(name)

    add_option(default_branch)
    add_option(current if current != default_branch else None)
    for branch in branches:
        if branch not in seen:
            ordered.append(branch)

    while True:
        print("Select a branch to base the new worktree on:")
        for idx, branch in enumerate(ordered, start=1):
            tags: list[str] = []
            if branch == default_branch:
                tags.append("default")
            if current and branch == current:
                tags.append("current")
            suffix = f" ({', '.join(tags)})" if tags else ""
            print(f"  {idx}. {branch}{suffix}")
        choice = input(f"Enter number or branch name [{default_branch}]: ").strip()
        if not choice:
            return default_branch
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(ordered):
                return ordered[index]
        elif choice in ordered:
            return choice
        print(f"Invalid selection '{choice}'. Please try again.")


def determine_source_ref(cfg: Config) -> str:
    if cfg.from_branch:
        return cfg.from_branch
    if cfg.from_master:
        success("Base branch: master (--from-master)")
        return "master"

    branches = _list_local_branches()
    if not branches:
        return "HEAD"

    current = current_branch()
    if current == "detached":
        current = None

    if "master" in branches:
        default_branch = "master"
    elif current and current in branches:
        default_branch = current
    else:
        default_branch = branches[0]

    if not sys.stdin.isatty():
        success("Base branch: %s", default_branch)
        return default_branch

    selected = _prompt_for_branch_selection(branches, default_branch, current)
    success("Base branch: %s", selected)
    return selected
