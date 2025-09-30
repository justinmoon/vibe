# Vibe (Python)

Python implementation of the `vibe` tmux + AI agent launcher. The project now uses a `src/` layout and `uv` for packaging so you can both iterate from source and ship an installable CLI.

## Features

- tmux session management with automatic session switching
- git worktree orchestration and OpenAI-powered branch naming
- dual-agent mode (Claude + Codex) with split panes
- multiple input modes (args, stdin, editor, file) and project overrides
- codex command passthrough (`/pr`, `--command`, etc.)

## Quick Start

```bash
# Run straight from source (no install)
uv run --project ~/code/vibe vibe "describe the change"

# Or, inside the project directory
uv run vibe --list
```

The `~/configs/bin/vibe` shim is configured to run `uv` with this project, so editing source files under `src/vibe/` takes effect immediately.

## Packaging & Distribution

- The project is defined in `pyproject.toml` with `hatchling` as the build backend.
- Use `uv build` to produce wheels/sdists in `dist/`.
- Install locally with `uv tool install --from .` or `uv pip install dist/vibe-*.whl`.
- Entry point `vibe = "vibe.cli:main"` exposes the same CLI as the bash/Go versions.

## Development Tips

```bash
# format / lint helpers (configure as desired)
uv run python -m compileall src  # quick syntax check

# run a dry command without worktree
uv run vibe --no-worktree "investigate logs"
```

The code is split into focused modules:

- `args.py` – CLI parsing and prompt capture
- `tmux.py` – tmux helpers
- `gitops.py` / `worktree.py` – git integration
- `openai_client.py` – branch naming
- `run.py` – orchestration logic
- `agents.py` – command construction for Claude/Codex


## Testing

Run the integration suite (real tmux + worktrees) with:

```bash
uv run --project . --extra test pytest
```
