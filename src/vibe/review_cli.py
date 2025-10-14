from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from .config import Config
from .output import error_exit, info
from .run import run_duo_review, run_single


def handle_review_command(argv: Iterable[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="vibe review",
        description="Review worktrees created by vibe",
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="Project directory containing the review worktrees (defaults to cwd)",
    )
    parser.add_argument(
        "--base",
        help="Specific duo base name to review",
    )
    parser.add_argument(
        "--duo",
        action="store_true",
        help="Run claude+codex review (default if worktree pair detected).",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Run a single-agent review instead of duo",
    )
    parser.add_argument(
        "--codex",
        action="store_true",
        help="Use codex for single-agent review",
    )
    parser.add_argument(
        "--prompt",
        default="Review the completed work, list issues, missing tests, and merge readiness.",
        help="Custom review prompt",
    )

    args = parser.parse_args(list(argv))

    project = args.project.resolve() if args.project else Path.cwd()
    cfg = Config(
        session_name=None,
        project_path=str(project),
        input_mode="args",
        input_file=None,
        no_worktree=True,
        branch_name=None,
        from_branch=None,
        from_master=False,
        list_sessions=False,
        agent_cmd="claude" if not args.codex else "codex",
        agent_mode="single",
        codex_command_name=None,
        prompt=args.prompt,
        raw_args=list(argv),
        editor=None,
        tmux_socket=None,
        review_base=args.base,
    )

    if args.single:
        run_single(cfg)
        return

    cfg.agent_mode = "review"
    run_duo_review(cfg)

