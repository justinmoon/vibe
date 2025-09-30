from __future__ import annotations

import os
import shlex
import tempfile
from pathlib import Path

from .output import error_exit


def get_agent_flags(agent_cmd: str) -> str:
    if agent_cmd == "codex":
        return "--dangerously-bypass-approvals-and-sandbox"
    return "--dangerously-skip-permissions"


def build_agent_command(
    agent_cmd: str,
    agent_flags: str,
    context: str,
    prompt: str,
    codex_command_name: str | None,
) -> str:
    command_name = os.environ.get(f"VIBE_{agent_cmd.upper()}_BIN", agent_cmd)
    message = context if not prompt else f"{context}\n\n{prompt}"
    fd, temp_path = tempfile.mkstemp(prefix="vibe-msg.")
    os.close(fd)
    temp = Path(temp_path)
    temp.write_text(message)
    quoted_temp = shlex.quote(str(temp))
    command = f"{command_name} {agent_flags} \"$(cat {quoted_temp})\""
    if agent_cmd == "codex" and codex_command_name:
        command = f"{command} {shlex.quote(codex_command_name)}"
    return f"{command} && rm -f {quoted_temp}"


def build_claude_command(context: str, prompt: str) -> str:
    return build_agent_command("claude", get_agent_flags("claude"), context, prompt, None)


def build_codex_command(context: str, prompt: str, codex_command_name: str | None) -> str:
    return build_agent_command("codex", get_agent_flags("codex"), context, prompt, codex_command_name)
