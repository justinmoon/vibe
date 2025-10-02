from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .output import error_exit, success, warning

TMUX_SOCKET_ARGS: list[str] = []


def configure_tmux(socket: str | None) -> None:
    """Set the tmux socket arguments used for all future commands."""

    global TMUX_SOCKET_ARGS
    if socket:
        TMUX_SOCKET_ARGS = ["-L", socket]
    else:
        TMUX_SOCKET_ARGS = []


def ensure_tmux_available() -> None:
    if shutil.which("tmux") is None:
        error_exit("Error: tmux not found. Please install tmux to use vibe.")


def session_exists(name: str) -> bool:
    result = subprocess.run(["tmux", "has-session", "-t", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def run_tmux(args: Iterable[str], *, capture: bool = False) -> Optional[str]:
    cmd = ["tmux", *TMUX_SOCKET_ARGS, *args]
    if capture:
        return subprocess.check_output(cmd, text=True).strip()
    subprocess.run(cmd, check=True)
    return None


def list_vibe_sessions() -> None:
    result = subprocess.run(["tmux", "list-sessions"], capture_output=True, text=True)
    if result.returncode != 0:
        warning("  No active vibe sessions")
        return
    lines = [line for line in result.stdout.splitlines() if line.startswith("vibe-")]
    if not lines:
        success("Active vibe sessions:")
        warning("  No active vibe sessions")
        return
    success("Active vibe sessions:")
    for line in lines:
        session = line.split(":", 1)[0]
        window_list = subprocess.run(["tmux", "list-windows", "-t", session], capture_output=True, text=True)
        count = len(window_list.stdout.splitlines()) if window_list.returncode == 0 else 0
        print(f"  \033[1;33m{session}\033[0m ({count} windows)")


def attach_session(name: str, *, detach_others: bool = True) -> None:
    args = ["attach-session"]
    if detach_others:
        args.append("-d")
    args.extend(["-t", name])
    run_tmux(args)


def switch_client(name: str) -> None:
    run_tmux(["switch-client", "-t", name])


def new_session(name: str, cwd: Path, *, detached: bool = False) -> None:
    args = ["new-session"]
    if detached:
        args.append("-d")
    args.extend(["-s", name, "-c", str(cwd)])
    run_tmux(args)


def new_window(name: str, cwd: Path) -> str:
    try:
        window_id = run_tmux(
            ["new-window", "-n", name, "-c", str(cwd), "-P", "-F", "#{window_id}"],
            capture=True,
        )
    except subprocess.CalledProcessError:
        error_exit("Error: Could not create tmux window")
    assert window_id is not None
    success("Created tmux window: %s", window_id)
    return window_id


def split_window(window_id: str, *, direction: str = "-h", cwd: Path) -> str:
    try:
        pane_id = run_tmux(
            ["split-window", direction, "-t", window_id, "-c", str(cwd), "-P", "-F", "#{pane_id}"],
            capture=True,
        )
    except subprocess.CalledProcessError:
        error_exit("Error: Could not split tmux window for codex pane")
    assert pane_id is not None
    return pane_id


def set_window_dir(window_id: str, path: Path) -> None:
    result = subprocess.run(["tmux", "setw", "-t", window_id, "@window_dir", str(path)])
    if result.returncode != 0:
        warning("Warning: Could not set window directory variable")


def select_pane(target: str) -> None:
    run_tmux(["select-pane", "-t", target])


def set_pane_title(target: str, title: str) -> None:
    run_tmux(["select-pane", "-T", title, "-t", target])


def send_keys(target: str, *keys: str) -> None:
    run_tmux(["send-keys", "-t", target, *keys])


def current_pane(window_id: str) -> str:
    pane_id = run_tmux(["display-message", "-p", "-t", window_id, "#{pane_id}"], capture=True)
    assert pane_id is not None
    return pane_id


def list_windows() -> List[Tuple[str, str, str]]:
    if shutil.which("tmux") is None:
        return []
    try:
        output = run_tmux(["list-windows", "-a", "-F", "#{window_id} #{session_name} #{window_name}"], capture=True)
    except subprocess.CalledProcessError:
        return []
    if not output:
        return []
    windows: List[Tuple[str, str, str]] = []
    for line in output.splitlines():
        parts = line.split(" ", 2)
        if len(parts) == 3:
            windows.append((parts[0], parts[1], parts[2]))
    return windows


def kill_window(window_id: str, *, delay: bool = False) -> None:
    if shutil.which("tmux") is None:
        return
    if delay:
        def _delayed_kill(window: str) -> None:
            time.sleep(0.5)
            subprocess.run(["tmux", *TMUX_SOCKET_ARGS, "kill-window", "-t", window], stderr=subprocess.DEVNULL)

        import threading

        threading.Thread(target=_delayed_kill, args=(window_id,), daemon=True).start()
    else:
        try:
            run_tmux(["kill-window", "-t", window_id])
        except subprocess.CalledProcessError:
            pass
