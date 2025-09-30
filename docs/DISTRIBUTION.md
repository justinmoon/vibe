# Vibe Distribution Notes

This document outlines practical ways to ship the Python-based `vibe` CLI now that it uses a standard `pyproject.toml` and `uv` for dependency/build management. All options preserve the edit-in-place workflow: you can keep running from source via `uv run` while adopting one of these when you want to share the tool.

## 1. Run-from-source (no packaging step)
- Continue using the `~/configs/bin/vibe` shim, which calls `uv run --project ~/code/vibe vibe ...`.
- Any edits under `src/vibe/` take effect immediately.
- This is ideal for day-to-day hacking and keeps zero install steps on your machine.

## 2. Local tool install with `uv`
- Build once, then pin the CLI globally:
  ```bash
  uv tool install --from ~/code/vibe vibe
  ```
- `uv` compiles a wheel from the current tree and places a `vibe` entrypoint in `~/.local/bin` (or your configured tool directory).
- Re-run the command to pick up updates when you're ready.

## 3. Distribute wheels / sdists
- Produce artifacts with:
  ```bash
  uv build  # creates dist/vibe-<version>.whl and .tar.gz
  ```
- Share the wheel directly (internal tooling, Slack, etc.) or upload to a private/simple index (e.g., cloud storage, GitHub Releases).
- Consumers install via `uv pip install https://.../vibe-<version>.whl` or standard `pip`.

## 4. Git-based install
- Tag the repo and let others install from git:
  ```bash
  uv pip install git+ssh://github.com/your-org/vibe@v0.1.0
  ```
- `uv`/`pip` will build from source using the metadata in `pyproject.toml`.

## 5. System package/wrapper options
- For dotfile integration, keep a tiny shim (like the current `~/configs/bin/vibe`) that invokes either `uv run` or a `uv tool install`ed binary.
- For wider team distribution, consider a Homebrew formula that depends on `uv` and runs `uv tool install`, or prebuild wheels and upload to a private package index.

## Release Checklist
1. Bump the version in `pyproject.toml`.
2. `uv run python -m compileall src` (or run tests once added).
3. `uv build` and smoke-test via `uv run --project dist/vibe-<version>.whl vibe --help` (using `uv tool run` if desired).
4. Tag the commit and publish artifacts (wheel, sdist) wherever appropriate.

## Keeping Iteration Fast
- Because the shim calls `uv run --project`, you can edit source and re-run immediately with zero rebuilds.
- When you **do** want an installable artifact, `uv` reuses build caches so subsequent `uv build` or `uv tool install` runs are quick.
- Optional: add `uv lock --locked` to CI to ensure dependency reproducibility once dependencies are introduced.
