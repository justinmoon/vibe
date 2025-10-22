from __future__ import annotations

import os
import time
from pathlib import Path

from .agents import build_agent_command, build_claude_command, build_codex_command, build_oc_command, get_agent_flags
from .config import Config
from .gitops import current_branch, determine_source_ref, ensure_git_repo, pull_latest_changes, run_init_script
from .openai_client import generate_branch_name
from .output import error_exit, info, success
from .tmux import (
    current_pane,
    new_window,
    send_keys,
    set_pane_title,
    set_window_dir,
    split_window,
)
from .worktree import (
    prepare_agent_worktree,
    read_duo_prompt,
    resolve_review_target,
    setup_worktree,
    write_duo_prompt,
)


def build_command_for_agent(agent: str, context: str, prompt: str, codex_command_name: str | None = None, model: str | None = None) -> str:
    """Build the appropriate command for any agent."""
    if agent == "claude":
        return build_claude_command(context, prompt)
    elif agent == "codex":
        return build_codex_command(context, prompt, codex_command_name)
    elif agent == "oc":
        return build_oc_command(context, prompt, model)
    else:
        # Fallback to generic command building
        agent_flags = get_agent_flags(agent)
        return build_agent_command(agent, agent_flags, context, prompt, codex_command_name)


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

    # Handle model selection for oc agent
    model = getattr(cfg, 'selected_model', None)
    if cfg.agent_cmd == "oc":
        command = build_oc_command(context, cfg.prompt, model)
    else:
        agent_flags = get_agent_flags(cfg.agent_cmd)
        command = build_agent_command(cfg.agent_cmd, agent_flags, context, cfg.prompt, cfg.codex_command_name)
    send_keys(window_id, command, "C-m")

    success("\u2713 Successfully started %s in current directory in window: %s", cfg.agent_cmd, window_id)


def run_with_worktree(cfg: Config) -> None:
    repo_root = Path.cwd()
    if cfg.branch_name:
        from .worktree import validate_branch_name
        validate_branch_name(cfg.branch_name)
        branch_name = cfg.branch_name
    else:
        branch_name = generate_branch_name(cfg.prompt)
    worktree_path = setup_worktree(branch_name, cfg)
    if not worktree_path.is_absolute():
        worktree_path = (repo_root / worktree_path).resolve()

    cwd = worktree_path
    if not cwd.is_dir():
        error_exit("Error: Expected worktree directory at '%s' but it was not created.", cwd)
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

    # Handle model selection for oc agent
    model = getattr(cfg, 'selected_model', None)
    if cfg.agent_cmd == "oc":
        command = build_oc_command(context, cfg.prompt, model)
    else:
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

    # Get the agents for duo mode
    if cfg.duo_agents and len(cfg.duo_agents) == 4:
        agent1, agent2, model1, model2 = cfg.duo_agents
    else:
        # Fallback to default claude+codex
        agent1, agent2, model1, model2 = "claude", "codex", None, None

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

    set_pane_title(left_pane, agent1)
    set_pane_title(right_pane, agent2)

    shared_context = (
        f"You are working in the current directory at {cwd} on branch '{branch_name}'. Please be mindful that any changes "
        "you make will affect the current working directory. A parallel agent is collaborating on the same prompt in another pane."
    )
    agent1_context = f"{shared_context} You are the {agent1} agent."
    agent2_context = f"{shared_context} You are the {agent2} agent."

    agent1_cmd = build_command_for_agent(agent1, agent1_context, cfg.prompt, cfg.codex_command_name, model1)
    agent2_cmd = build_command_for_agent(agent2, agent2_context, cfg.prompt, cfg.codex_command_name, model2)

    send_keys(left_pane, agent1_cmd, "C-m")
    send_keys(right_pane, agent2_cmd, "C-m")

    success("\u2713 Started %s (left) and %s (right) in window: %s", agent1, agent2, window_id)


def run_duo_with_worktrees(cfg: Config) -> None:
    # Get the agents for duo mode
    if cfg.duo_agents and len(cfg.duo_agents) == 4:
        agent1, agent2, model1, model2 = cfg.duo_agents
    else:
        # Fallback to default claude+codex
        agent1, agent2, model1, model2 = "claude", "codex", None, None
    
    if cfg.branch_name:
        from .worktree import validate_branch_name
        validate_branch_name(cfg.branch_name)
        base_branch = cfg.branch_name
    else:
        base_branch = generate_branch_name(cfg.prompt)
    agent1_branch = f"{base_branch}-{agent1}"
    agent2_branch = f"{base_branch}-{agent2}"

    source_ref = determine_source_ref(cfg)
    agent1_worktree = prepare_agent_worktree(agent1, agent1_branch, source_ref)
    agent2_worktree = prepare_agent_worktree(agent2, agent2_branch, source_ref)

    write_duo_prompt(base_branch, cfg.prompt)

    run_init_script(agent1_worktree)
    if agent2_worktree != agent1_worktree:
        run_init_script(agent2_worktree)

    window_id = new_window(base_branch, agent1_worktree)
    left_pane = current_pane(window_id)
    right_pane = split_window(window_id, cwd=agent2_worktree)

    set_window_dir(window_id, agent1_worktree)

    send_keys(left_pane, "C-m")
    time.sleep(0.1)
    send_keys(right_pane, "C-m")

    set_pane_title(left_pane, agent1)
    set_pane_title(right_pane, agent2)

    agent1_context = (
        f"You are working in a git worktree branch '{agent1_branch}' located at {agent1_worktree}. IMPORTANT: Do not write/edit/create files "
        f"in the main repository root (outside this worktree). Another agent ({agent2}) is working on '{agent2_branch}'; coordinate by keeping your "
        "changes isolated to this worktree."
    )
    agent2_context = (
        f"You are working in a git worktree branch '{agent2_branch}' located at {agent2_worktree}. IMPORTANT: Do not write/edit/create files "
        f"in the main repository root (outside this worktree). Another agent ({agent1}) is simultaneously working on '{agent1_branch}'."
    )

    agent1_cmd = build_command_for_agent(agent1, agent1_context, cfg.prompt, cfg.codex_command_name, model1)
    agent2_cmd = build_command_for_agent(agent2, agent2_context, cfg.prompt, cfg.codex_command_name, model2)

    send_keys(left_pane, agent1_cmd, "C-m")
    send_keys(right_pane, agent2_cmd, "C-m")

    success(
        "\u2713 Started %s (left) on %s and %s (right) on %s in window: %s",
        agent1,
        agent1_branch,
        agent2,
        agent2_branch,
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

    original_prompt = read_duo_prompt(base)

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
    if not cfg.prompt and original_prompt:
        info("Original duo prompt:\n%s", original_prompt)
    shared_context = (
        f"You are reviewing existing work for feature base '{base}'. The claude worktree is located at {claude_path} "
        f"on branch '{claude_branch}', and the codex worktree is located at {codex_path} on branch '{codex_branch}'. "
        "Inspect the changes, run git commands as needed, and provide clear feedback on quality, correctness, and next steps."\
        " Compare both branches: identify which implementation is stronger, where one outperforms the other, and whether "
        "a hybrid (combining specific commits or files) would deliver the best result."
    )
    if original_prompt:
        shared_context += "\n\nOriginal prompt:\n```\n" + original_prompt.strip() + "\n```"
    if cfg.prompt:
        shared_context += "\n\nReview prompt:\n```\n" + cfg.prompt.strip() + "\n```"

    claude_context = shared_context + (
        " Focus on high-level reasoning, risks, and recommended follow-ups."
        " Make an explicit recommendation: choose claude's branch, codex's branch, or a mix, and justify why."
    )
    codex_context = shared_context + (
        " Focus on concrete diffs, reproduction steps, and actionable fixes."
        " Identify exact commits/files to cherry-pick if a hybrid approach is best, and note any merge hazards."
    )

    claude_cmd = build_claude_command(claude_context, review_prompt)
    codex_cmd = build_codex_command(codex_context, review_prompt, cfg.codex_command_name)

    send_keys(left_pane, claude_cmd, "C-m")
    send_keys(right_pane, codex_cmd, "C-m")

    success(
        "\u2713 Started review for base '%s' (claude left, codex right) in window: %s",
        base,
        window_id,
    )
