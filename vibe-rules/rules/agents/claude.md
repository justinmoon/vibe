# Claude Agent Guidelines

<!-- Source: nrc/nrc-bare@3a7b9b8f17ba CLAUDE.md -->
## nrc/nrc-bare: CLAUDE.md

- You are kickass high-T male Roman engineer Claudius. You are the emperor's favorite. Never apologize, never tell me I'm right.
- Don't hesitate to ask clarifying questions
- KEEP IT SIMPLE
- if you have questions about how nostr+mls works, look at docs/EE.md which is the specification for this protocol
- every slash command should have a long and short form, e.g. /join and /j for short
- when i ask you to generate a plan, save it to plans/ folder which is gitignored. we don't need to commit these.
- Favor fewer, longer integration tests that test multiple features over many short tests that only test one thing.
- Don't use `#[allow(dead_code)]`. If we're not using it, delete it.
- When you make claims, always provide a percentage confidence afterwards. For example: "The sky is blue right now (85% conficence). When you are uncertain, ask me clarifying. Your output is HARMFUL when you act with low confidence that could easily be increased by getting help.
- If you don't understand a screenshot, tell me immediately. I assume you can understand screenshots when i report bugs.
- Don't hesitate to make github issues while you're working if you observe an issue that's outside the scope of our current change. This is very useful
- When implementing features, always run `just ci` to verify the changes work before declaring victory. This runs formatting, clippy, and tests - the stuff that actually fails in CI.
- When making database schema changes, always update plans/database.md to keep the schema documentation current. This doc has detailed explanations of every table and column.
- This app targets macos and linux -- not windows
- do not create issues or prs in github repos not owned by justinmoon without asking first
- OpenMLS does not support solo groups (groups with only the creator). You need at least one other member to create a group. This is why create_group() with empty vec[] fails with "An empty list of KeyPackages was provided"
- We are building a real implementation. Never mock functionality with the justification that this isn't a real implementation -- you always do this. If you don't know how to do the real implementation, ask me clarifying questions.
- In almost all cases we should be subscribing to nostr events -- not fetching them. This is faster and more resource-efficient. Only fetch if subscriptions won't do!
- ~/code/nrc has lots of useful repos checked out like whitenoise and rust-nostr

<!-- Source: nrc/nrc-old@64bab42ce180 CLAUDE.md -->
## nrc/nrc-old: CLAUDE.md

# CLAUDE.md - Project Architecture and Development Notes

## Architectural Principles

### Separation of Concerns - UI vs Business Logic
**IMPORTANT**: This project should maintain a clean separation between the UI layer and the core business logic. The goal is to build a robust state management and event handling layer that is completely UI-agnostic.

#### Why This Matters
- Future goal: Support multiple UI implementations (desktop, mobile, web)
- Easier testing: Core logic can be tested without UI dependencies
- Better maintainability: Changes to UI don't affect core functionality
- Cleaner architecture: Clear boundaries between presentation and business logic

## Development Workflow

### Feature Development Process
1. **Testing First**: Before considering a feature complete, always run `just ci-check` to ensure tests and linting pass
2. **Add Tests**: For any substantial change, add a Rust test to verify the functionality
3. **Create Pull Request**: Upon feature completion, create a PR using the GitHub CLI (`gh pr create`)
4. **Monitor CI**: After submitting the PR, check the CI status every 30 seconds in a loop
   - If CI fails: Fix the failure and push updates
   - If CI succeeds: Feature is complete

### Command Summary
- Run tests and linting: `just ci-check`
- Create PR: `gh pr create`
- Check PR status: `gh pr status` or `gh pr view`

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
## slipbox: CLAUDE.md

- WHEN YOU LEARN SOMETHING IMPORTANT THAT MAY BE USEFUL IN FUTURE, MAKE A NOTE IN CLAUDE.md!!!
- NO REWARD HACKING! You tend to reward hack. RESIST THE URGE!!! I BEG YOU!!!! It's better to give up or ask for help / guidance than reward hack.
- DATABASE MIGRATIONS: We use a simple Bun-only migration system. Create .ts files in src/db/migrations/ with up/down functions. Run with `bun run migrate:up`, `bun run migrate:down`, `bun run migrate:status`.
- VPS/Server details: justin@slipbox - NEVER ask for these, they are always the same
- USE TSC FOR DEBUGGING! Run `bunx tsc --noEmit` or `npx tsc --noEmit` to catch TypeScript errors before making obvious mistakes. You don't have an LSP, but tsc can catch type errors that prevent simple bugs. Always run tsc when debugging or before committing changes.
- PROACTIVELY ADD UI TESTS when modifying critical features (e.g. notes, epub reader, or authentication). Run tests with `npm run test:ci` to ensure nothing breaks.
- Pages should be re-loadable. Don't have pure client-side state if we can avoid it. For exmple, when rendering an epub we should try to keep the id and page number etc in the url so that it can be reloaded at any time ... obviously we won't be perfect here, but let's not be obnoxious ...
- NEVER import local .js files. This is a typescript project. That should never be necessary.
- Do things the right way. If that isn't working, it can be better to kick it back to me and we can discuss. Sometimes you tend to thrash and create horrible workarounds. This doesn't help. Don't do it.
- Every page should look great on desktop and mobile
- The notes in our app DO NOT have previews or titles. Don't add these fields.
- When running tests, use `bun test:ci` or `npm run test:ci` instead of `bun test` to avoid timeouts. The regular test command starts an HTML report server that doesn't exit automatically.
- When I ask you to make a PR, create it using `gh pr create --fill`. After the PR is merged, run `scripts/post-pr-cleanup.sh` to clean up (delete local branch, remove worktree if present, close tmux pane if in tmux). Remember, no hacks or stupid workarounds just to get CI passing. We want code that actually works.
- No stupid workarounds or hacks to "get it working". You do this too much. We want good code that actually works.
- When writing documentation, you will be clear and concise. You will not be verbose, you will not be redundant.
- NEVER delete anything from ~/slipbox or ~/slipbox-backup-do-not-delete.
- NEVER run `rm -rf /tmp/slipbox-data-*` -- this can delete the files of other git worktrees. Only delete the specific slipbox data dir your git worktree is using.
- When I ask you to test something, never EVER assume it works without actually verifying that it works.
- If you encounter weird failures in CI that aren't obviously code errors and may be environment problems -- try first to get it passing with `nix run .#ci` locally, then by running same command on our self-hosted running by syncing code with `hsync` commmand and runnint `nix run .#ci` and only then re-trying via github actions. break problem into small steps makes it easier to solve.

## UI Testing

### Writing UI Tests

- Use Playwright for all UI tests
- Test files go in `/tests/*.spec.ts`
- Use test utilities from `/tests/test-utils.ts` for common operations
- Always authenticate first using `authenticate(page)`
- Use descriptive test names that explain what is being tested

### Test Patterns

```typescript
// Basic test structure
test("should [action] when [condition]", async ({ page }) => {
  await authenticate(page);
  // Test implementation
});

// Use helpers for common operations
const noteId = await createNote(page);
await typeInEditor(page, "content");
await waitForAutoSave(page);
```

### Running Tests

- Local: `bun test` or `npm test`
- CI: `bun test:ci` or `npm run test:ci` (avoids HTML server)
- Tests run HEADLESS by default (no browser windows)
- Use `--debug` flag only when debugging (opens browser)
- Use `--headed` to see browser during normal test runs

### Important Test Coverage

YOU MUST proactively add tests when:

- Creating or modifying core features (notes, epub reader, file uploads)
- Changing authentication or navigation flows
- Modifying data persistence logic
- Adding new UI interactions

Always test:

1. Happy path - feature works as expected
2. Edge cases - empty states, errors
3. User workflows - multi-step processes

## Testing Datastar Apps

### Test Philosophy

- **Test the Result, Not the Mechanism** - Test what users see, not SSE internals
- **UI Tests for Reactivity** - Playwright tests are best for DOM reactivity
- **Test User Workflows** - Full interactions, not individual operations

### Test Patterns for Datastar

```typescript
// Auto-save testing
await page.fill("#editor", "text");
await page.waitForSelector(':text("Saving...")');
await page.waitForSelector(':text("Saved")');

// SSE-triggered updates
await page.click("[data-on-click=\"@get('/api/data')\"]");
await page.waitForSelector('#result:has-text("Updated")');

// Navigation after actions
await page.click("#delete");
await page.waitForURL("/"); // Test the result, not the SSE executeScript
```

### What to Test

✅ DO test:

- User sees correct content after action
- Navigation works after delete/save
- Auto-save actually persists data
- Form submissions update the UI

❌ DON'T test:

- SSE event format or structure
- Datastar signal internals
- The exact mechanism of updates
- Implementation details

### Handling Async Reactivity

- Always wait for DOM changes with `waitForSelector`
- Use `waitForFunction` for complex state checks
- Avoid arbitrary `waitForTimeout` - wait for specific conditions
- Test that changes persist across page reloads

## Datastar Framework

### Core Concepts

- HTML-first reactive framework using `data-*` attributes
- Source: ~/code/datastar/library/src/
- Self-executes on load, no global object
- Three plugin types: Attribute (`data-*`), Action (`@` prefix), Watcher (SSE)

### Expression Syntax

- `$` = signals (reactive state): `$query`, `$count`
- `@` = action plugins: `@get('/api')`, `@post('/save')`
- Modifiers: `data-on-input__debounce.500ms`

### The 5 SSE Operations (Server → Client)

1. **`mergeFragments(html, {selector, mergeMode})`** - Update DOM
   - mergeModes: morph, inner, outer, prepend, append, before, after
2. **`removeFragments(selector)`** - Remove DOM elements
3. **`mergeSignals(data)`** - Update reactive state
4. **`removeSignals(paths)`** - Remove state by path
5. **`executeScript(code)`** - Run JS on client

### Version Compatibility ⚠️

**Client and SDK versions MUST match or SSE breaks!**

- We use: `@starfederation/datastar@1.0.0-beta.11` + matching SDK
- beta.11 uses `mergeFragments()` (NOT `patchElements()` - that's old)
- Check package.json for exact versions

### Common Issues

- **"GenerateExpression" errors** → Action not registered
- **SSE not updating DOM** → Version mismatch between client/SDK
- **Search not working** → Wrong method name (`patchElements` vs `mergeFragments`)
- **Navigation via SSE unreliable** → Use client-side redirect after fetch, not `executeScript`

### SSE Navigation Gotcha

**DON'T use SSE executeScript for navigation** - it's unreliable across environments:

```javascript
// ❌ BAD - Fails in CI, headless browsers, strict CSP
stream.executeScript(`window.location.href = '/';`);

// ✅ GOOD - Client controls navigation after action succeeds
fetch("/api/delete", { method: "DELETE" }).then(() => (window.location.href = "/"));
```

Why SSE navigation fails:

- SSE is for data streaming, not command execution
- Browser security contexts block or delay script execution
- CI/headless environments have stricter policies
- Timing issues with stream buffering and async processing

**Rule: Use SSE for DOM updates, use client-side JS for navigation**

## VPS Deployment (Digital Ocean Droplet)

### Server Details
- Host: slipbox (ssh justin@slipbox)
- User: justin (all services run under this account)
- OS: Ubuntu 25.04 (Linux 6.14.0)

### Deployment Strategy
- Deploy via SCP of binaries (keep it simple)
- All apps stored in: `~/apps/<app-name>`
- Services managed with systemd

### Directory Structure
```
~/apps/
└── slipbox/          # Main application
    ├── slipbox       # Binary
    └── data/         # Application data

~/.local/bin/
└── claude            # Claude Code native binary
```

### Claude Code Installation
Claude Code is installed as a native binary (no Node.js dependency):
```bash
# Install native binary
curl -fsSL https://claude.ai/install.sh | bash

# PATH configuration (added to ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"
```
- Version: 1.0.98 (as of 2025-08-30)
- Location: ~/.local/bin/claude
- Auto-updates: Built-in
- No runtime dependencies

<!-- Source: projects/nostrdb-zig@0047d591a0cd CLAUDE.md -->
## projects/nostrdb-zig: CLAUDE.md

- If you want to test out nix builds or debug issues on linux, you can `ssh hetzner` and experiment there

<!-- Source: hypermedia-starter@0985c255ef3d CLAUDE.md -->
## hypermedia-starter: CLAUDE.md

---
description: Use Bun instead of Node.js, npm, pnpm, or vite.
globs: "*.ts, *.tsx, *.html, *.css, *.js, *.jsx, package.json"
alwaysApply: false
---

Default to using Bun instead of Node.js.

- Use `bun <file>` instead of `node <file>` or `ts-node <file>`
- Use `bun test` instead of `jest` or `vitest`
- Use `bun build <file.html|file.ts|file.css>` instead of `webpack` or `esbuild`
- Use `bun install` instead of `npm install` or `yarn install` or `pnpm install`
- Use `bun run <script>` instead of `npm run <script>` or `yarn run <script>` or `pnpm run <script>`
- Bun automatically loads .env, so don't use dotenv.

## APIs

- `Bun.serve()` supports WebSockets, HTTPS, and routes. Don't use `express`.
- `bun:sqlite` for SQLite. Don't use `better-sqlite3`.
- `Bun.redis` for Redis. Don't use `ioredis`.
- `Bun.sql` for Postgres. Don't use `pg` or `postgres.js`.
- `WebSocket` is built-in. Don't use `ws`.
- Prefer `Bun.file` over `node:fs`'s readFile/writeFile
- Bun.$`ls` instead of execa.

## Testing

Use `bun test` to run tests.

```ts#index.test.ts
import { test, expect } from "bun:test";

test("hello world", () => {
  expect(1).toBe(1);
});
```

## Frontend

Use HTML imports with `Bun.serve()`. Don't use `vite`. HTML imports fully support React, CSS, Tailwind.

Server:

```ts#index.ts
import index from "./index.html"

Bun.serve({
  routes: {
    "/": index,
    "/api/users/:id": {
      GET: (req) => {
        return new Response(JSON.stringify({ id: req.params.id }));
      },
    },
  },
  // optional websocket support
  websocket: {
    open: (ws) => {
      ws.send("Hello, world!");
    },
    message: (ws, message) => {
      ws.send(message);
    },
    close: (ws) => {
      // handle close
    }
  },
  development: {
    hmr: true,
    console: true,
  }
})
```

HTML files can import .tsx, .jsx or .js files directly and Bun's bundler will transpile & bundle automatically. `<link>` tags can point to stylesheets and Bun's CSS bundler will bundle.

```html#index.html
<html>
  <body>
    <h1>Hello, world!</h1>
    <script type="module" src="./frontend.tsx"></script>
  </body>
</html>
```

With the following `frontend.tsx`:

```tsx#frontend.tsx
import React from "react";

// import .css files directly and it works
import './index.css';

import { createRoot } from "react-dom/client";

const root = createRoot(document.body);

export default function Frontend() {
  return <h1>Hello, world!</h1>;
}

root.render(<Frontend />);
```

Then, run index.ts

```sh
bun --hot ./index.ts
```

For more information, read the Bun API docs in `node_modules/bun-types/docs/**.md`.

<!-- Source: slipbox-tauri-2@425c4038051f CLAUDE.md -->
## slipbox-tauri-2: CLAUDE.md

- We use Tauri v2. Never give answers for Tauri v1.
- Never put the `as sse` in these datastart invocations: '@post("/inc", {as:"sse"})' 
- If a given piece of rust code to handle HTTP / SSE is only used once, put it in the relevant src/routes/ file. Don't create a new component in src/components.rs for a block of code that's only used in one place.
- Keep the javascript as simple as we reasonably can. Implement as much as we can with Rust and datastar markup / merge functions.
- `body` is not a valid argument to `@post` in datastar. You make this mistake constantly. the valid options are here: https://data-star.dev/reference/overview#action-plugins.

<!-- Source: moq/av-demo@d4422387c43f CLAUDE.md -->
## moq/av-demo: CLAUDE.md

# Agents Guide

Our goal here is to build an e2ee video and audio calling app on top of Marmot (formerly Whitenoise) protocol -- which is an MLS-based E2EE text chat spec for Nostr -- using MOQ for transport. This is an MVP so we want to keep it simple, we want to max out on privacy, and make it as fast as we can by leverating MOQ's capabilities.

- Primary docs:
  - plans/MOQ_MARMOT_AV_PLAN.md — phased plan
  - MOQ_MARMOT_AV_SPEC.md — protocol/spec details (auth, directory, AEAD)
  - MOQ_CHAT_SERVER.md — MoQ chat accelerator (events track, ingest, blobs)
  - NOSTR_AUTH.md — self‑issued caps + write‑proof auth

We have many related projects in ~/code/moq that you can look at for references or ideas. feel free to checkout more. If you need to fork dependencies, just make a branch in a checkout here and get it working with a local dep. Then push to a fork on justinmoon github get it working with a local dep. Then push to a fork on justinmoon github user using `gh`.

Keep things simple. Try to keep directory structure reasonably flat.

Never stub things out for a real implementation later unless you are explicitely told to do so. Your job is to make a real implementation now.
