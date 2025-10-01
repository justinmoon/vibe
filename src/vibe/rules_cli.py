from __future__ import annotations

import argparse
import os
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "target",
    "dist",
    "build",
    "tmp",
    "temp",
    "__pycache__",
    ".venv",
    "venv",
    "coverage",
    "bazel-bin",
    "bazel-out",
    "bazel-testlogs",
}

AUTO_START_MARK = "<!-- vibe:auto:start -->"
AUTO_END_MARK = "<!-- vibe:auto:end -->"
AUTO_NOTICE = "<!-- Managed by `vibe rules apply`; edits below will be overwritten. -->"

REGISTRY_FILENAMES = {
    "_base.md",
    "_claude.md",
    "_codex.md",
}


@dataclass
class OutputTarget:
    key: str
    label: str
    relative_path: Path
    defaults: List[str]


@dataclass
class ApplyConfig:
    registry_root: Path
    project_root: Path
    outputs: List[OutputTarget]


def handle_rules_command(argv: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="vibe rules",
        description="Rules registry utilities",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Create an empty rules registry skeleton",
    )
    bootstrap_parser.add_argument(
        "--registry",
        type=Path,
        default=_default_registry_root(),
        help="Registry directory to scaffold (default: ~/code/vibe-rules)",
    )
    bootstrap_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite example files if they already exist",
    )
    bootstrap_parser.set_defaults(func=_bootstrap_command)

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Harvest unique lines from AGENTS.md/CLAUDE.md files",
    )
    ingest_parser.add_argument(
        "--source-root",
        type=Path,
        default=Path.home() / "code",
        help="Root directory to scan (default: ~/code)",
    )
    ingest_parser.add_argument(
        "--registry",
        type=Path,
        help="Registry directory used to derive the default output path",
    )
    ingest_parser.add_argument(
        "--output",
        type=Path,
        help="File path for the concatenated lines (default: <registry>/INGEST.md)",
    )
    ingest_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )
    ingest_parser.set_defaults(func=_ingest_command)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Interactively select registry snippets for a project",
    )
    apply_parser.add_argument(
        "--config",
        type=Path,
        default=Path("vibe.rules.toml"),
        help="Project config file (default: ./vibe.rules.toml)",
    )
    apply_parser.set_defaults(func=_apply_command)

    args = parser.parse_args(list(argv))
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return
    handler(args)


def _default_registry_root() -> Path:
    return (Path.home() / "code" / "vibe-rules")


def _bootstrap_command(args: argparse.Namespace) -> None:
    registry_root = args.registry.expanduser().resolve()
    rules_dir = registry_root / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    templates: Dict[Path, str] = {
        Path("README.md"): textwrap.dedent(
            """\
            # Vibe Rules Registry

            This directory stores reusable guidance for Justin's projects.

            Action plan:
            1. Run `vibe rules ingest` to collect raw agent guidance into `INGEST.md`.
            2. Curate the content into the markdown files under `rules/`.
            3. Inside a project, run `vibe rules apply` to build AGENTS.md / CLAUDE.md.
            """
        ).strip()
        + "\n",
        Path("rules/_base.md"): textwrap.dedent(
            """\
            # Shared Base Guidelines

            <!-- Add reusable cross-project guidance here. -->
            """
        ).strip()
        + "\n",
        Path("rules/_claude.md"): textwrap.dedent(
            """\
            # Claude Agent Guidance

            <!-- Claude-specific notes live here. -->
            """
        ).strip()
        + "\n",
        Path("rules/_codex.md"): textwrap.dedent(
            """\
            # Codex Agent Guidance

            <!-- Codex-specific notes live here. -->
            """
        ).strip()
        + "\n",
    }

    created_files: List[str] = []
    overwritten_files: List[str] = []
    skipped_files: List[str] = []

    for rel_path, content in templates.items():
        destination = registry_root / rel_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not args.force:
            skipped_files.append(rel_path.as_posix())
            continue
        if destination.exists():
            overwritten_files.append(rel_path.as_posix())
        else:
            created_files.append(rel_path.as_posix())
        destination.write_text(content, encoding="utf-8")

    print(f"Registry scaffold ready at {registry_root}")
    if created_files:
        print("Created example files:")
        for entry in created_files:
            print(f"  - {entry}")
    if overwritten_files:
        print("Overwrote files (force enabled):")
        for entry in overwritten_files:
            print(f"  - {entry}")
    if skipped_files:
        print("Skipped existing files (use --force to overwrite):")
        for entry in skipped_files:
            print(f"  - {entry}")


def _ingest_command(args: argparse.Namespace) -> None:
    source_root = args.source_root.expanduser().resolve()
    if not source_root.exists():
        print(f"Source root {source_root} does not exist.")
        return

    registry_root = (
        args.registry.expanduser().resolve()
        if args.registry
        else _default_registry_root().expanduser().resolve()
    )
    default_output = registry_root / "INGEST.md"
    output_path = (args.output or default_output).expanduser().resolve()

    if output_path.exists() and not args.force:
        print(
            f"{output_path} already exists. Use --force to overwrite or choose a different path.",
        )
        return

    exclude_root = registry_root if registry_root.exists() else None
    entries, source_files = _collect_unique_lines(source_root, exclude_root=exclude_root)
    if not entries:
        print("No AGENTS.md or CLAUDE.md files were found under the source root.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write("# Ingested Agent Guidance\n\n")
        fh.write(
            f"Harvested {len(entries)} unique lines from {len(source_files)} files under {source_root}.\n\n",
        )
        fh.write("Process each line, copy what matters into `rules/`, and delete it when done.\n\n")
        fh.write("---\n\n")
        for text, sources in entries:
            fh.write(f"<!-- Sources: {', '.join(sorted(sources))} -->\n")
            fh.write(f"{text}\n\n")

    print(
        f"Wrote {len(entries)} unique lines from {len(source_files)} files to {output_path}",
    )


def _collect_unique_lines(
    source_root: Path,
    *,
    exclude_root: Optional[Path] = None,
) -> tuple[List[tuple[str, Set[str]]], Set[str]]:
    seen: Dict[str, int] = {}
    entries: List[Dict[str, object]] = []
    source_files: Set[str] = set()
    excluded = exclude_root.resolve() if exclude_root else None

    for file_path in _iter_rule_files(source_root):
        if excluded and _is_relative_to(file_path, excluded):
            continue
        rel_path = file_path.relative_to(source_root).as_posix()
        source_files.add(rel_path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            normalized = stripped
            record_index = seen.get(normalized)
            if record_index is None:
                entries.append({
                    "text": raw_line.rstrip(),
                    "sources": {rel_path},
                })
                seen[normalized] = len(entries) - 1
            else:
                entry = entries[record_index]
                sources = entry["sources"]
                if isinstance(sources, set):
                    sources.add(rel_path)

    ordered_entries: List[tuple[str, Set[str]]] = []
    for entry in entries:
        line_text = str(entry["text"])
        sources = entry["sources"]
        if isinstance(sources, set):
            ordered_entries.append((line_text, sources))
    return ordered_entries, source_files


def _iter_rule_files(root: Path) -> Sequence[Path]:
    matches: List[Path] = []
    if not root.exists():
        return matches
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES
            and not d.startswith(".")
            and not Path(dirpath, d).is_symlink()
        ]
        for name in filenames:
            lower = name.lower()
            if lower in {"agents.md", "claude.md"}:
                candidate = Path(dirpath) / name
                if candidate.is_symlink():
                    continue
                matches.append(candidate)
    matches.sort()
    return matches


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.resolve().relative_to(other.resolve())
        return True
    except ValueError:
        return False


def _apply_command(args: argparse.Namespace) -> None:
    if tomllib is None:
        print(
            "Python 3.11+ is required for `tomllib`. Install the `tomli` package "
            "or upgrade Python to use `vibe rules apply`.",
        )
        return

    config_path = args.config.expanduser()
    config = _load_apply_config(config_path)

    if not config.registry_root.exists():
        print(
            f"Registry directory {config.registry_root} does not exist. "
            "Run `vibe rules bootstrap` or update the config.",
        )
        return

    rule_paths = _gather_registry_files(config.registry_root)
    if not rule_paths:
        print(
            f"No markdown files found under {config.registry_root}. "
            "Populate the registry before running apply.",
        )
        return

    warnings = _warn_missing_defaults(config.outputs, rule_paths)
    for warning in warnings:
        print(warning)

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            "Interactive terminal required for the apply TUI. Run the command "
            "from a TTY-enabled shell.",
        )
        return

    initial_selection = {
        target.key: {path for path in target.defaults if path in rule_paths}
        for target in config.outputs
    }

    try:
        selections = _run_apply_ui(
            registry_root=config.registry_root,
            outputs=config.outputs,
            rule_paths=rule_paths,
            selection_map=initial_selection,
        )
    except _UserAbort:
        print("Aborted without writing any files.")
        return
    except RuntimeError as exc:
        print(str(exc))
        return

    _write_selected_rules(
        registry_root=config.registry_root,
        project_root=config.project_root,
        outputs=config.outputs,
        selections=selections,
        rule_paths=rule_paths,
    )


def _default_output_targets() -> List[OutputTarget]:
    return [
        OutputTarget(
            key="agents",
            label="AGENTS",
            relative_path=Path("AGENTS.md"),
            defaults=["rules/_base.md", "rules/_codex.md"],
        ),
        OutputTarget(
            key="claude",
            label="CLAUDE",
            relative_path=Path("CLAUDE.md"),
            defaults=["rules/_base.md", "rules/_claude.md"],
        ),
    ]


def _load_apply_config(config_path: Path) -> ApplyConfig:
    config_dir = config_path.parent.resolve() if config_path else Path.cwd()
    project_root = config_dir
    registry_root = _default_registry_root().expanduser().resolve()
    outputs = _default_output_targets()

    if config_path and config_path.exists():
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)

        project_cfg: Dict[str, object] = data.get("project", {}) if isinstance(data, dict) else {}

        root_value = project_cfg.get("root") if isinstance(project_cfg, dict) else None
        if isinstance(root_value, str):
            project_root = (config_dir / Path(root_value)).resolve()
        else:
            project_root = config_dir

        registry_value = project_cfg.get("registry") if isinstance(project_cfg, dict) else None
        if isinstance(registry_value, str):
            registry_root = (config_dir / Path(registry_value)).resolve()

        raw_outputs = None
        if isinstance(data, dict):
            raw_outputs = data.get("output") or data.get("outputs")

        if isinstance(raw_outputs, list):
            parsed: List[OutputTarget] = []
            for idx, entry in enumerate(raw_outputs):
                if not isinstance(entry, dict):
                    continue
                key = str(entry.get("key") or entry.get("name") or f"output{idx+1}")
                label = str(entry.get("label") or key.upper())
                path_str = str(entry.get("path") or entry.get("file") or f"{label}.md")
                defaults = [
                    str(item)
                    for item in entry.get("defaults", [])
                    if isinstance(item, (str, Path))
                ]
                if not defaults:
                    for default_target in _default_output_targets():
                        if default_target.key == key:
                            defaults = list(default_target.defaults)
                            break
                parsed.append(
                    OutputTarget(
                        key=key,
                        label=label,
                        relative_path=Path(path_str),
                        defaults=defaults,
                    )
                )
            if parsed:
                outputs = parsed

    return ApplyConfig(
        registry_root=registry_root,
        project_root=project_root,
        outputs=outputs,
    )


def _gather_registry_files(registry_root: Path) -> List[str]:
    rules_dir = registry_root / "rules"
    if not rules_dir.exists():
        return []
    paths: List[str] = []
    for path in rules_dir.glob("*.md"):
        if path.is_file():
            paths.append(path.relative_to(registry_root).as_posix())
    paths = sorted(paths)
    return paths


def _warn_missing_defaults(outputs: List[OutputTarget], available: List[str]) -> List[str]:
    available_set = set(available)
    warnings: List[str] = []
    for target in outputs:
        missing = [item for item in target.defaults if item not in available_set]
        if missing:
            warnings.append(
                f"Warning: {target.label} defaults not found in registry: {', '.join(missing)}",
            )
    return warnings


class _UserAbort(Exception):
    pass


def _run_apply_ui(
    *,
    registry_root: Path,
    outputs: List[OutputTarget],
    rule_paths: List[str],
    selection_map: Dict[str, Set[str]],
) -> Dict[str, Set[str]]:
    import curses

    rule_contents = {
        path: (registry_root / path).read_text(encoding="utf-8", errors="ignore")
        for path in rule_paths
    }

    tab_keys = {9}
    if hasattr(curses, "KEY_TAB"):
        tab_keys.add(getattr(curses, "KEY_TAB"))
    back_tab_keys = {353}
    if hasattr(curses, "KEY_BTAB"):
        back_tab_keys.add(getattr(curses, "KEY_BTAB"))

    current_rule = 0
    current_output = 0
    list_scroll = 0
    preview_scroll = 0

    for target in outputs:
        selection_map.setdefault(target.key, set())

    def clamp(value: int, minimum: int, maximum: int) -> int:
        return max(minimum, min(value, maximum))

    instructions = (
        "[↑/↓] move  [space] toggle  [tab] cycle output  [a] all  [n] none  "
        "[PgUp/PgDn] preview  [w] write  [q] cancel"
    )

    def draw(stdscr: "curses._CursesWindow") -> Dict[str, Set[str]]:  # type: ignore[name-defined]
        nonlocal current_rule, current_output, list_scroll, preview_scroll
        curses.curs_set(0)
        stdscr.keypad(True)

        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            if height < 8 or width < 40:
                stdscr.addstr(0, 0, "Resize terminal (min 8x40) to continue.")
                stdscr.refresh()
                ch = stdscr.getch()
                if ch in (ord("q"), 27):
                    raise _UserAbort
                continue

            left_width = min(48, max(28, width // 2))
            list_height = max(1, height - 4)

            current_output = clamp(current_output, 0, len(outputs) - 1)
            max_rule_index = max(0, len(rule_paths) - 1)
            current_rule = clamp(current_rule, 0, max_rule_index)

            active_output = outputs[current_output]
            selected = selection_map[active_output.key]

            if current_rule < list_scroll:
                list_scroll = current_rule
            elif current_rule >= list_scroll + list_height:
                list_scroll = current_rule - list_height + 1

            stdscr.addstr(
                0,
                0,
                "Outputs: "
                + "  ".join(
                    f"[{target.label}]" if idx == current_output else target.label
                    for idx, target in enumerate(outputs)
                ),
            )

            stdscr.hline(1, 0, ord("-"), width)

            visible_rules = rule_paths[list_scroll : list_scroll + list_height]
            for offset, path in enumerate(visible_rules):
                row = 2 + offset
                marker = "[x]" if path in selected else "[ ]"
                prefix = ">" if (list_scroll + offset) == current_rule else " "
                truncated = path[: left_width - 6]
                stdscr.addstr(row, 0, f"{prefix}{marker} {truncated}")

            stdscr.vline(2, left_width, ord("|"), list_height)

            if rule_paths:
                active_path = rule_paths[current_rule]
                content_lines = rule_contents.get(active_path, "").splitlines()
                max_preview_scroll = max(0, len(content_lines) - list_height)
                preview_scroll = clamp(preview_scroll, 0, max_preview_scroll)
                preview_slice = content_lines[
                    preview_scroll : preview_scroll + list_height
                ]
                for offset, line in enumerate(preview_slice):
                    row = 2 + offset
                    trimmed = line[: max(0, width - left_width - 2)]
                    stdscr.addstr(row, left_width + 2, trimmed)
            else:
                stdscr.addstr(2, left_width + 2, "(No rules found)")

            stdscr.hline(height - 2, 0, ord("-"), width)
            stdscr.addstr(height - 1, 0, instructions[: width - 1])
            stdscr.refresh()

            ch = stdscr.getch()
            if ch in (ord("q"), 27):
                raise _UserAbort
            if ch in (curses.KEY_UP, ord("k")):
                if current_rule > 0:
                    current_rule -= 1
                    preview_scroll = 0
                continue
            if ch in (curses.KEY_DOWN, ord("j")):
                if current_rule < len(rule_paths) - 1:
                    current_rule += 1
                    preview_scroll = 0
                continue
            if ch == curses.KEY_PPAGE:
                preview_scroll = max(0, preview_scroll - max(1, list_height // 2))
                continue
            if ch == curses.KEY_NPAGE:
                preview_scroll = min(
                    preview_scroll + max(1, list_height // 2),
                    max(0, len(rule_contents.get(rule_paths[current_rule], "").splitlines()) - list_height),
                )
                continue
            if ch in tab_keys:
                current_output = (current_output + 1) % len(outputs)
                preview_scroll = 0
                continue
            if ch in back_tab_keys:
                current_output = (current_output - 1) % len(outputs)
                preview_scroll = 0
                continue
            if ch in (ord(" "), ord("x"), ord("X"), curses.KEY_ENTER, 10, 13):
                if rule_paths:
                    active_path = rule_paths[current_rule]
                    if active_path in selected:
                        selected.remove(active_path)
                    else:
                        selected.add(active_path)
                continue
            if ch in (ord("a"), ord("A")):
                selected.update(rule_paths)
                continue
            if ch in (ord("n"), ord("N")):
                selected.clear()
                continue
            if ch in (ord("w"), ord("s")):
                return {key: set(paths) for key, paths in selection_map.items()}

    return curses.wrapper(draw)


def _write_selected_rules(
    *,
    registry_root: Path,
    project_root: Path,
    outputs: List[OutputTarget],
    selections: Dict[str, Set[str]],
    rule_paths: List[str],
) -> None:
    ordered_lookup = {path: idx for idx, path in enumerate(rule_paths)}
    for target in outputs:
        selected_paths = selections.get(target.key, set())
        ordered = sorted(selected_paths, key=lambda path: ordered_lookup.get(path, 0))
        sections: List[str] = []
        for path in ordered:
            file_path = registry_root / path
            if not file_path.exists():
                continue
            sections.append(file_path.read_text(encoding="utf-8", errors="ignore").strip())
        generated = _render_generated_rules(sections)

        destination = (project_root / target.relative_path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)

        manual_prefix = _read_manual_prefix(destination, target.label)
        manual_block = manual_prefix.rstrip("\n")

        parts: List[str] = []
        if manual_block:
            parts.append(manual_block)
            parts.append("")
        parts.extend([AUTO_START_MARK, AUTO_NOTICE])
        if generated:
            parts.extend(["", generated])
        else:
            parts.extend(["", "<!-- No rules selected yet. -->"])
        parts.extend(["", AUTO_END_MARK, ""])
        output_text = "\n".join(parts)
        destination.write_text(output_text, encoding="utf-8")


def _read_manual_prefix(file_path: Path, label: str) -> str:
    if not file_path.exists():
        template = [
            f"# {label} Notes",
            "",
            "<!-- Everything above this marker is maintained manually. -->",
        ]
        return "\n".join(template)

    text = file_path.read_text(encoding="utf-8", errors="ignore")
    if AUTO_START_MARK in text:
        prefix = text.split(AUTO_START_MARK)[0]
        return prefix.rstrip("\n")
    return text.rstrip("\n")


def _render_generated_rules(sections: List[str]) -> str:
    cleaned = [section.strip() for section in sections if section.strip()]
    if not cleaned:
        return ""
    return "\n\n".join(cleaned)
