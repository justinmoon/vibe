from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

from .config import Config
from .output import error_exit


def gather_prompt(cfg: Config, remaining: Iterable[str]) -> str:
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


def build_editor_command(editor: str, path: Path) -> list[str]:
    if editor in {"vim", "nvim"}:
        return [editor, str(path), "+4"]
    if editor in {"helix", "hx"}:
        return [editor, f"{path}:4:1"]
    if editor == "nano":
        return [editor, str(path), "+4"]
    if editor == "emacs":
        return [editor, str(path), "+4"]
    return [editor, str(path)]
