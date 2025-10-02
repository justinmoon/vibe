from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

from .output import error_exit, info, success, warning
from .tmux import kill_window, list_windows
from .worktree import WORKTREE_BASE, list_duo_targets


@dataclass
class DuoTarget:
    base: str
    repo_root: Path
    claude_branch: str
    claude_path: Path
    codex_branch: str
    codex_path: Path


def handle_merge_command(argv: Iterable[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="vibe merge",
        description="Merge a duo worktree branch into a target branch",
    )
    parser.add_argument("--base", help="Base name of the duo worktree pair")
    parser.add_argument(
        "--keep",
        choices=["claude", "codex"],
        help="Which agent branch to merge",
    )
    parser.add_argument(
        "--into",
        dest="target_branch",
        help="Branch to merge into (defaults to current branch in repo root)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--ff-only",
        action="store_true",
        help="Use fast-forward merge only",
    )
    group.add_argument(
        "--no-ff",
        action="store_true",
        help="Force a merge commit (default behaviour)",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip fetching from origin before merging",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed even if the target branch is dirty",
    )

    args = parser.parse_args(list(argv))

    targets = _collect_duo_targets()
    if not targets:
        error_exit("No duo worktrees found. Run `vibe --duo` before merging.")

    target = _choose_target(targets, args.base)
    keep = args.keep or _prompt_keep_choice()

    keeping_branch, keeping_path = _keeping_branch(target, keep)
    repo_root = target.repo_root

    if not keeping_path.exists():
        error_exit("Worktree for branch %s no longer exists at %s", keeping_branch, keeping_path)

    if _worktree_dirty(keeping_path) and not args.force:
        error_exit(
            "Unstaged changes detected in %s. Commit or stash before merging, or re-run with --force.",
            keeping_branch,
        )

    target_branch = args.target_branch or _detect_current_branch(repo_root)
    if not target_branch:
        error_exit("Unable to determine target branch. Use --into to specify explicitly.")

    if not args.no_fetch:
        _run_git(repo_root, ["fetch", "--all"], check=False)

    if _worktree_dirty(repo_root) and not args.force:
        error_exit(
            "Target branch %s has unstaged changes. Commit or stash before merging, or re-run with --force.",
            target_branch,
        )

    current_branch = _detect_current_branch(repo_root)
    if current_branch != target_branch:
        success("Checking out %s in %s", target_branch, repo_root)
        _run_git(repo_root, ["checkout", target_branch])

    merge_args = ["merge"]
    if args.ff_only:
        merge_args.append("--ff-only")
    else:
        merge_args.append("--no-ff")
        merge_args.append("--no-edit")
    merge_args.append(keeping_branch)

    success("Merging %s into %s", keeping_branch, target_branch)
    result = _run_git(repo_root, merge_args, check=False)
    if result != 0:
        warning(
            "Merge command exited with status %s. Resolve conflicts manually, then rerun `vibe merge` if needed.",
            result,
        )
        return

    success("Merge completed. Review changes, run tests, and push when ready.")

    _offer_cleanup(target)


def _collect_duo_targets() -> Dict[str, DuoTarget]:
    raw = list_duo_targets()
    targets: Dict[str, DuoTarget] = {}
    for base, (claude_branch, claude_path, codex_branch, codex_path) in raw.items():
        repo_root = _git_repo_root(claude_path) or _git_repo_root(codex_path)
        if repo_root is None:
            warning("Skipping pair %s: unable to determine repository root", base)
            continue
        targets[base] = DuoTarget(
            base=base,
            repo_root=repo_root,
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
    print("Which branch would you like to merge?")
    print("  1. claude")
    print("  2. codex")
    choice = input("Enter number: ").strip()
    if choice == "1":
        return "claude"
    if choice == "2":
        return "codex"
    error_exit("Invalid selection for branch to merge")


def _keeping_branch(target: DuoTarget, keep: str) -> tuple[str, Path]:
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


def _git_toplevel(path: Path) -> Optional[Path]:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def _detect_current_branch(repo_root: Path) -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch if branch and branch != "HEAD" else None


def _run_git(repo_root: Path, args: Iterable[str], *, check: bool = True) -> int:
    cmd = ["git", "-C", str(repo_root), *args]
    result = subprocess.run(cmd)
    if check and result.returncode != 0:
        error_exit("Command failed: %s", " ".join(cmd))
    return result.returncode


def _find_related_windows(target: DuoTarget):
    matches = []
    for window_id, session, name in list_windows():
        lower = name.lower()
        if target.base.lower() in lower:
            matches.append((window_id, session, name))
            continue
        if target.claude_branch.lower() in lower or target.codex_branch.lower() in lower:
            matches.append((window_id, session, name))
    return matches


def _git_repo_root(path: Path) -> Optional[Path]:
    for flag in ("--show-toplevel", "--git-common-dir"):
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", flag],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            resolved = Path(result.stdout.strip())
            if flag == "--git-common-dir":
                if resolved.name == ".git":
                    return resolved.parent
                if resolved.name == "worktrees":
                    git_dir = resolved.parent
                    if git_dir.name == ".git":
                        return git_dir.parent
            else:
                return resolved
    return None


def _offer_cleanup(target: DuoTarget) -> None:
    response = input(
        f"Cleanup worktrees, branches, and tmux windows for base '{target.base}'? (y/N): "
    ).strip().lower()
    if response not in {"y", "yes"}:
        return

    cleanup_tasks = [
        ("worktree", target.claude_path),
        ("worktree", target.codex_path),
        ("branch", target.claude_branch),
        ("branch", target.codex_branch),
        ("prompt", WORKTREE_BASE / f"{target.base}.prompt"),
    ]

    for kind, value in cleanup_tasks:
        if kind == "worktree":
            _remove_worktree(target.repo_root, value)
        elif kind == "branch":
            _delete_branch(target.repo_root, value)
        elif kind == "prompt":
            _delete_file(value)

    for window_id, _, name in _find_related_windows(target):
        kill_window(window_id, delay=False)
        info("Closed tmux window %s", name)

    success("Cleanup complete for base '%s'", target.base)


def _remove_worktree(repo_root: Path, path: Path) -> None:
    if not path.exists():
        return
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "worktree",
            "remove",
            str(path),
            "--force",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        warning("Failed to remove worktree %s: %s", path, result.stderr.strip())
    else:
        success("Removed worktree %s", path)


def _delete_branch(repo_root: Path, branch: str) -> None:
    if not branch:
        return
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "branch",
            "-D",
            branch,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        warning("Failed to delete branch %s: %s", branch, result.stderr.strip())
    else:
        success("Deleted branch %s", branch)


def _delete_file(path: Path) -> None:
    if path.exists():
        path.unlink()
        info("Deleted %s", path)
