from __future__ import annotations

import os
import time
from pathlib import Path

from .agents import build_agent_command, build_claude_command, build_codex_command, get_agent_flags
from .config import Config
from .gitops import current_branch, determine_source_ref, ensure_git_repo, pull_latest_changes, run_init_script
from .openai_client import generate_branch_name
from .output import success
from .tmux import (
    current_pane,
    new_window,
    send_keys,
    set_pane_title,
    set_window_dir,
    split_window,
)
from .worktree import prepare_agent_worktree, resolve_review_target, setup_worktree


def run_single(cfg: Config) -> None:
    if cfg.project_path:
        project = Path(cfg.project_path)
        if not project.is_dir():
            from .output import error_exit

            error_exit("Error: Project directory '%s' does not exist", cfg.project_path)
        os.chdir(project)

    ensure_git_repo()
    pull_latest_changes(cfg)

    if cfg.no_worktree:
        run_no_worktree(cfg)
    else:
        run_with_worktree(cfg)


def run_no_worktree(cfg: Config) -> None:
    success("Running in no-worktree mode (current directory)")
    branch_name = current_branch()
    cwd = Path.cwd()
    run_init_script(cwd)

    window_id = new_window(branch_name, cwd)
    set_window_dir(window_id, cwd)

    time.sleep(0.2)
    send_keys(window_id, "C-m")
    time.sleep(0.1)

    context = (
        f"You are working in the current directory at {cwd} on branch '{branch_name}'. "
        "Please be mindful that any changes you make will affect the current working directory."
    )

    agent_flags = get_agent_flags(cfg.agent_cmd)
    command = build_agent_command(cfg.agent_cmd, agent_flags, context, cfg.prompt, cfg.codex_command_name)
    send_keys(window_id, command, "C-m")

    success("\u2713 Successfully started %s in current directory in window: %s", cfg.agent_cmd, window_id)


def run_with_worktree(cfg: Config) -> None:
    branch_name = generate_branch_name(cfg.prompt)
    worktree_path = setup_worktree(branch_name, cfg)

    cwd = worktree_path
    os.chdir(cwd)
    success("Working directory: %s", cwd)
    run_init_script(cwd)

    window_id = new_window(branch_name, cwd)
    set_window_dir(window_id, cwd)

    time.sleep(0.2)
    send_keys(window_id, "C-m")
    time.sleep(0.1)

    context = (
        f"You are working in a git worktree branch '{branch_name}' located at {cwd}. IMPORTANT: Do not write/edit/create files "
        "in the main repository root (outside this worktree). You can write to this worktree directory and to other unrelated "
        "paths like ~/configs, but avoid modifying the parent repository. You can read files from anywhere for context. This ensures "
        "your changes are isolated to this feature branch."
    )

    agent_flags = get_agent_flags(cfg.agent_cmd)
    command = build_agent_command(cfg.agent_cmd, agent_flags, context, cfg.prompt, cfg.codex_command_name)
    send_keys(window_id, command, "C-m")

    success("\u2713 Successfully created worktree and started %s in window: %s", cfg.agent_cmd, window_id)


def run_duo(cfg: Config) -> None:
    if cfg.project_path:
        project = Path(cfg.project_path)
        if not project.is_dir():
            from .output import error_exit

            error_exit("Error: Project directory '%s' does not exist", cfg.project_path)
        os.chdir(project)

    ensure_git_repo()
    pull_latest_changes(cfg)

    if cfg.no_worktree:
        run_duo_no_worktree(cfg)
    else:
        run_duo_with_worktrees(cfg)


def run_duo_no_worktree(cfg: Config) -> None:
    branch_name = current_branch()
    cwd = Path.cwd()
    run_init_script(cwd)

    window_name = f"{branch_name}-duo"
    window_id = new_window(window_name, cwd)
    left_pane = current_pane(window_id)
    right_pane = split_window(window_id, cwd=cwd)
    set_window_dir(window_id, cwd)

    send_keys(left_pane, "C-m")
    time.sleep(0.1)
    send_keys(right_pane, "C-m")
    time.sleep(0.1)
    time.sleep(0.1)

    set_pane_title(left_pane, "claude")
    set_pane_title(right_pane, "codex")

    shared_context = (
        f"You are working in the current directory at {cwd} on branch '{branch_name}'. Please be mindful that any changes "
        "you make will affect the current working directory. A parallel agent is collaborating on the same prompt in another pane."
    )
    claude_context = f"{shared_context} You are the claude agent; focus on high-level reasoning and clarity."
    codex_context = f"{shared_context} You are the codex agent; focus on precise execution and coding speed."

    claude_cmd = build_claude_command(claude_context, cfg.prompt)
    codex_cmd = build_codex_command(codex_context, cfg.prompt, cfg.codex_command_name)

    send_keys(left_pane, claude_cmd, "C-m")
    send_keys(right_pane, codex_cmd, "C-m")

    success("\u2713 Started claude (left) and codex (right) in window: %s", window_id)


def run_duo_with_worktrees(cfg: Config) -> None:
    base_branch = generate_branch_name(cfg.prompt)
    claude_branch = f"{base_branch}-claude"
    codex_branch = f"{base_branch}-codex"

    source_ref = determine_source_ref(cfg)
    claude_worktree = prepare_agent_worktree("claude", claude_branch, source_ref)
    codex_worktree = prepare_agent_worktree("codex", codex_branch, source_ref)

    run_init_script(claude_worktree)
    if codex_worktree != claude_worktree:
        run_init_script(codex_worktree)

    window_id = new_window(base_branch, claude_worktree)
    left_pane = current_pane(window_id)
    right_pane = split_window(window_id, cwd=codex_worktree)

    set_window_dir(window_id, claude_worktree)

    send_keys(left_pane, "C-m")
    time.sleep(0.1)
    send_keys(right_pane, "C-m")

    set_pane_title(left_pane, "claude")
    set_pane_title(right_pane, "codex")

    claude_context = (
        f"You are working in a git worktree branch '{claude_branch}' located at {claude_worktree}. IMPORTANT: Do not write/edit/create files "
        "in the main repository root (outside this worktree). Another agent (codex) is working on '{codex_branch}'; coordinate by keeping your "
        "changes isolated to this worktree."
    )
    codex_context = (
        f"You are working in a git worktree branch '{codex_branch}' located at {codex_worktree}. IMPORTANT: Do not write/edit/create files "
        "in the main repository root (outside this worktree). Another agent (claude) is simultaneously working on '{claude_branch}'."
    )

    claude_cmd = build_claude_command(claude_context, cfg.prompt)
    codex_cmd = build_codex_command(codex_context, cfg.prompt, cfg.codex_command_name)

    send_keys(left_pane, claude_cmd, "C-m")
    send_keys(right_pane, codex_cmd, "C-m")

    success(
        "\u2713 Started claude (left) on %s and codex (right) on %s in window: %s",
        claude_branch,
        codex_branch,
        window_id,
    )


def run_duo_review(cfg: Config) -> None:
    if cfg.project_path:
        project = Path(cfg.project_path)
        if not project.is_dir():
            from .output import error_exit

            error_exit("Error: Project directory '%s' does not exist", cfg.project_path)
        os.chdir(project)

    ensure_git_repo()

    base, claude_branch, claude_path, codex_branch, codex_path = resolve_review_target(cfg.review_base)

    run_init_script(claude_path)
    if codex_path != claude_path:
        run_init_script(codex_path)

    window_name = f"{base}-review"
    window_id = new_window(window_name, claude_path)
    left_pane = current_pane(window_id)
    right_pane = split_window(window_id, cwd=codex_path)

    set_window_dir(window_id, claude_path)

    send_keys(left_pane, "C-m")
    time.sleep(0.1)
    send_keys(right_pane, "C-m")
    time.sleep(0.1)

    set_pane_title(left_pane, "claude")
    set_pane_title(right_pane, "codex")

    review_prompt = cfg.prompt or "Review the completed work, list issues, missing tests, and merge readiness."
    shared_context = (
        f"You are reviewing existing work for feature base '{base}'. The claude worktree is located at {claude_path} "
        f"on branch '{claude_branch}', and the codex worktree is located at {codex_path} on branch '{codex_branch}'. "
        "Inspect the changes, run git commands as needed, and provide clear feedback on quality, correctness, and next steps."
    )
    claude_context = shared_context + " Focus on high-level reasoning, risks, and recommended follow-ups."
    codex_context = shared_context + " Focus on concrete diffs, reproduction steps, and actionable fixes."

    claude_cmd = build_claude_command(claude_context, review_prompt)
    codex_cmd = build_codex_command(codex_context, review_prompt, cfg.codex_command_name)

    send_keys(left_pane, claude_cmd, "C-m")
    send_keys(right_pane, codex_cmd, "C-m")

    success(
        "\u2713 Started review for base '%s' (claude left, codex right) in window: %s",
        base,
        window_id,
    )
