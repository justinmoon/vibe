from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

DEFAULT_EDITOR = os.environ.get("EDITOR", "helix")
WORKTREE_BASE = Path("./worktrees")


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
    tmux_socket: Optional[str] = None
    review_base: Optional[str] = None
