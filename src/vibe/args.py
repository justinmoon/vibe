from __future__ import annotations

import argparse
import os
import re
import textwrap
from typing import List

from .config import Config, DEFAULT_EDITOR
from .output import info, warning
from .prompt import gather_prompt


def parse_args(argv: List[str]) -> Config:
    description = textwrap.dedent(
        """\
        Usage: vibe [OPTIONS] [TEXT]

        Options:
          -s, --session NAME  Use specific session name (default: current directory name)
          -p, --project PATH  Set project directory
          -i, --stdin         Read input from standard input
          -e, --editor        Open editor for composing message
          -f, --file FILE     Read input from file
          --no-worktree       Run in current directory without creating a worktree
          --from BRANCH       Start from specified branch instead of master
          --from-master       When in worktree, branch from master instead of current branch
          --list              List all active vibe sessions
          --codex             Use codex agent instead of claude
          --duo               Run both claude and codex in a split tmux window
          --amp               Use amp agent instead of claude
          --oc                Use oc (opencode) agent instead of claude
          --command NAME      Codex command name (only meaningful for codex)
          -h, --help          Show this help message

        Examples:
          vibe "Single line message"           # Uses vibe-<current-dir> session
          vibe -s myproject "fix bug"          # Uses vibe-myproject session
          echo "Multi-line text" | vibe -i
          vibe -e                              # Opens editor
          vibe -f message.txt                  # Read from file
          vibe -p /path/to/project "fix bug"   # Run in specific project
          vibe --from feature-branch "add tests"  # Start from feature-branch
          vibe --list                          # Show all vibe sessions
        """
    )

    parser = argparse.ArgumentParser(
        prog="vibe",
        add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=description,
    )

    parser.add_argument("-s", "--session", dest="session_name")
    parser.add_argument("-p", "--project", dest="project_path")
    parser.add_argument("-i", "--stdin", dest="stdin", action="store_true")
    parser.add_argument("-e", "--editor", dest="editor_mode", action="store_true")
    parser.add_argument("-f", "--file", dest="input_file")
    parser.add_argument("--no-worktree", action="store_true")
    parser.add_argument("--from", dest="from_branch")
    parser.add_argument("--from-master", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--codex", action="store_true")
    parser.add_argument("--duo", action="store_true")
    parser.add_argument("--amp", action="store_true")
    parser.add_argument("--oc", action="store_true")
    parser.add_argument("--command", dest="codex_command_name")
    parser.add_argument("--tmux-socket", dest="tmux_socket")
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("text", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)

    if args.help:
        info(description)
        raise SystemExit(0)

    input_mode = "args"
    if args.stdin:
        input_mode = "stdin"
    elif args.editor_mode:
        input_mode = "editor"
    elif args.input_file:
        input_mode = "file"

    agent_cmd = "claude"
    if args.codex:
        agent_cmd = "codex"
    elif args.amp:
        agent_cmd = "amp"
    elif args.oc:
        agent_cmd = "oc"

    cfg = Config(
        session_name=args.session_name,
        project_path=args.project_path,
        input_mode=input_mode,
        input_file=args.input_file,
        no_worktree=args.no_worktree,
        from_branch=args.from_branch,
        from_master=args.from_master,
        list_sessions=args.list,
        agent_cmd=agent_cmd,
        agent_mode="dual" if args.duo else "single",
        codex_command_name=args.codex_command_name,
        prompt="",
        raw_args=argv,
        editor=os.environ.get("EDITOR", DEFAULT_EDITOR),
        tmux_socket=args.tmux_socket or os.environ.get("VIBE_TMUX_SOCKET"),
    )

    cfg.prompt = gather_prompt(cfg, args.text)
    cfg.prompt = cfg.prompt.rstrip("\n")

    if not cfg.codex_command_name and cfg.prompt.startswith("/"):
        parts = cfg.prompt.split(maxsplit=1)
        candidate = parts[0][1:]
        if re.fullmatch(r"[A-Za-z0-9_-]+", candidate or ""):
            cfg.codex_command_name = candidate
            cfg.prompt = parts[1].strip() if len(parts) > 1 else ""

    if cfg.agent_mode == "dual" and cfg.agent_cmd != "claude":
        warning("Warning: --duo mode runs claude + codex and ignores single-agent overrides")
        cfg.agent_cmd = "claude"

    return cfg
