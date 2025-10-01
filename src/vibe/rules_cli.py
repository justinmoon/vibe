from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None

from .agents import build_claude_command, build_codex_command

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
    "worktrees",
}

DEFAULT_HEADERS: Dict[str, str] = {
    "rules/base.md": "# Base Guidelines",
    "rules/agents/claude.md": "# Claude Agent Guidelines",
    "rules/agents/codex.md": "# Codex Agent Guidelines",
    "rules/languages/python.md": "# Python Guidance",
    "rules/languages/rust.md": "# Rust Guidance",
    "rules/workflows/duo.md": "# Duo Workflow Notes",
    "rules/workflows/dio-review.md": "# Duo Review Workflow Notes",
}

AUTO_START_MARK = "<!-- vibe:auto:start -->"
AUTO_END_MARK = "<!-- vibe:auto:end -->"
AUTO_NOTICE = "<!-- Managed by `vibe rules apply`; edits below will be overwritten. -->"

GENERAL_SECTION_KEYWORDS = (
    "general",
    "principle",
    "overview",
    "philosophy",
    "important",
    "expectation",
    "guideline",
    "intro",
    "introduction",
    "baseline",
)

LANGUAGE_KEYWORDS = {
    "python": "rules/languages/python.md",
    "rust": "rules/languages/rust.md",
}

WORKFLOW_KEYWORDS = {
    "duo": "rules/workflows/duo.md",
    "dual": "rules/workflows/duo.md",
    "dio": "rules/workflows/dio-review.md",
    "review": "rules/workflows/dio-review.md",
}


@dataclass
class SourceContext:
    repo_path: Path
    repo_label: str
    rel_path: Path
    commit: str


@dataclass
class MarkdownSection:
    title: str
    level: int
    body: str


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


def _default_output_targets() -> List[OutputTarget]:
    return [
        OutputTarget(
            key="agents",
            label="AGENTS",
            relative_path=Path("AGENTS.md"),
            defaults=[
                "rules/base.md",
                "rules/agents/codex.md",
            ],
        ),
        OutputTarget(
            key="claude",
            label="CLAUDE",
            relative_path=Path("CLAUDE.md"),
            defaults=[
                "rules/base.md",
                "rules/agents/claude.md",
            ],
        ),
    ]


def _load_apply_config(config_path: Path) -> ApplyConfig:
    config_dir = config_path.parent.resolve() if config_path else Path.cwd()
    project_root = config_dir
    registry_root = (Path.home() / "code" / "vibe-rules").resolve()
    outputs = _default_output_targets()

    if config_path and config_path.exists():
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)

        project_cfg: Dict[str, object] = data.get("project", {}) if isinstance(data, dict) else {}

        if "root" in project_cfg:
            project_root = (config_dir / Path(project_cfg["root"])).resolve()
        else:
            project_root = config_dir

        if "registry" in project_cfg:
            registry_root = (config_dir / Path(project_cfg["registry"])).resolve()
        else:
            registry_root = (Path.home() / "code" / "vibe-rules").resolve()

        raw_outputs = None
        if isinstance(data, dict):
            raw_outputs = data.get("output") or data.get("outputs")
        if raw_outputs:
            parsed: List[OutputTarget] = []
            for idx, entry in enumerate(raw_outputs):
                key = entry.get("key") or entry.get("name") or f"output{idx+1}"
                label = entry.get("label") or key.upper()
                path_str = entry.get("path") or entry.get("file") or f"{label}.md"
                defaults = [str(item) for item in entry.get("defaults", [])]
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
    if not registry_root.exists():
        return []
    paths: List[str] = []
    for path in registry_root.rglob("*.md"):
        if path.is_file():
            relative = path.relative_to(registry_root).as_posix()
            paths.append(relative)
    return sorted(paths)


def _warn_missing_defaults(outputs: List[OutputTarget], available: List[str]) -> List[str]:
    available_set = set(available)
    warnings: List[str] = []
    for target in outputs:
        missing = [default for default in target.defaults if default not in available_set]
        if missing:
            joined = ", ".join(missing)
            warnings.append(
                f"Warning: {target.label} defaults not found in registry: {joined}",
            )
    return warnings


class RegistryBuilder:
    def __init__(self, headers: Optional[Dict[str, str]] = None) -> None:
        self.headers: Dict[str, str] = dict(headers or {})
        self.sections: Dict[str, List[str]] = defaultdict(list)
        self._seen: Dict[str, set[str]] = defaultdict(set)

    def set_header_if_missing(self, path: str, header: str) -> None:
        if path not in self.headers or not self.headers[path]:
            self.headers[path] = header

    def ensure_path(self, path: str) -> None:
        _ = self.sections.setdefault(path, [])

    def add(self, path: str, snippet: str) -> None:
        content = snippet.strip()
        if not content:
            return
        if content in self._seen[path]:
            return
        self._seen[path].add(content)
        self.sections[path].append(content)

    def write(self, root: Path) -> List[Tuple[str, int]]:
        written: List[Tuple[str, int]] = []
        all_paths = sorted(set(self.headers) | set(self.sections))
        for relative_path in all_paths:
            sections = self.sections.get(relative_path, [])
            header = self.headers.get(relative_path)
            components: List[str] = []
            if header:
                components.append(header.strip())
            if sections:
                if header:
                    components.append("")
                components.append("\n\n".join(sections))
            else:
                if header:
                    components.append("")
                    components.append("<!-- TODO: curate content -->")
            output = "\n".join(components).rstrip() + "\n"
            destination = root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(output, encoding="utf-8")
            written.append((relative_path, len(sections)))
        return written


def handle_rules_command(argv: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="vibe rules",
        description="Rules registry utilities",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Collect AGENTS/CLAUDE docs into the local registry",
    )
    bootstrap_parser.add_argument(
        "--registry",
        type=Path,
        default=Path.cwd() / "vibe-rules",
        help="Destination rules registry directory",
    )
    bootstrap_parser.add_argument(
        "--source-root",
        type=Path,
        default=Path.home() / "code",
        help="Root directory to scan for git repositories",
    )
    bootstrap_parser.add_argument(
        "--author",
        default="Justin Moon",
        help="Author name to treat as a major contributor",
    )
    bootstrap_parser.add_argument(
        "--min-commits",
        type=int,
        default=5,
        help="Minimum commits required to treat repository as relevant",
    )
    bootstrap_parser.add_argument(
        "--min-share",
        type=float,
        default=0.2,
        help="Minimum share of total commits for the author",
    )
    bootstrap_parser.add_argument(
        "--include-worktrees",
        action="store_true",
        help="Include git worktree directories when gathering docs",
    )
    bootstrap_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and summarize without writing registry files",
    )
    bootstrap_parser.set_defaults(func=_bootstrap_command)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Scaffold project-level rules application",
    )
    apply_parser.add_argument(
        "--config",
        type=Path,
        default=Path("vibe.rules.toml"),
        help="Project configuration file for future rule application",
    )
    apply_parser.set_defaults(func=_apply_command)

    curate_parser = subparsers.add_parser(
        "curate",
        help="Launch configured agents to curate the rules registry",
    )
    curate_parser.add_argument(
        "--registry",
        type=Path,
        default=Path.cwd() / "vibe-rules",
        help="Registry directory to curate",
    )
    curate_parser.add_argument(
        "--source-root",
        type=Path,
        default=Path.home() / "code",
        help="Root directory containing candidate repositories",
    )
    curate_parser.add_argument(
        "--agent",
        dest="agents",
        action="append",
        help=(
            "Agent command to invoke. Can be specified multiple times. "
            "Defaults to trying agentds, claude, and codex in that order."
        ),
    )
    curate_parser.add_argument(
        "--codex-command",
        dest="codex_command",
        help="Codex command name to use when invoking codex (default: vibe-rules-curate)",
    )
    curate_parser.add_argument(
        "--context-note",
        help="Additional note appended to the agent context instructions",
    )
    curate_parser.set_defaults(func=_curate_command)

    args = parser.parse_args(list(argv))
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return
    handler(args)


def _bootstrap_command(args: argparse.Namespace) -> None:
    registry_root = args.registry.expanduser().resolve()
    source_root = args.source_root.expanduser().resolve()

    builder = RegistryBuilder(DEFAULT_HEADERS)
    for default_path in DEFAULT_HEADERS:
        builder.ensure_path(default_path)

    repos = list(_discover_git_repos(source_root))

    relevant_repos: List[Tuple[Path, List[Path]]] = []
    for repo in repos:
        if not _is_major_contributor(
            repo,
            args.author,
            min_commits=args.min_commits,
            min_share=args.min_share,
        ):
            continue
        agent_files = _find_agent_files(
            repo,
            include_worktrees=args.include_worktrees,
        )
        if agent_files:
            relevant_repos.append((repo, agent_files))

    if not relevant_repos:
        print("No repositories with qualifying contributions were found.")
        return

    stats: List[str] = []
    for repo, files in relevant_repos:
        repo_label = _format_repo_label(repo, source_root)
        stats.append(f"- {repo_label}: {len(files)} rule files")
        for file_path in files:
            metadata = _build_source_context(repo, source_root, file_path)
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            doc_kind = "claude" if file_path.name.lower() == "claude.md" else "agents"
            _ingest_full_document(builder, doc_kind, text, metadata)
            preamble, sections = _parse_markdown_sections(text)
            if preamble:
                snippet = _format_body_snippet(
                    heading=f"{metadata.repo_label}: overview",
                    body=preamble,
                    metadata=metadata,
                )
                builder.add("rules/base.md", snippet)
            for section in sections:
                lower_title = section.title.lower()
                if any(keyword in lower_title for keyword in GENERAL_SECTION_KEYWORDS):
                    builder.add(
                        "rules/base.md",
                        _format_section_snippet(section, metadata),
                    )
                    continue
                targets = _categorize_section(section)
                heading_label = f"{metadata.repo_label}: {section.title}"
                for target in targets:
                    snippet = _format_section_snippet(
                        section,
                        metadata,
                        heading_override=heading_label,
                    )
                    if not snippet:
                        continue
                    if target.startswith("rules/topics/"):
                        builder.set_header_if_missing(
                            target,
                            f"# {section.title.strip()}",
                        )
                    builder.add(target, snippet)

    if args.dry_run:
        print("Repositories that would be processed:")
        print("\n".join(stats))
        return

    written = builder.write(registry_root)
    print(f"Wrote registry to {registry_root}")
    for path, count in written:
        print(f"  {path}: {count} entries")


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
            "Run `vibe rules bootstrap` first or update the config.",
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
    if warnings:
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


def _curate_command(args: argparse.Namespace) -> None:
    registry_root = args.registry.expanduser().resolve()
    source_root = args.source_root.expanduser().resolve()
    additional_note = (args.context_note or "").strip()

    if not registry_root.exists():
        print(
            "Registry directory does not exist yet. Run `vibe rules bootstrap` "
            "before curating.",
        )
        return

    instructions = _build_curation_instructions(
        registry_root=registry_root,
        source_root=source_root,
        extra_note=additional_note,
    )

    agent_names = args.agents if args.agents else ["agentds", "claude", "codex"]
    any_invoked = False
    for agent in agent_names:
        normalized = _normalize_agent_name(agent)
        if normalized == "claude":
            command = build_claude_command(instructions, "")
            if _invoke_agent_command(command, "claude"):
                any_invoked = True
        elif normalized == "codex":
            command_name = args.codex_command or "vibe-rules-curate"
            command = build_codex_command(instructions, "", command_name)
            if _invoke_agent_command(command, "codex"):
                any_invoked = True
        else:
            if _invoke_generic_agent(normalized, instructions):
                any_invoked = True
    if not any_invoked:
        tried = ", ".join(agent_names)
        print(
            "No agents were invoked. Ensure at least one of "
            f"{tried} is installed or specify a custom agent via --agent.",
        )


def _discover_git_repos(root: Path) -> Iterable[Path]:
    root = root.resolve()
    for dirpath, dirnames, _ in os.walk(root):
        current = Path(dirpath)
        if ".git" in dirnames:
            yield current
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]


def _is_major_contributor(
    repo_path: Path,
    author: str,
    min_commits: int,
    min_share: float,
) -> bool:
    shortlog = _git_shortlog(repo_path)
    if not shortlog:
        return False

    author_lower = author.lower()
    total_commits = sum(count for count, _ in shortlog)
    author_entry: Optional[Tuple[int, int, str]] = None
    for index, (count, name) in enumerate(shortlog):
        name_lower = name.lower()
        if author_lower in name_lower:
            author_entry = (index, count, name)
            break
        author_tokens = [token for token in author_lower.split() if token]
        if author_tokens and all(token in name_lower for token in author_tokens):
            author_entry = (index, count, name)
            break
    if author_entry is None:
        return False

    index, count, _ = author_entry
    if count < min_commits:
        return False

    if index <= 1:
        return True

    share = count / total_commits if total_commits else 0.0
    return share >= min_share


def _git_shortlog(repo_path: Path) -> List[Tuple[int, str]]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "shortlog", "-sn", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    entries: List[Tuple[int, str]] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"(\d+)\s+(.+)", stripped)
        if not match:
            continue
        count = int(match.group(1))
        name = match.group(2).strip()
        entries.append((count, name))
    return entries


def _find_agent_files(
    repo_path: Path,
    include_worktrees: bool = False,
) -> List[Path]:
    results: List[Path] = []
    for pattern in ("AGENTS.md", "CLAUDE.md"):
        for path in repo_path.rglob(pattern):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(repo_path).parts
            if not include_worktrees and "worktrees" in rel_parts:
                continue
            if any(part in SKIP_DIR_NAMES for part in rel_parts):
                continue
            results.append(path)
    return results


def _format_repo_label(repo: Path, source_root: Path) -> str:
    try:
        return str(repo.relative_to(source_root))
    except ValueError:
        return repo.name


def _build_source_context(
    repo_path: Path,
    source_root: Path,
    file_path: Path,
) -> SourceContext:
    rel_path = file_path.relative_to(repo_path)
    repo_label = _format_repo_label(repo_path, source_root)
    commit = _latest_commit_for_path(repo_path, rel_path)
    return SourceContext(
        repo_path=repo_path,
        repo_label=repo_label,
        rel_path=rel_path,
        commit=commit,
    )


def _latest_commit_for_path(repo_path: Path, rel_path: Path) -> str:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "log",
                "-n",
                "1",
                "--format=%H",
                "--",
                str(rel_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return "unknown"

    commit = result.stdout.strip()
    return commit[:12] if commit else "unknown"


def _ingest_full_document(
    builder: RegistryBuilder,
    doc_kind: str,
    content: str,
    metadata: SourceContext,
) -> None:
    trimmed = content.strip()
    if not trimmed:
        return
    destination = (
        "rules/agents/claude.md"
        if doc_kind == "claude"
        else "rules/agents/codex.md"
    )
    snippet = _format_body_snippet(
        heading=f"{metadata.repo_label}: {metadata.rel_path}",
        body=trimmed,
        metadata=metadata,
    )
    builder.add(destination, snippet)


def _parse_markdown_sections(text: str) -> Tuple[str, List[MarkdownSection]]:
    preamble_lines: List[str] = []
    sections: List[MarkdownSection] = []
    current_title: Optional[str] = None
    current_level: int = 0
    current_lines: List[str] = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            if current_title is not None:
                sections.append(
                    MarkdownSection(
                        title=current_title.strip(),
                        level=current_level,
                        body="\n".join(current_lines).strip(),
                    )
                )
            current_title = match.group(2).strip()
            current_level = len(match.group(1))
            current_lines = []
        else:
            if current_title is None:
                preamble_lines.append(line)
            else:
                current_lines.append(line)

    if current_title is not None:
        sections.append(
            MarkdownSection(
                title=current_title.strip(),
                level=current_level,
                body="\n".join(current_lines).strip(),
            )
        )

    preamble = "\n".join(preamble_lines).strip()
    filtered_sections = [section for section in sections if section.title]
    return preamble, filtered_sections


def _categorize_section(section: MarkdownSection) -> List[str]:
    targets: List[str] = []
    lower_title = section.title.lower()
    for keyword, path in LANGUAGE_KEYWORDS.items():
        if keyword in lower_title:
            targets.append(path)
    for keyword, path in WORKFLOW_KEYWORDS.items():
        if keyword in lower_title:
            if path not in targets:
                targets.append(path)
    if not targets:
        slug = _slugify(section.title)
        targets.append(f"rules/topics/{slug}.md")
    return targets


def _format_section_snippet(
    section: MarkdownSection,
    metadata: SourceContext,
    heading_override: Optional[str] = None,
) -> str:
    comment = _format_source_comment(metadata)
    heading_text = heading_override or section.title.strip()
    level = max(2, min(section.level, 6))
    heading = "#" * level + " " + heading_text
    body = section.body.strip()
    if not body:
        return ""
    return f"{comment}\n{heading}\n\n{body}"


def _format_body_snippet(
    heading: str,
    body: str,
    metadata: SourceContext,
) -> str:
    comment = _format_source_comment(metadata)
    heading_line = f"## {heading}"
    body_text = body.strip()
    if body_text:
        return f"{comment}\n{heading_line}\n\n{body_text}"
    return f"{comment}\n{heading_line}"


def _format_source_comment(metadata: SourceContext) -> str:
    return (
        f"<!-- Source: {metadata.repo_label}@{metadata.commit} {metadata.rel_path} -->"
    )


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        slug = "topic"
    if len(slug) > 48:
        slug = slug[:48].rstrip("-")
    return slug or "topic"


def _build_curation_instructions(
    registry_root: Path,
    source_root: Path,
    extra_note: str,
) -> str:
    note = f"\n\nAdditional context: {extra_note}" if extra_note else ""
    return (
        "You are curating reusable agent guidance for Justin Moon."
        "\n\n"
        f"Registry directory: {registry_root}\n"
        f"Candidate repo root: {source_root}\n"
        "Goal: refine the seeded registry (base, agent, topic files) into a "
        "streamlined, non-duplicative set of rules appropriate for reuse across "
        "Justin's active projects. Work directly in the registry files."
        "\n\nImportant constraints:\n"
        "- Only use guidance from repositories where Justin Moon is a primary "
        "contributor (top committers).\n"
        "- Do not edit the original AGENTS.md or CLAUDE.md files in those repositories.\n"
        "- Preserve source attribution comments (`<!-- Source: repo@commit path -->`).\n"
        "- Merge duplicate content and tighten wording while keeping actionable details.\n"
        "- Leave TODO comments for areas that still need manual follow-up.\n"
        "\nHelpful commands:\n"
        f"  rg --files -g 'AGENTS.md' {source_root}\n"
        f"  rg --files -g 'CLAUDE.md' {source_root}\n"
        "  git -C <repo> shortlog -sn HEAD\n"
        "  git -C <repo> log -n 1 --format='%H' -- <path>\n"
        "  vibe rules bootstrap --dry-run\n"
        "  vibe rules bootstrap (to regenerate from scratch if needed)\n"
        f"  ls -R {registry_root}\n"
        "\nDeliverables:\n"
        "- Curated markdown in the registry directory with redundant material "
        "consolidated.\n"
        "- Topic files grouped logically (rename or split as needed).\n"
        "- Optional notes about further work captured as HTML comments."
        f"{note}\n"
    )


def _normalize_agent_name(agent: str) -> str:
    mapping = {
        "cc": "claude",
        "claude-code": "claude",
        "claude_code": "claude",
        "codex": "codex",
        "agentds": "agentds",
    }
    normalized = agent.strip().lower()
    return mapping.get(normalized, normalized)


def _invoke_agent_command(command: str, label: str) -> bool:
    try:
        subprocess.run(command, shell=True, check=True)
        return True
    except FileNotFoundError:
        print(f"Failed to launch {label}: command not found.")
    except subprocess.CalledProcessError as exc:
        print(f"{label} exited with status {exc.returncode}.")
    return False


def _invoke_generic_agent(agent_name: str, instructions: str) -> bool:
    binary = os.environ.get(f"VIBE_{agent_name.upper()}_BIN") or which(agent_name)
    if not binary:
        print(f"Skipping {agent_name}: not found in PATH.")
        return False

    fd, tmp_path = tempfile.mkstemp(prefix="vibe-curate.", suffix=".txt")
    os.close(fd)
    temp = Path(tmp_path)
    temp.write_text(instructions, encoding="utf-8")
    try:
        command = f"{binary} \"$(cat {shlex.quote(str(temp))})\""
        subprocess.run(command, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"{agent_name} exited with status {exc.returncode}.")
        return False
    finally:
        temp.unlink(missing_ok=True)


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
            if ch in (curses.KEY_TAB, 9):
                current_output = (current_output + 1) % len(outputs)
                preview_scroll = 0
                continue
            if ch == curses.KEY_BTAB:
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
