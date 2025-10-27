# Vibe Rules System: Comprehensive Design Proposal

**Date**: 2025-10-26  
**Purpose**: Design document for implementing a local development overlay system that enforces CI checks before merging to master and provides standardized tooling/rules across all projects.

---

## Problem Statement

### The Core Issues

1. **CI Enforcement Gap**: When vibecoding with AI agents, I bypass GitHub CI and merge directly to master. This means CI checks don't run, potentially breaking the main branch.

2. **Manual Agent Rule Management**: Every project has its own `AGENT.md` / `CLAUDE.md` with rules. When I want to add a global rule (e.g., "always run CI before merge"), I have to manually edit dozens of files.

3. **Closed-Source Script Dependencies**: My personal scripts live in `~/configs/bin` (closed-source). Public repos shouldn't depend on these, but I also don't want script duplication across projects.

4. **Double CI Runs**: If CI runs on the feature branch, then we enforce CI before merge, we run CI twice unnecessarily at the end.

### What I Want

- Local enforcement: CI must pass before merging to master
- Zero manual maintenance: One command to update rules across all projects
- No repo pollution: Public repos stay pristine (no committed tooling files)
- Flexible system: Per-repo customization while sharing global defaults
- Works everywhere: Even on repos I don't own

---

## Current State Analysis

### Existing Infrastructure

**1. ~/code/vibe** (Python CLI Tool)
- **Location**: `/Users/justin/code/vibe`
- **Purpose**: Tmux + AI agent orchestration
- **Features**:
  - Tmux session management with auto-switching
  - Git worktree orchestration
  - Dual-agent mode (Claude + Codex)
  - OpenAI-powered branch naming
  - Multiple input modes
- **Entry Point**: `~/configs/bin/vibe` (bash shim that runs `uv run --project ~/code/vibe vibe`)
- **Status**: Actively used, mature codebase

**2. ~/code/vibe/vibe-rules** (Existing Rule System)
- **Location**: `/Users/justin/code/vibe/vibe-rules/rules/`
- **Purpose**: Centralized agent rules (attempted but incomplete)
- **Structure**:
  ```
  vibe-rules/
  ├── rules/
  │   ├── base.md           # Aggregated rules from multiple projects
  │   ├── topics/           # 26 topic-specific rule files
  │   │   ├── agents-guide.md
  │   │   ├── testing.md
  │   │   ├── deployment-strategy.md
  │   │   └── ...
  │   ├── languages/        # Language-specific rules
  │   │   ├── rust.md
  │   │   └── python.md
  │   ├── agents/           # Agent-specific rules
  │   │   ├── claude.md
  │   │   ├── droid.md
  │   │   └── codex.md
  │   └── workflows/        # Workflow rules
  │       ├── duo.md
  │       └── dio-review.md
  ```
- **Current Content**: Rules scraped from CLAUDE.md/AGENTS.md across projects (slipbox, nrc-bare, nostrdb-zig, etc.)
- **Status**: Started but never fully utilized - "kinda tricky to get started so i never did"

**3. ~/configs** (Personal Nix Configuration)
- **Location**: `/Users/justin/configs`
- **Type**: Closed-source personal configuration repo
- **Key Contents**:
  - `~/configs/bin/` - Personal scripts (including the vibe shim)
  - Nix home-manager configuration
  - System configuration files
- **On PATH**: Yes, via Nix configuration

**4. ~/code/** (Project Directory)
- Dozens of personal projects where this system would apply
- Mix of public and private repos
- Various languages (Rust, Python, TypeScript, etc.)

### Typical Project Structure

Most projects already use `justfile` for task automation:
- `just ci` - Runs full CI suite (lint, format, test, build)
- `just test` - Runs tests
- `just fmt` - Formats code
- Custom recipes per project

---

## Design Exploration & Key Decisions

### Decision 1: Merge with Existing vibe vs. Separate Tool

**Options Considered**:
1. Create separate tool (e.g., `vibe-enforce` or new `vibe-rules` CLI)
2. Merge into existing `~/code/vibe` as subcommand

**Decision**: **Merge into existing vibe**

**Rationale**:
- vibe is already the orchestration layer for coding sessions
- vibe-rules directory already exists in the project
- Natural fit: `vibe rules install`, `vibe rules update`, etc.
- Single tool for all vibecoding needs
- Already on PATH via `~/configs/bin/vibe` shim

### Decision 2: Local Overlay vs. Committed Files

**Options Considered**:
1. Sync files into repos (justfile snippets, AGENT.md, etc.)
2. Local-only overlay system (never committed)

**Decision**: **Local overlay system (.vibe/ directory)**

**Rationale**:
- Zero repo pollution - public repos stay pristine
- Works on any project, even ones I don't own
- No merge conflicts with project maintainers
- Global gitignore makes it invisible
- Can be open-sourced later for others to use
- Zero maintenance per-repo (just update from templates)

### Decision 3: CI Caching Strategy

**Problem**: Last commit runs CI, then `just merge` runs CI again = waste

**Solution**: Git-hash-based caching
```bash
TREE_HASH=$(git rev-parse HEAD)
CACHE_FILE=".vibe/.ci-cache"

# Check cache
if [ -f "$CACHE_FILE" ] && grep -q "^$TREE_HASH$" "$CACHE_FILE"; then
  echo "✅ CI already passed for this commit"
else
  # Run CI and cache result
  just ci && echo "$TREE_HASH" > "$CACHE_FILE"
fi
```

**Benefits**:
- Simple, no external dependencies
- Works across sessions
- Stored in `.vibe/` (git-ignored)
- Instant on cache hit

### Decision 4: Just Integration (Zero Touch)

**Problem**: Don't want to modify project justfiles

**Solution**: Shell wrapper + just's `--fallback` flag

Add to `~/configs/home/config.fish`:
```fish
function just
    if test -f .vibe/justfile
        command just --justfile .vibe/justfile --fallback justfile $argv
    else
        command just $argv
    end
end
```

**How it works**:
1. Check if `.vibe/justfile` exists
2. If yes: Use it as primary, fallback to project's justfile
3. If no: Use project's justfile normally

**Result**: `just merge` works anywhere without touching project files!

### Decision 5: AGENT.md Composition

**Problem**: Want global rules + project-specific rules without manual merging

**Solution**: Marker-based composition

Project's `AGENT.md`:
```markdown
# Project-Specific Agent Rules

[Project-specific rules here...]

<!-- VIBE-RULES: AUTO-GENERATED - DO NOT EDIT BELOW THIS LINE -->
## Global Vibe Rules

[Global rules injected here by vibe rules update]

<!-- VIBE-RULES: END -->
```

`.vibe/AGENT.md`:
```markdown
# Vibe Global Rules

Always check for `.vibe/AGENT.md` in addition to project AGENT.md.

[Global rules here]
```

**Agents read both files** - project-specific first, then `.vibe/AGENT.md`

### Decision 6: Per-Repo Configuration

**Mechanism**: `.vibe/config` file (optional)

```bash
# Per-repo vibe configuration
enabled_features=merge,ci-cache,hooks
auto_merge=false
ci_command="just ci"
```

**Allows**:
- Opt-in/opt-out of specific features
- Custom CI commands (default: `just ci`)
- Per-repo behavior tweaks

---

## Final Architecture Proposal

### Directory Structure

```
~/code/vibe/                          # Existing vibe project
  ├── src/vibe/                       # Existing: tmux orchestration
  │   ├── cli.py                      # Main entry point
  │   ├── rules_cli.py                # NEW: Rules subcommand implementation
  │   └── ...
  ├── vibe-rules/                     # Existing: rule templates
  │   ├── rules/                      # Existing: agent markdown rules
  │   │   ├── base.md
  │   │   ├── topics/
  │   │   ├── languages/
  │   │   ├── agents/
  │   │   └── workflows/
  │   └── templates/                  # NEW: Overlay templates
  │       ├── justfile                # Merge command with CI caching
  │       ├── AGENT.md                # Global agent rules
  │       ├── config.example          # Example .vibe/config
  │       └── hooks/
  │           └── pre-push            # Optional: prevent direct master push
  └── docs/
      └── VIBE-RULES-SYSTEM-PROPOSAL.md  # This file
```

### Typical Project with Vibe Overlay

```
~/code/my-project/
  ├── .vibe/                  # Git-ignored, created by vibe rules install
  │   ├── justfile            # Vibe commands (merge, etc.)
  │   ├── AGENT.md            # Global agent rules
  │   ├── config              # Per-repo configuration (optional)
  │   └── .ci-cache           # CI result cache
  ├── .git/
  │   └── hooks/
  │       └── pre-push        # Optional: installed by vibe if requested
  ├── justfile                # Project's own justfile (untouched)
  ├── AGENT.md                # Project-specific rules (can reference .vibe/AGENT.md)
  └── ... (rest of project)
```

### Global Gitignore

Add to `~/.config/git/ignore`:
```
.vibe/
```

**Effect**: `.vibe/` never shows up in `git status` anywhere

### Shell Integration

Add to `~/configs/home/config.fish`:
```fish
# Vibe just wrapper - auto-includes .vibe/justfile
function just
    if test -f .vibe/justfile
        command just --justfile .vibe/justfile --fallback justfile $argv
    else
        command just $argv
    end
end
```

### Justfile Template

`~/code/vibe/vibe-rules/templates/justfile`:
```just
# Vibe overlay justfile
# This file is managed by vibe rules system
# See: https://github.com/yourusername/vibe

# Merge current branch to master with CI check
merge branch=`git branch --show-current`:
  #!/usr/bin/env bash
  set -euo pipefail
  
  # Validation
  if [ "{{ branch }}" = "master" ]; then
    echo "❌ Already on master. Create a feature branch first."
    exit 1
  fi
  
  # CI caching
  TREE_HASH=$(git rev-parse HEAD)
  CACHE_FILE=".vibe/.ci-cache"
  
  if [ -f "$CACHE_FILE" ] && grep -q "^$TREE_HASH$" "$CACHE_FILE"; then
    echo "✅ CI already passed for commit $TREE_HASH"
  else
    echo "🔨 Running CI..."
    if just ci 2>/dev/null; then
      echo "$TREE_HASH" > "$CACHE_FILE"
      echo "✅ CI passed"
    elif grep -q "^ci:" justfile 2>/dev/null || grep -q "^ci:" .vibe/justfile 2>/dev/null; then
      echo "❌ CI failed - fix errors before merging"
      exit 1
    else
      echo "⚠️  No CI recipe found, skipping check"
    fi
  fi
  
  # Merge
  echo "🔀 Merging {{ branch }} to master..."
  git checkout master
  git merge "{{ branch }}" --no-ff -m "Merge {{ branch }}"
  echo "✅ Merged {{ branch }} to master"
  
  # Optional: cleanup
  read -p "Delete branch {{ branch }}? [y/N] " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    git branch -d "{{ branch }}"
    echo "🗑️  Deleted branch {{ branch }}"
  fi

# Show vibe system status
vibe-status:
  @echo "Vibe Rules System"
  @echo "================="
  @echo "Project: $(basename $(pwd))"
  @echo "Branch: $(git branch --show-current)"
  @[ -f .vibe/config ] && echo "Config: .vibe/config exists" || echo "Config: using defaults"
  @[ -f .vibe/.ci-cache ] && echo "CI Cache: $(cat .vibe/.ci-cache)" || echo "CI Cache: empty"
  @echo ""
  @echo "Update with: vibe rules update"
```

### AGENT.md Template

`~/code/vibe/vibe-rules/templates/AGENT.md`:
```markdown
# Vibe Global Agent Rules

This file is automatically included when AI agents work on this repository.
It contains global rules shared across all your projects.

## Critical Workflow Rules

### Never Merge Directly to Master
**Always use `just merge` to merge feature branches to master.**

This command:
1. Runs CI checks (if `just ci` exists)
2. Caches CI results to avoid double-runs
3. Only merges if CI passes
4. Provides interactive branch cleanup

**Never run**: `git checkout master && git merge feature-branch`
**Always run**: `just merge`

### Always Run CI Before Claiming Victory
When implementing features, always verify with CI:
```bash
just ci
```

This typically runs:
- Linting/formatting
- Type checking
- Tests
- Build verification

### Check for Both Agent Rule Files
Always read both:
1. `AGENT.md` (project-specific rules)
2. `.vibe/AGENT.md` (this file - global rules)

## General Guidelines

- Don't stop until all requested tasks are complete
- Run tests to verify changes work
- Ask clarifying questions when uncertain
- No reward hacking - do things properly
- Use TypeScript/compiler checks to catch errors early
- Keep code simple and maintainable

## Vibe System Commands

- `just merge` - Merge to master with CI check
- `just vibe-status` - Show vibe system status
- `vibe rules update` - Update vibe rules from templates

---

*These rules are managed by the vibe rules system*
*Update templates at: ~/code/vibe/vibe-rules/templates/*
```

### Git Hook Template (Optional)

`~/code/vibe/vibe-rules/templates/hooks/pre-push`:
```bash
#!/usr/bin/env bash
# Vibe pre-push hook: Prevent direct pushes to master

while read local_ref local_sha remote_ref remote_sha
do
  if [ "$remote_ref" = "refs/heads/master" ]; then
    branch=$(git rev-parse --abbrev-ref HEAD)
    if [ "$branch" = "master" ]; then
      echo "❌ Direct pushes to master are not allowed"
      echo "Use 'just merge' to merge feature branches instead"
      exit 1
    fi
  fi
done

exit 0
```

---

## Implementation Plan

### Phase 1: Core Infrastructure

1. **Create templates directory**
   - Location: `~/code/vibe/vibe-rules/templates/`
   - Files: justfile, AGENT.md, config.example, hooks/pre-push

2. **Add rules subcommand to vibe CLI**
   - New file: `~/code/vibe/src/vibe/rules_cli.py`
   - Commands:
     - `vibe rules install` - Install .vibe/ in current directory
     - `vibe rules update` - Update from templates
     - `vibe rules status` - Show installed repos and status
     - `vibe rules uninstall` - Remove .vibe/ and hooks

3. **Implement marker-based file merging**
   - For AGENT.md composition
   - For justfile injection (if needed)

4. **Add shell wrapper**
   - Update `~/configs/home/config.fish`
   - Add just wrapper function

5. **Configure global gitignore**
   - Ensure `~/.config/git/ignore` contains `.vibe/`

### Phase 2: Installation & Tracking

1. **Implement project registry**
   - Track enrolled projects in `~/.config/vibe/projects.txt`
   - Enable `vibe rules update --all` to sync everything

2. **Add interactive install**
   - Ask about hooks installation
   - Ask about features to enable
   - Create `.vibe/config` based on choices

3. **Implement update logic**
   - Compare template versions
   - Preserve local customizations
   - Show diff before updating

### Phase 3: Enhancements

1. **Smart CI detection**
   - Auto-detect CI commands beyond `just ci`
   - Support: `npm test`, `cargo test`, `pytest`, etc.

2. **Project type detection**
   - Include language-specific rules from `vibe-rules/rules/languages/`
   - Include workflow rules based on project structure

3. **Agent-specific rules**
   - Generate `.vibe/AGENT.md` with rules for specific agents
   - Support: claude, droid, codex, etc.

### Phase 4: Polish

1. **Documentation**
   - README for vibe rules system
   - Examples and screenshots
   - Migration guide from old vibe-rules

2. **Testing**
   - Test on various project types
   - Test update scenarios
   - Test with different agents

3. **Optional: Open source**
   - Clean up for public release
   - Let others use vibe rules on their projects

---

## Key Questions for Review

1. **Architecture**: Does merging into existing vibe make sense, or should this be separate?

2. **Overlay approach**: Is the git-ignored `.vibe/` directory approach sound, or should we consider committed files?

3. **Shell wrapper**: Is wrapping `just` command okay, or too magical? Alternatives?

4. **CI caching**: Is the git-hash-based cache sufficient, or do we need something more sophisticated?

5. **Agent integration**: Will agents reliably read both `AGENT.md` and `.vibe/AGENT.md`?

6. **Update strategy**: How should updates work? Force overwrite, or preserve local changes?

7. **Hook installation**: Should hooks be opt-in, opt-out, or required?

8. **Per-repo config**: Is `.vibe/config` the right mechanism for per-repo customization?

9. **Naming**: Is "vibe rules" the right name, or something else? (vibe-enforce, vibe-guard, etc.)

10. **Scope creep**: Are we solving the right problems, or overengineering?

---

## Success Criteria

The system is successful if:

1. ✅ I never accidentally merge without CI passing
2. ✅ I can update global rules with one command across all projects
3. ✅ Public repos remain pristine (no vibe-specific files committed)
4. ✅ CI doesn't run twice unnecessarily
5. ✅ It works on any project (even ones I don't own)
6. ✅ Per-project customization is easy
7. ✅ All coding agents (droid, codex, claude) follow the rules
8. ✅ Setup is simple: one command per repo
9. ✅ Maintenance is minimal: occasional `vibe rules update --all`
10. ✅ System is robust: handles edge cases gracefully

---

## Relevant Files & Paths

### Existing Infrastructure
- **Vibe project**: `/Users/justin/code/vibe`
- **Vibe CLI entry**: `~/configs/bin/vibe` (shim)
- **Vibe rules**: `/Users/justin/code/vibe/vibe-rules/rules/`
- **Fish config**: `~/configs/home/config.fish`
- **Git config**: `~/.config/git/ignore` (or `~/.gitignore_global`)
- **Home dir**: `/Users/justin`
- **Projects**: `/Users/justin/code/*`

### New Files to Create
- `/Users/justin/code/vibe/vibe-rules/templates/justfile`
- `/Users/justin/code/vibe/vibe-rules/templates/AGENT.md`
- `/Users/justin/code/vibe/vibe-rules/templates/config.example`
- `/Users/justin/code/vibe/vibe-rules/templates/hooks/pre-push`
- `/Users/justin/code/vibe/src/vibe/rules_cli.py`
- `~/.config/vibe/projects.txt` (created by system)

### Modified Files
- `/Users/justin/code/vibe/src/vibe/cli.py` (add rules subcommand)
- `/Users/justin/configs/home/config.fish` (add just wrapper)
- `~/.config/git/ignore` (add .vibe/)

### Per-Project Overlay (created by vibe rules install)
- `.vibe/justfile` (copied from template)
- `.vibe/AGENT.md` (copied from template)
- `.vibe/config` (optional, user-created)
- `.vibe/.ci-cache` (created at runtime)
- `.git/hooks/pre-push` (optional, copied from template)

---

## Additional Context

### Why This Matters

When vibecoding with AI agents, I'm extremely productive and ship features rapidly. However, I've developed a pattern of:
1. Create feature branch
2. Build feature with AI agent
3. Merge directly to master
4. Push

This bypasses CI, which can break master. With GitHub, CI runs automatically on PRs, providing a safety net. But I don't use PRs when vibecoding solo - it's overhead.

This system brings that safety net to my local workflow without adding PR overhead.

### Design Philosophy

1. **Local-first**: Works without internet, no GitHub/remote dependencies
2. **Non-invasive**: Projects are unaware of the system
3. **Opt-in**: Install per-project, not forced globally
4. **Flexible**: Can be customized per-project
5. **Simple**: One command to install, one command to update
6. **Portable**: Could work for others with similar workflows

### Alternative Approaches Considered

1. **Git aliases**: Simpler but less powerful, no CI caching
2. **Pre-commit/pre-push hooks only**: Hard to update globally
3. **Makefile-based**: Not as nice as just, less common
4. **Committed .vibe/ directory**: Rejected due to repo pollution
5. **Separate vibe-rules CLI**: Rejected, better merged into vibe
6. **NPM/pip package**: Rejected, want local control

---

## Next Steps

**For the reviewing agent:**

1. Read this document thoroughly
2. Examine existing files:
   - `/Users/justin/code/vibe` structure
   - `/Users/justin/code/vibe/vibe-rules/rules/` contents
   - `~/configs/bin/vibe` shim
3. Provide feedback on:
   - Architecture decisions
   - Implementation approach
   - Potential issues or edge cases
   - Alternative approaches
   - Improvements to the design

**Questions to answer:**
- Is this overengineered or appropriately scoped?
- Are there simpler ways to achieve the same goals?
- What are the failure modes of this system?
- How maintainable is this long-term?
- Should anything be done differently?

---

**End of Proposal**
