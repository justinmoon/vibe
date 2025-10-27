# Vibe Rules System - Design Proposal

## Problem
When vibecoding, I bypass CI and merge directly to master. Need local enforcement without repo pollution.

## Solution
Local overlay system that adds CI checks + standardized rules to any project.

---

## Architecture

### The .vibe/ Overlay (git-ignored)
```
~/code/my-project/
  ├── .vibe/              # Created by: vibe rules install
  │   ├── justfile        # Contains: just merge command
  │   ├── config          # Optional per-repo settings
  │   └── .ci-cache       # CI results by git hash
  ├── AGENT.md            # Modified: global rules injected via markers
  └── .git/hooks/pre-push # Optional: prevent direct master push
```

### Global Setup (one-time)
1. Add to `~/.config/git/ignore`: `.vibe/`
2. Add to `~/configs/home/config.fish`:
```fish
function just
    if test -f .vibe/justfile
        command just --justfile .vibe/justfile --fallback justfile $argv
    else
        command just $argv
    fi
end
```

### Template Location
```
~/code/vibe/vibe-rules/
  └── templates/
      ├── justfile          # Merge command with CI caching
      ├── agent-rules.md    # Global agent rules
      ├── config.example    # Optional settings
      └── hooks/pre-push    # Optional git hook
```

---

## Key Features

### 1. CI-Checked Merge
```bash
just merge    # Runs CI, caches result, merges to master
```

**Implementation** (in `.vibe/justfile`):
```just
merge:
  #!/usr/bin/env bash
  set -euo pipefail
  
  # Check cache
  HASH=$(git rev-parse HEAD)
  if grep -q "^$HASH$" .vibe/.ci-cache 2>/dev/null; then
    echo "✅ CI already passed"
  else
    echo "🔨 Running CI..."
    just ci && echo "$HASH" > .vibe/.ci-cache
  fi
  
  # Merge
  BRANCH=$(git branch --show-current)
  git checkout master && git merge "$BRANCH" --no-ff
```

### 2. Agent Rule Injection
**Before** (project AGENT.md):
```markdown
# My Project Rules
- Use tabs not spaces
```

**After** (`vibe rules install`):
```markdown
# My Project Rules
- Use tabs not spaces

<!-- VIBE-RULES: AUTO-GENERATED -->
## Global Vibe Rules
- **NEVER merge to master directly** - use `just merge`
- Always run `just ci` before claiming victory
- Check `.vibe/` directory for additional rules
<!-- VIBE-RULES: END -->
```

`vibe rules update` only modifies content between markers.

### 3. Just Integration (zero touch)
Fish wrapper makes `.vibe/justfile` commands available:
- `just merge` → runs `.vibe/justfile` merge recipe
- `just ci` → fallback to project's justfile
- `just test` → fallback to project's justfile

No modification of project files needed!

---

## Commands

```bash
# Install in current repo
vibe rules install

# Update all enrolled repos from templates
vibe rules update [--all]

# Show status
vibe rules status

# Remove from current repo
vibe rules uninstall
```

---

## Implementation Plan

### Phase 1: Core (MVP)
1. Create templates in `~/code/vibe/vibe-rules/templates/`
2. Add `src/vibe/rules_cli.py` with install/update/uninstall
3. Wire into `src/vibe/cli.py` as subcommand
4. Add just wrapper to fish config
5. Test on one project

### Phase 2: Polish
1. Add project registry (`~/.config/vibe/projects.txt`)
2. Implement `--all` flag for bulk updates
3. Add per-repo config support (`.vibe/config`)
4. Smart CI detection (npm test, cargo test, etc.)

### Phase 3: Optional
1. Language-specific rule injection from `vibe-rules/rules/languages/`
2. Agent-specific rule variants
3. Git hook installation option

---

## Marker-Based AGENT.md Update Algorithm

```python
def update_agent_md(project_path, global_rules):
    agent_md = project_path / "AGENT.md"
    
    if not agent_md.exists():
        # Create new file with just global rules
        content = f"# Agent Rules\n\n{MARKERS[0]}\n{global_rules}\n{MARKERS[1]}"
        agent_md.write_text(content)
        return
    
    content = agent_md.read_text()
    
    if MARKERS[0] in content:
        # Update existing markers
        before = content.split(MARKERS[0])[0]
        after = content.split(MARKERS[1])[1] if MARKERS[1] in content else ""
        new_content = f"{before}{MARKERS[0]}\n{global_rules}\n{MARKERS[1]}{after}"
    else:
        # Append markers at end
        new_content = f"{content}\n\n{MARKERS[0]}\n{global_rules}\n{MARKERS[1]}\n"
    
    agent_md.write_text(new_content)
```

---

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Merge vs Separate | Merge into `~/code/vibe` | Already orchestration tool, natural fit |
| Committed vs Local | Local `.vibe/` only | Zero repo pollution, works on any project |
| CI Caching | Git hash in `.vibe/.ci-cache` | Simple, no dependencies, good enough |
| Just Integration | Shell wrapper function | Zero touch, transparent to projects |
| Agent Rules | Marker-based injection | Agents already look for AGENT.md |
| Update Strategy | Template sync with markers | Preserves local customizations |

---

## Success Criteria

✅ Never merge without CI passing  
✅ One command updates all repos  
✅ Public repos stay pristine  
✅ CI runs once per commit  
✅ Works on any project  
✅ Per-repo customization easy  
✅ All agents follow rules  

---

## Critical Paths

**Files to create:**
- `/Users/justin/code/vibe/vibe-rules/templates/justfile`
- `/Users/justin/code/vibe/vibe-rules/templates/agent-rules.md`
- `/Users/justin/code/vibe/src/vibe/rules_cli.py`

**Files to modify:**
- `/Users/justin/code/vibe/src/vibe/cli.py` (add rules subcommand)
- `/Users/justin/configs/home/config.fish` (add just wrapper)
- `~/.config/git/ignore` (add `.vibe/`)

**Runtime creation per-repo:**
- `.vibe/justfile` (from template)
- `.vibe/config` (optional)
- `.vibe/.ci-cache` (at runtime)
- `AGENT.md` (marker injection)

---

## Open Questions

1. Should git hooks be installed by default or opt-in?
2. What if project has no `just ci` recipe? Skip or error?
3. Handle projects without AGENT.md - create or skip?
4. Track enrolled projects automatically or explicit opt-in?
5. How to handle .vibe/ in worktrees (shared or per-worktree)?

---

**Next Step**: Review this design, then implement Phase 1.
