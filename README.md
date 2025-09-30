# Vibe (Python)

Python rewrite of the `vibe` tmux + agent launcher. Features mirror the prior bash tooling:

- tmux session management with automatic session creation and switching
- git worktree orchestration with OpenAI-powered branch naming
- dual-agent mode that runs Claude and Codex side-by-side
- multiple input modes (arguments, stdin, editor, file)
- project directory overrides and `--no-worktree` fast mode
- optional Codex command dispatch (`/pr`, `--command`, etc.)

Install by pointing the wrapper script in `~/configs/bin` at this module (done in this repo). Requires Python 3.10+, tmux, git, the Claude/Codex CLIs, and 1Password CLI for API key retrieval.

Run `python -m vibe` or simply `vibe` via the provided shim once configs are updated.
