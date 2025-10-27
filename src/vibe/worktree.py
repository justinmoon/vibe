from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config import Config, WORKTREE_BASE
from .gitops import determine_source_ref
from .output import error_exit, success, warning

PROMPT_SUFFIX = ".prompt"

PROMPT_SUFFIX = ".prompt"


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
    result = subprocess.run(
        ["git", "show-ref", "--verify", f"refs/heads/{branch_name}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
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
    
    # Known agent suffixes to look for
    agent_suffixes = ["-claude", "-codex", "-droid", "-oc", "-amp"]
    
    # Group branches by base name
    base_map: Dict[str, Dict[str, Tuple[str, Path]]] = {}
    
    for branch, path in branches.items():
        # Check if branch ends with any agent suffix
        for suffix in agent_suffixes:
            if branch.endswith(suffix):
                base = branch[: -len(suffix)]
                agent = suffix[1:]  # Remove leading dash
                if base not in base_map:
                    base_map[base] = {}
                base_map[base][agent] = (branch, path)
                break
    
    # Find bases that have exactly 2 agents
    for base, agents in base_map.items():
        if len(agents) == 2:
            agent_list = sorted(agents.items())
            agent1_name, (branch1, path1) = agent_list[0]
            agent2_name, (branch2, path2) = agent_list[1]
            pairs[base] = (branch1, path1, branch2, path2)

    return pairs


def resolve_review_target(base_hint: Optional[str]) -> Tuple[str, str, Path, str, Path]:
    targets = list_duo_targets()
    if base_hint:
        match = targets.get(base_hint)
        if not match:
            error_exit(
                "Error: No duo worktree pair found for base '%s'. Pass a different base or run --duo first.",
                base_hint,
            )
        branch1, path1, branch2, path2 = match
        return base_hint, branch1, path1, branch2, path2

    if not targets:
        error_exit(
            "Error: No existing duo worktrees found. Run vibe --duo first or specify --review-base.",
        )

    if len(targets) == 1:
        base, (branch1, path1, branch2, path2) = next(iter(targets.items()))
        return base, branch1, path1, branch2, path2

    if sys.stdin.isatty():
        options = sorted(targets.keys())
        # Use fzf for selection
        try:
            result = subprocess.run(
                ["fzf", "--prompt", "Select a duo worktree base to review: "],
                input="\n".join(options),
                text=True,
                capture_output=True,
            )
            
            if result.returncode == 0:
                selected = result.stdout.strip()
                branch1, path1, branch2, path2 = targets[selected]
                return selected, branch1, path1, branch2, path2
            else:
                error_exit("Error: No review base selected")
        except FileNotFoundError:
            error_exit("Error: fzf not found. Please install fzf.")

    error_exit(
        "Error: Multiple duo worktrees found (%s). Provide --review-base to disambiguate.",
        ", ".join(sorted(targets.keys())),
    )


def _prompt_path(base: str) -> Path:
    ensure_worktree_dir()
    return WORKTREE_BASE / f"{base}{PROMPT_SUFFIX}"


def write_duo_prompt(base: str, prompt: str) -> None:
    if not prompt:
        return
    try:
        _prompt_path(base).write_text(prompt.strip() + "\n", encoding="utf-8")
    except OSError:
        warning("Failed to persist prompt metadata for base '%s'", base)


def read_duo_prompt(base: str) -> Optional[str]:
    path = _prompt_path(base)
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8").strip()
        return content or None
    except OSError:
        warning("Failed to read prompt metadata for base '%s'", base)
        return None
