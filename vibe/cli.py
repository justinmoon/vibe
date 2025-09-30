from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

WORKTREE_BASE = Path("./worktrees")
DEFAULT_EDITOR = os.environ.get("EDITOR", "helix")


@dataclass
class Config:
    session_name: Optional[str]
    project_path: Optional[str]
    input_mode: str
    input_file: Optional[str]
    no_worktree: bool
    from_branch: Optional[str]
    from_master: bool
    list_sessions: bool
    agent_cmd: str
    agent_mode: str
    codex_command_name: Optional[str]
    prompt: str
    raw_args: List[str] = field(default_factory=list)
    editor: str = DEFAULT_EDITOR


def print_success(message: str, *args: object) -> None:
    print(GREEN + (message % args if args else message) + NC)


def print_warning(message: str, *args: object) -> None:
    print(YELLOW + (message % args if args else message) + NC, file=sys.stderr)


def print_error(message: str, *args: object) -> None:
    print(RED + (message % args if args else message) + NC, file=sys.stderr)


def error_exit(message: str, *args: object, exit_code: int = 1) -> None:
    print_error(message, *args)
    sys.exit(exit_code)


def info(message: str, *args: object) -> None:
    print(message % args if args else message)


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
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("text", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)

    if args.help:
        info(description)
        sys.exit(0)

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
        print_warning("Warning: --duo mode runs claude + codex and ignores single-agent overrides")
        cfg.agent_cmd = "claude"

    return cfg


def gather_prompt(cfg: Config, remaining: List[str]) -> str:
    if cfg.input_mode == "args":
        return " ".join(remaining).strip()
    if cfg.input_mode == "stdin":
        return sys.stdin.read()
    if cfg.input_mode == "editor":
        return open_editor(cfg.editor)
    if cfg.input_mode == "file":
        if not cfg.input_file or not Path(cfg.input_file).is_file():
            error_exit("Error: File '%s' not found", cfg.input_file or "")
        return Path(cfg.input_file).read_text()
    return ""


def open_editor(editor: str) -> str:
    fd, tmp_path = tempfile.mkstemp(prefix="vibe.", text=True)
    os.close(fd)
    tmp = Path(tmp_path)
    try:
        tmp.write_text(
            "# Enter your message below. Lines starting with # will be ignored.\n"
            "# Save and exit when done.\n\n"
        )

        editor_cmd = build_editor_command(editor, tmp)
        try:
            subprocess.run(editor_cmd, check=True)
        except FileNotFoundError:
            error_exit("Error: Editor '%s' not found", editor)
        except subprocess.CalledProcessError as exc:
            error_exit("Error: Editor exited with code %s", exc.returncode)

        lines = [line for line in tmp.read_text().splitlines() if not line.startswith("#")]
        return "\n".join(lines)
    finally:
        tmp.unlink(missing_ok=True)


def build_editor_command(editor: str, path: Path) -> List[str]:
    if editor in {"vim", "nvim"}:
        return [editor, str(path), "+4"]
    if editor in {"helix", "hx"}:
        return [editor, f"{path}:4:1"]
    if editor == "nano":
        return [editor, str(path), "+4"]
    if editor == "emacs":
        return [editor, str(path), "+4"]
    return [editor, str(path)]


def ensure_tmux_available() -> None:
    if shutil.which("tmux") is None:
        error_exit("Error: tmux not found. Please install tmux to use vibe.")


def ensure_git_repo() -> None:
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        error_exit("Error: Not in a git repository")


def tmux_session_exists(name: str) -> bool:
    result = subprocess.run(["tmux", "has-session", "-t", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def tmux_cmd(args: List[str], capture: bool = False) -> str:
    if capture:
        return subprocess.check_output(["tmux", *args], text=True).strip()
    subprocess.run(["tmux", *args], check=True)
    return ""


def list_sessions() -> None:
    output = subprocess.run(["tmux", "list-sessions"], capture_output=True, text=True)
    if output.returncode != 0:
        print_warning("  No active vibe sessions")
        return
    sessions = [line for line in output.stdout.splitlines() if line.startswith("vibe-")]
    if not sessions:
        print_success("Active vibe sessions:")
        print_warning("  No active vibe sessions")
        return
    print_success("Active vibe sessions:")
    for line in sessions:
        session = line.split(":", 1)[0]
        window_list = subprocess.run(["tmux", "list-windows", "-t", session], capture_output=True, text=True)
        count = len(window_list.stdout.splitlines()) if window_list.returncode == 0 else 0
        print(f"  {YELLOW}{session}{NC} ({count} windows)")


def get_session_name(custom: Optional[str]) -> str:
    if custom:
        return f"vibe-{custom}"
    return f"vibe-{Path.cwd().name}"


def inside_tmux() -> bool:
    return bool(os.environ.get("TMUX"))


def handle_session_only(session_name: str) -> None:
    if inside_tmux():
        if tmux_session_exists(session_name):
            print_success("Switching to session: %s", session_name)
            tmux_cmd(["switch-client", "-t", session_name])
        else:
            print_success("Creating new session: %s", session_name)
            tmux_cmd(["new-session", "-d", "-s", session_name])
            tmux_cmd(["switch-client", "-t", session_name])
        return

    if tmux_session_exists(session_name):
        print_success("Attaching to existing session: %s", session_name)
        tmux_cmd(["attach-session", "-d", "-t", session_name])
    else:
        print_success("Creating new session: %s", session_name)
        tmux_cmd(["new-session", "-s", session_name])


def run_with_tmux(session_name: str, cfg: Config) -> None:
    cwd = Path.cwd()
    if tmux_session_exists(session_name):
        fd, tmp_path = tempfile.mkstemp(prefix="vibe-run.", suffix=".sh")
        os.close(fd)
        temp_script = Path(tmp_path)
        try:
            content = f"#!/bin/bash\ncd {shlex.quote(str(cwd))}\nvibe {shlex.join(cfg.raw_args)}\nrm -f {shlex.quote(str(temp_script))}\n"
            temp_script.write_text(content)
            temp_script.chmod(0o755)
            cmd = f"tmux attach-session -d -t {shlex.quote(session_name)} \\; send-keys {shlex.quote(str(temp_script))} C-m"
            subprocess.run(cmd, shell=True, check=True)
        finally:
            temp_script.unlink(missing_ok=True)
    else:
        quoted_args = shlex.join(cfg.raw_args)
        cmd = (
            f"tmux new-session -s {shlex.quote(session_name)} -c {shlex.quote(str(cwd))} "
            f"\"vibe {quoted_args}; $SHELL\""
        )
        subprocess.run(cmd, shell=True, check=True)


def run_single(cfg: Config) -> None:
    if cfg.project_path:
        project = Path(cfg.project_path)
        if not project.is_dir():
            error_exit("Error: Project directory '%s' does not exist", cfg.project_path)
        os.chdir(project)

    ensure_git_repo()

    if not cfg.from_branch:
        print_success("Pulling latest changes from origin...")
        result = subprocess.run(["git", "pull", "--rebase"], capture_output=True, text=True)
        if result.returncode != 0:
            print_warning(
                "Warning: Could not pull latest changes. This might be due to:\n  - Uncommitted changes\n  - Network issues\n  - Remote repository issues\nContinuing anyway..."
            )
    else:
        print_success("Using --from branch: %s (skipping pull from origin)", cfg.from_branch)

    if cfg.no_worktree:
        run_no_worktree(cfg)
    else:
        run_with_worktree(cfg)


def run_no_worktree(cfg: Config) -> None:
    print_success("Running in no-worktree mode (current directory)")

    branch_result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    if branch_result.returncode != 0:
        print_warning("Error: Could not determine current branch")
        branch_name = "detached"
    else:
        branch_name = branch_result.stdout.strip()

    run_init_script(Path.cwd())

    window_id = create_tmux_window(branch_name, Path.cwd())
    set_window_dir(window_id, Path.cwd())

    time.sleep(0.2)
    tmux_cmd(["send-keys", "-t", window_id, "C-m"])
    time.sleep(0.1)

    context = (
        f"You are working in the current directory at {Path.cwd()} on branch '{branch_name}'. "
        "Please be mindful that any changes you make will affect the current working directory."
    )

    agent_flags = get_agent_flags(cfg.agent_cmd)
    send_agent_command(window_id, cfg.agent_cmd, agent_flags, context, cfg.prompt, cfg.codex_command_name)

    print_success("\u2713 Successfully started %s in current directory in window: %s", cfg.agent_cmd, window_id)


def run_with_worktree(cfg: Config) -> None:
    branch_name = generate_branch_name(cfg.prompt)

    worktree_path = setup_worktree(branch_name, cfg)

    os.chdir(worktree_path)
    cwd = Path.cwd()
    print_success("Working directory: %s", cwd)

    run_init_script(cwd)

    window_id = create_tmux_window(branch_name, cwd)
    set_window_dir(window_id, cwd)

    time.sleep(0.2)
    tmux_cmd(["send-keys", "-t", window_id, "C-m"])
    time.sleep(0.1)

    context = (
        f"You are working in a git worktree branch '{branch_name}' located at {cwd}. IMPORTANT: Do not write/edit/create files "
        "in the main repository root (outside this worktree). You can write to this worktree directory and to other unrelated "
        "paths like ~/configs, but avoid modifying the parent repository. You can read files from anywhere for context. This ensures "
        "your changes are isolated to this feature branch."
    )

    agent_flags = get_agent_flags(cfg.agent_cmd)
    send_agent_command(window_id, cfg.agent_cmd, agent_flags, context, cfg.prompt, cfg.codex_command_name)

    print_success("\u2713 Successfully created worktree and started %s in window: %s", cfg.agent_cmd, window_id)


def run_duo(cfg: Config) -> None:
    if cfg.project_path:
        project = Path(cfg.project_path)
        if not project.is_dir():
            error_exit("Error: Project directory '%s' does not exist", cfg.project_path)
        os.chdir(project)

    ensure_git_repo()

    if not cfg.from_branch:
        print_success("Pulling latest changes from origin...")
        result = subprocess.run(["git", "pull", "--rebase"], capture_output=True, text=True)
        if result.returncode != 0:
            print_warning(
                "Warning: Could not pull latest changes. This might be due to:\n  - Uncommitted changes\n  - Network issues\n  - Remote repository issues\nContinuing anyway..."
            )
    else:
        print_success("Using --from branch: %s (skipping pull from origin)", cfg.from_branch)

    if cfg.no_worktree:
        run_duo_no_worktree(cfg)
    else:
        run_duo_with_worktrees(cfg)


def run_duo_no_worktree(cfg: Config) -> None:
    print_success("Running in no-worktree mode (current directory) for claude + codex")

    branch_result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    if branch_result.returncode != 0:
        print_warning("Error: Could not determine current branch")
        branch_name = "detached"
    else:
        branch_name = branch_result.stdout.strip()

    run_init_script(Path.cwd())

    window_name = f"{branch_name}-duo"
    window_id = create_tmux_window(window_name, Path.cwd())

    try:
        tmux_cmd(["split-window", "-h", "-t", window_id, "-c", str(Path.cwd())])
    except subprocess.CalledProcessError:
        error_exit("Error: Could not split tmux window for codex pane")

    set_window_dir(window_id, Path.cwd())

    tmux_cmd(["select-pane", "-t", f"{window_id}.0"])
    tmux_cmd(["select-pane", "-T", "claude"])
    tmux_cmd(["select-pane", "-t", f"{window_id}.1"])
    tmux_cmd(["select-pane", "-T", "codex"])

    time.sleep(0.2)
    tmux_cmd(["send-keys", "-t", f"{window_id}.0", "C-m"])
    time.sleep(0.1)
    tmux_cmd(["send-keys", "-t", f"{window_id}.1", "C-m"])
    time.sleep(0.1)

    shared_context = (
        f"You are working in the current directory at {Path.cwd()} on branch '{branch_name}'. Please be mindful that any changes "
        "you make will affect the current working directory. A parallel agent is collaborating on the same prompt in another pane."
    )
    claude_context = f"{shared_context} You are the claude agent; focus on high-level reasoning and clarity."
    codex_context = f"{shared_context} You are the codex agent; focus on precise execution and coding speed."

    claude_cmd = build_agent_command("claude", "--dangerously-skip-permissions", claude_context, cfg.prompt, None)
    codex_cmd = build_agent_command("codex", "--dangerously-bypass-approvals-and-sandbox", codex_context, cfg.prompt, cfg.codex_command_name)

    send_command_to_pane(f"{window_id}.0", claude_cmd)
    send_command_to_pane(f"{window_id}.1", codex_cmd)

    print_success("\u2713 Started claude (left) and codex (right) in window: %s", window_id)


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

    window_id = create_tmux_window(base_branch, claude_worktree)

    try:
        tmux_cmd(["split-window", "-h", "-t", window_id, "-c", str(codex_worktree)])
    except subprocess.CalledProcessError:
        error_exit("Error: Could not split tmux window for codex pane")

    set_window_dir(window_id, claude_worktree)

    tmux_cmd(["select-pane", "-t", f"{window_id}.0"])
    tmux_cmd(["select-pane", "-T", "claude"])
    tmux_cmd(["select-pane", "-t", f"{window_id}.1"])
    tmux_cmd(["select-pane", "-T", "codex"])

    time.sleep(0.2)
    tmux_cmd(["send-keys", "-t", f"{window_id}.0", "C-m"])
    time.sleep(0.1)
    tmux_cmd(["send-keys", "-t", f"{window_id}.1", "C-m"])

    claude_context = (
        f"You are working in a git worktree branch '{claude_branch}' located at {claude_worktree}. IMPORTANT: Do not write/edit/create files "
        "in the main repository root (outside this worktree). Another agent (codex) is working on '{codex_branch}'; coordinate by keeping your "
        "changes isolated to this worktree."
    )
    codex_context = (
        f"You are working in a git worktree branch '{codex_branch}' located at {codex_worktree}. IMPORTANT: Do not write/edit/create files "
        "in the main repository root (outside this worktree). Another agent (claude) is simultaneously working on '{claude_branch}'."
    )

    claude_cmd = build_agent_command("claude", "--dangerously-skip-permissions", claude_context, cfg.prompt, None)
    codex_cmd = build_agent_command("codex", "--dangerously-bypass-approvals-and-sandbox", codex_context, cfg.prompt, cfg.codex_command_name)

    send_command_to_pane(f"{window_id}.0", claude_cmd)
    send_command_to_pane(f"{window_id}.1", codex_cmd)

    print_success(
        "\u2713 Started claude (left) on %s and codex (right) on %s in window: %s",
        claude_branch,
        codex_branch,
        window_id,
    )


def send_command_to_pane(pane_id: str, command: str) -> None:
    tmux_cmd(["send-keys", "-t", pane_id, command, "C-m"])


def run_init_script(path: Path) -> None:
    init_script = path / "scripts" / "init.sh"
    if init_script.is_file():
        print_success("Running worktree initialization script...")
        result = subprocess.run(["bash", str(init_script)], cwd=path)
        if result.returncode != 0:
            print_warning("Warning: Initialization script failed, continuing anyway...")


def create_tmux_window(name: str, cwd: Path) -> str:
    try:
        window_id = tmux_cmd([
            "new-window",
            "-n",
            name,
            "-c",
            str(cwd),
            "-P",
            "-F",
            "#{window_id}",
        ], capture=True)
    except subprocess.CalledProcessError:
        error_exit("Error: Could not create tmux window")
    print_success("Created tmux window: %s", window_id)
    return window_id


def set_window_dir(window_id: str, path: Path) -> None:
    result = subprocess.run(["tmux", "setw", "-t", window_id, "@window_dir", str(path)])
    if result.returncode != 0:
        print_warning("Warning: Could not set window directory variable")


def get_agent_flags(agent_cmd: str) -> str:
    if agent_cmd == "codex":
        return "--dangerously-bypass-approvals-and-sandbox"
    return "--dangerously-skip-permissions"


def build_agent_command(agent_cmd: str, agent_flags: str, context: str, prompt: str, codex_command_name: Optional[str]) -> str:
    message = context if not prompt else f"{context}\n\n{prompt}"
    fd, temp_path = tempfile.mkstemp(prefix="vibe-msg.")
    os.close(fd)
    temp = Path(temp_path)
    temp.write_text(message)
    temp_path = shlex.quote(str(temp))
    base = f"{agent_cmd} {agent_flags} \"$(cat {temp_path})\""
    if agent_cmd == "codex" and codex_command_name:
        base = f"{base} {shlex.quote(codex_command_name)}"
    return f"{base} && rm -f {temp_path}"


def send_agent_command(window_id: str, agent_cmd: str, agent_flags: str, context: str, prompt: str, codex_command_name: Optional[str]) -> None:
    command = build_agent_command(agent_cmd, agent_flags, context, prompt, codex_command_name)
    send_command_to_pane(window_id, command)


def setup_worktree(branch_name: str, cfg: Config) -> Path:
    ensure_worktree_dir()
    worktree_path = WORKTREE_BASE / branch_name

    existing = find_existing_worktree(branch_name)
    if existing:
        print_warning("Branch '%s' already has a worktree at: %s", branch_name, existing)
        if existing.is_dir():
            print_success("Using existing worktree at: %s", existing)
            return existing
        print_warning("Worktree directory doesn't exist. Pruning and recreating...")
        subprocess.run(["git", "worktree", "prune"], check=True)
        subprocess.run(["git", "worktree", "add", str(worktree_path), branch_name], check=True)
        return worktree_path

    if branch_exists(branch_name):
        print_success("Adding worktree for existing branch: %s", branch_name)
        subprocess.run(["git", "worktree", "add", str(worktree_path), branch_name], check=True)
        return worktree_path

    source_ref = determine_source_ref(cfg)

    print_success("Creating new branch and worktree: %s from %s", branch_name, source_ref)
    try:
        subprocess.run(["git", "worktree", "add", "-b", branch_name, str(worktree_path), source_ref], check=True)
    except subprocess.CalledProcessError:
        interactive = sys.stdin.isatty()
        if not interactive:
            error_exit("Error: Cannot prompt for input in non-interactive mode. Try --no-worktree or a simpler prompt.")
        custom = input("Enter a custom branch name (or press Ctrl+C to cancel): ").strip()
        if not custom:
            error_exit("Error: No branch name provided")
        validate_branch_name(custom)
        worktree_path = WORKTREE_BASE / custom
        subprocess.run(["git", "worktree", "add", "-b", custom, str(worktree_path), "HEAD"], check=True)
        return worktree_path
    return worktree_path


def determine_source_ref(cfg: Config) -> str:
    if cfg.from_branch:
        return cfg.from_branch
    cwd_str = str(Path.cwd())
    if "/worktree" in cwd_str:
        if cfg.from_master:
            return "master"
        result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
        if result.returncode == 0:
            current = result.stdout.strip() or "HEAD"
            print_success("In worktree on '%s' - branching from current branch", current)
            return "HEAD"
    return "HEAD"


def ensure_worktree_dir() -> None:
    if not WORKTREE_BASE.exists():
        WORKTREE_BASE.mkdir(parents=True)


def find_existing_worktree(branch_name: str) -> Optional[Path]:
    result = subprocess.run(["git", "worktree", "list", "--porcelain"], capture_output=True, text=True, check=True)
    lines = result.stdout.splitlines()
    current_worktree = None
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


def prepare_agent_worktree(agent_label: str, branch_name: str, source_ref: str) -> Path:
    validate_branch_name(branch_name)
    ensure_worktree_dir()
    worktree_path = WORKTREE_BASE / branch_name

    existing = find_existing_worktree(branch_name)
    if existing:
        print_warning("%s branch '%s' already has a worktree at: %s", agent_label, branch_name, existing)
        if existing.is_dir():
            print_success("Using existing %s worktree at: %s", agent_label, existing)
            return existing
        print_warning("Worktree directory missing for %s. Pruning and recreating...", agent_label)
        subprocess.run(["git", "worktree", "prune"], check=True)
        subprocess.run(["git", "worktree", "add", str(worktree_path), branch_name], check=True)
        return worktree_path

    if branch_exists(branch_name):
        print_success("Adding %s worktree for existing branch: %s", agent_label, branch_name)
        subprocess.run(["git", "worktree", "add", str(worktree_path), branch_name], check=True)
        return worktree_path

    print_success("Creating new %s branch/worktree: %s from %s", agent_label, branch_name, source_ref)
    subprocess.run(["git", "worktree", "add", "-b", branch_name, str(worktree_path), source_ref], check=True)
    return worktree_path


def generate_branch_name(prompt: str) -> str:
    api_key = fetch_openai_key()
    if not api_key:
        print_warning("Error: AI branch name generation failed")
        print_warning("OpenAI API key not found in 1Password (op://cli/openai/configs)")
        print_warning("Fix the issue or use --no-worktree to work in current directory")
        sys.exit(1)

    essence = openai_chat(api_key, "Extract the main topic and intent from this development request in 5-10 words. Focus on the key feature, component, or goal being worked on.", prompt, max_tokens=30)
    branch = openai_chat(
        api_key,
        textwrap.dedent(
            """\
            Generate a concise git branch name (2-4 words, hyphenated, lowercase). Focus on the main feature/component. Examples:
            - "implement multi-user chats" → group-chats
            - "event-driven architecture refactor" → event-architecture
            - "fix authentication bug" → fix-auth
            - "add dark mode toggle" → dark-mode
            - "database migration system" → db-migration
            - "api rate limiting" → rate-limiting
            Return only the branch name, no quotes or explanations.
            """
        ).strip(),
        essence,
        max_tokens=10,
    )

    sanitized = sanitize_branch_name(branch)
    if not sanitized:
        error_exit("Error: Generated invalid branch name")

    validate_branch_name(sanitized)
    return sanitized


def sanitize_branch_name(name: str) -> str:
    lowered = name.strip().lower()
    lowered = re.sub(r"^[^a-z0-9]+", "", lowered)
    lowered = re.sub(r"[^a-z0-9-]+", "-", lowered)
    lowered = re.sub(r"-+", "-", lowered)
    lowered = lowered.strip("-")
    return lowered


def fetch_openai_key() -> Optional[str]:
    try:
        result = subprocess.run(["op", "read", "op://cli/openai/configs"], capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    api_key = result.stdout.strip()
    return api_key or None


def openai_chat(api_key: str, system_prompt: str, user_content: str, *, max_tokens: int) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_exit("Error: OpenAI request failed with status %s", exc.code)
    except urllib.error.URLError as exc:
        error_exit("Error: OpenAI request failed (%s)", exc.reason)

    try:
        parsed = json.loads(body)
        content = parsed["choices"][0]["message"]["content"].strip()
        return content
    except (KeyError, IndexError, json.JSONDecodeError):
        error_exit("Error: Unexpected response from OpenAI")


def main(argv: Optional[List[str]] = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    ensure_tmux_available()

    cfg = parse_args(argv)

    if cfg.list_sessions:
        list_sessions()
        return

    session_name = get_session_name(cfg.session_name)

    if not cfg.prompt:
        handle_session_only(session_name)
        return

    if inside_tmux():
        if cfg.agent_mode == "dual":
            run_duo(cfg)
        else:
            run_single(cfg)
    else:
        run_with_tmux(session_name, cfg)


if __name__ == "__main__":
    main()
