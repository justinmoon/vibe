from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

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


def list_worktree_branches() -> Dict[str, Path]:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    branches: Dict[str, Path] = {}
    current_path: Optional[Path] = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line.split(maxsplit=1)[1])
        elif line.startswith("branch ") and current_path is not None:
            branch = line.split(maxsplit=1)[1].replace("refs/heads/", "")
            branches[branch] = current_path
    return branches


def list_duo_targets() -> Dict[str, Tuple[str, Path, str, Path]]:
    branches = list_worktree_branches()
    pairs: Dict[str, Tuple[str, Path, str, Path]] = {}
    claude_map: Dict[str, Path] = {}
    codex_map: Dict[str, Path] = {}

    for branch, path in branches.items():
        if branch.endswith("-claude"):
            base = branch[: -len("-claude")]
            claude_map[base] = path
        elif branch.endswith("-codex"):
            base = branch[: -len("-codex")]
            codex_map[base] = path

    for base, claude_path in claude_map.items():
        codex_path = codex_map.get(base)
        if codex_path is not None:
            pairs[base] = (
                f"{base}-claude",
                claude_path,
                f"{base}-codex",
                codex_path,
            )

    return pairs


def resolve_review_target(base_hint: Optional[str]) -> Tuple[str, Path, str, Path, str]:
    targets = list_duo_targets()
    if base_hint:
        match = targets.get(base_hint)
        if not match:
            error_exit(
                "Error: No duo worktree pair found for base '%s'. Pass a different base or run --duo first.",
                base_hint,
            )
        claude_branch, claude_path, codex_branch, codex_path = match
        return base_hint, claude_branch, claude_path, codex_branch, codex_path

    if not targets:
        error_exit(
            "Error: No existing duo worktrees found. Run vibe --duo first or specify --review-base.",
        )

    if len(targets) == 1:
        base, (claude_branch, claude_path, codex_branch, codex_path) = next(iter(targets.items()))
        return base, claude_branch, claude_path, codex_branch, codex_path

    if sys.stdin.isatty():
        options = sorted(targets.keys())
        print("Select a duo worktree base to review:")
        for idx, base in enumerate(options, start=1):
            print(f"  {idx}. {base}")
        choice = input("Enter number: ").strip()
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(options):
                selected = options[index]
                claude_branch, claude_path, codex_branch, codex_path = targets[selected]
                return selected, claude_branch, claude_path, codex_branch, codex_path
        error_exit("Error: Invalid selection for review base")

    error_exit(
        "Error: Multiple duo worktrees found (%s). Provide --review-base to disambiguate.",
        ", ".join(sorted(targets.keys())),
    )
