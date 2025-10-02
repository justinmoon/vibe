from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .output import error_exit, info, success, warning
from .tmux import kill_window, list_windows
from .worktree import list_duo_targets


@dataclass
class DuoTarget:
    base: str
    claude_branch: str
    claude_path: Path
    codex_branch: str
    codex_path: Path


def handle_merge_command(argv: Iterable[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="vibe merge",
        description="Merge or clean up duo worktrees",
    )
    parser.add_argument("--base", help="Base name of the duo worktree pair to merge")
    parser.add_argument(
        "--keep",
        choices=["claude", "codex"],
        help="Which agent branch to keep",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed even if worktrees have unstaged changes",
    )
    parser.add_argument(
        "--no-tmux",
        action="store_true",
        help="Skip killing tmux windows",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned actions without executing",
    )

    args = parser.parse_args(list(argv))

    targets = _collect_duo_targets()
    if not targets:
        error_exit("No duo worktrees found. Run `vibe --duo` before merging.")

    target = _choose_target(targets, args.base)
    keep = args.keep or _prompt_keep_choice()

    losing_branch, losing_path = _losing_branch(target, keep)
    keeping_branch, keeping_path = _keeping_branch(target, keep)

    keeping_dirty = keeping_path.exists() and _worktree_dirty(keeping_path)
    losing_dirty = losing_path.exists() and _worktree_dirty(losing_path)

    if losing_dirty and not args.force:
        error_exit(
            "Unstaged changes detected in branch %s. Commit or stash before running `vibe merge`, or re-run with --force.",
            losing_branch,
        )

    windows_to_kill: List[str] = []
    if not args.no_tmux and shutil.which("tmux"):
        windows_to_kill = _find_related_windows(
            target.base,
            [target.claude_branch, target.codex_branch],
        )

    _print_summary(
        target=target,
        keep=keep,
        losing_branch=losing_branch,
        losing_path=losing_path,
        keeping_branch=keeping_branch,
        keeping_path=keeping_path,
        keeping_dirty=keeping_dirty,
        losing_dirty=losing_dirty,
        windows_to_kill=windows_to_kill,
    )

    if args.dry_run:
        return

    if not _confirm():
        info("Merge cancelled")
        return

    if windows_to_kill:
        for window_id in windows_to_kill:
            kill_window(window_id, delay=True)

    _cleanup_branch(losing_branch, losing_path)

    success(
        "Kept %s (%s). Next steps: checkout this branch, merge into your target branch, then delete it when finished.",
        keep,
        keeping_branch,
    )


def _collect_duo_targets() -> Dict[str, DuoTarget]:
    raw = list_duo_targets()
    targets: Dict[str, DuoTarget] = {}
    for base, (claude_branch, claude_path, codex_branch, codex_path) in raw.items():
        targets[base] = DuoTarget(
            base=base,
            claude_branch=claude_branch,
            claude_path=claude_path,
            codex_branch=codex_branch,
            codex_path=codex_path,
        )
    return targets


def _choose_target(targets: Dict[str, DuoTarget], base_hint: Optional[str]) -> DuoTarget:
    if base_hint:
        target = targets.get(base_hint)
        if not target:
            error_exit("No duo worktree pair found for base '%s'", base_hint)
        return target

    options = sorted(targets.keys())
    if len(options) == 1:
        return targets[options[0]]

    print("Select a duo worktree pair:")
    for idx, base in enumerate(options, start=1):
        print(f"  {idx}. {base}")
    choice = input("Enter number: ").strip()
    if choice.isdigit():
        index = int(choice) - 1
        if 0 <= index < len(options):
            return targets[options[index]]
    error_exit("Invalid selection for merge target")


def _prompt_keep_choice() -> str:
    print("Which branch would you like to keep?")
    print("  1. claude")
    print("  2. codex")
    choice = input("Enter number: ").strip()
    if choice == "1":
        return "claude"
    if choice == "2":
        return "codex"
    error_exit("Invalid selection for branch to keep")


def _losing_branch(target: DuoTarget, keep: str) -> Tuple[str, Path]:
    if keep == "claude":
        return target.codex_branch, target.codex_path
    return target.claude_branch, target.claude_path


def _keeping_branch(target: DuoTarget, keep: str) -> Tuple[str, Path]:
    if keep == "claude":
        return target.claude_branch, target.claude_path
    return target.codex_branch, target.codex_path


def _worktree_dirty(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "status", "--short"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        warning("Failed to inspect %s: %s", path, result.stderr.strip())
        return False
    return bool(result.stdout.strip())


def _find_related_windows(base: str, branches: List[str]) -> List[str]:
    windows = list_windows()
    matches: List[str] = []
    for window_id, _session, name in windows:
        haystack = name.lower()
        if base.lower() in haystack:
            matches.append(window_id)
            continue
        for branch in branches:
            if branch.lower() in haystack:
                matches.append(window_id)
                break
    return matches


def _print_summary(
    *,
    target: DuoTarget,
    keep: str,
    losing_branch: str,
    losing_path: Path,
    keeping_branch: str,
    keeping_path: Path,
    keeping_dirty: bool,
    losing_dirty: bool,
    windows_to_kill: List[str],
) -> None:
    print("\n========================================")
    print(f"Base: {target.base}")
    print(f"Keep branch: {keep} ({keeping_branch})")
    print(f"Lose branch: {losing_branch}")
    print(f"Keep path:  {keeping_path}")
    print(f"Lose path:  {losing_path}")
    if keeping_dirty:
        print(f"\nNote: keeping branch {keeping_branch} has unstaged changes (will remain intact).")
    if losing_dirty:
        print(f"\nWarning: losing branch {losing_branch} has unstaged changes (will be discarded).")
    if windows_to_kill:
        print("\nTmux windows to close:")
        for window_id in windows_to_kill:
            print(f"  - {window_id}")
    print("========================================\n")


def _confirm() -> bool:
    response = input("Proceed with cleanup? (y/N): ").strip().lower()
    return response in {"y", "yes"}


def _cleanup_branch(branch: str, path: Path) -> None:
    if path.exists():
        result = subprocess.run([
            "git",
            "worktree",
            "remove",
            str(path),
            "--force",
        ])
        if result.returncode == 0:
            success("Removed worktree %s", path)
        else:
            warning("Failed to remove worktree %s (exit %s)", path, result.returncode)
    result = subprocess.run(["git", "branch", "-D", branch])
    if result.returncode == 0:
        success("Deleted branch %s", branch)
    else:
        warning("Failed to delete branch %s (exit %s)", branch, result.returncode)
