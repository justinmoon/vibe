from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

from .args import parse_args
from .config import Config
from .run import run_duo, run_single
from .tmux import (
    attach_session,
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
    if inside_tmux():
        if session_exists(session_name):
            switch_client(session_name)
        else:
            new_session(session_name, Path.cwd(), detached=True)
            switch_client(session_name)
        return

    if session_exists(session_name):
        attach_session(session_name)
    else:
        new_session(session_name, Path.cwd())


def run_with_tmux(session_name: str, cfg: Config) -> None:
    cwd = Path.cwd()
    if session_exists(session_name):
        fd, tmp_path = tempfile.mkstemp(prefix="vibe-run.", suffix=".sh")
        os.close(fd)
        temp_script = Path(tmp_path)
        try:
            temp_script.write_text(
                "#!/bin/bash\n"
                f"cd {shlex.quote(str(cwd))}\n"
                f"vibe {shlex.join(cfg.raw_args)}\n"
                f"rm -f {shlex.quote(str(temp_script))}\n"
            )
            temp_script.chmod(0o755)
            cmd = (
                f"tmux attach-session -d -t {shlex.quote(session_name)} "
                f"\\; send-keys {shlex.quote(str(temp_script))} C-m"
            )
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


def main(argv: List[str] | None = None) -> None:
    ensure_tmux_available()

    cfg = parse_args(list(sys.argv[1:] if argv is None else argv))

    if cfg.list_sessions:
        list_vibe_sessions()
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
