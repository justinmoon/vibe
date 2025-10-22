from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

from .agent_selector import prompt_agent_selection
from .args import parse_args
from .config import Config
from .run import run_duo, run_duo_review, run_single
from .tmux import (
    attach_session,
    configure_tmux,
    ensure_tmux_available,
    list_vibe_sessions,
    new_session,
    session_exists,
    switch_client,
)


def get_session_name(custom: str | None) -> str:
    if custom:
        return f"vibe-{custom}"
    return f"vibe-{Path.cwd().name}"


def inside_tmux() -> bool:
    return bool(os.environ.get("TMUX"))


def handle_session_only(session_name: str) -> None:
    if session_exists(session_name):
        switch_client(session_name)
    else:
        new_session(session_name, Path.cwd(), detached=True)
        switch_client(session_name)





def main(argv: List[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] == "rules":
        from .rules_cli import handle_rules_command

        handle_rules_command(args[1:])
        return
    if args and args[0] == "merge":
        from .merge_cli import handle_merge_command

        handle_merge_command(args[1:])
        return
    if args and args[0] == "review":
        from .review_cli import handle_review_command

        handle_review_command(args[1:])
        return
    # Check for help flag before doing anything else
    if "--help" in args or "-h" in args:
        cfg = parse_args(args)
        return
    
    ensure_tmux_available()

    # Require vibe to be run inside an existing tmux session
    if not inside_tmux():
        from .output import error_exit
        error_exit("Error: vibe must be run inside an existing tmux session. Please run 'tmux' first.")

# Check if any agent-specific flags are provided
    has_agent_flags = any(arg in args for arg in ["--codex", "--amp", "--oc", "--duo", "--duo-review"])
    selection = None
    
    # If no agent flags provided, prompt for agent selection
    if not has_agent_flags:
        selection = prompt_agent_selection()
        if not selection:
            return
        
        mode, duo_agents = selection
        
        # Update args based on selection
        if mode == "duo":
            args.append("--duo")
        elif mode == "review":
            args.append("--duo-review")
        elif duo_agents and duo_agents[0]:
            # Single agent mode with selected agent
            agent = duo_agents[0]
            if agent == "codex":
                args.append("--codex")
            elif agent == "amp":
                args.append("--amp")
            elif agent == "oc":
                args.append("--oc")
            # claude is default, no flag needed

    cfg = parse_args(args)
    
    # Set duo agents if they were selected
    if selection:
        mode, agents_info = selection
        if mode == "duo" and agents_info and len(agents_info) == 4:
            cfg.duo_agents = agents_info
        elif mode in ["single", "review"] and agents_info and len(agents_info) == 2:
            # For single/review mode, agents_info is (agent, model)
            agent, model = agents_info
            if agent == "oc" and model:
                # Store model in a way that can be accessed later
                cfg.selected_model = model
    
    configure_tmux(cfg.tmux_socket)

    if cfg.list_sessions:
        list_vibe_sessions()
        return

    session_name = get_session_name(cfg.session_name)

    if not cfg.prompt:
        handle_session_only(session_name)
        return

    if cfg.agent_mode == "dual":
        run_duo(cfg)
    elif cfg.agent_mode == "review":
        run_duo_review(cfg)
    else:
        run_single(cfg)


if __name__ == "__main__":
    main()
