# Base Guidelines

<!-- Source: nrc/nrc-bare@e6151fa1fcc0 AGENTS.md -->
## nrc/nrc-bare: overview

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

<!-- Source: nrc/nrc-bare@3a7b9b8f17ba CLAUDE.md -->
## nrc/nrc-bare: overview

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

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
## slipbox: overview

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

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
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

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
### Test Philosophy

- **Test the Result, Not the Mechanism** - Test what users see, not SSE internals
- **UI Tests for Reactivity** - Playwright tests are best for DOM reactivity
- **Test User Workflows** - Full interactions, not individual operations

<!-- Source: projects/nostrdb-zig@c9f497fa7c3f AGENTS.md -->
## projects/nostrdb-zig: overview

- If you want to test out nix builds or debug issues on linux, you can `ssh hetzner` and experiment there

<!-- Source: projects/nostrdb-zig@0047d591a0cd CLAUDE.md -->
## projects/nostrdb-zig: overview

- If you want to test out nix builds or debug issues on linux, you can `ssh hetzner` and experiment there

<!-- Source: hypermedia-starter@0985c255ef3d CLAUDE.md -->
## hypermedia-starter: overview

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

<!-- Source: slipbox-tauri-2@425c4038051f CLAUDE.md -->
## slipbox-tauri-2: overview

- We use Tauri v2. Never give answers for Tauri v1.
- Never put the `as sse` in these datastart invocations: '@post("/inc", {as:"sse"})' 
- If a given piece of rust code to handle HTTP / SSE is only used once, put it in the relevant src/routes/ file. Don't create a new component in src/components.rs for a block of code that's only used in one place.
- Keep the javascript as simple as we reasonably can. Implement as much as we can with Rust and datastar markup / merge functions.
- `body` is not a valid argument to `@post` in datastar. You make this mistake constantly. the valid options are here: https://data-star.dev/reference/overview#action-plugins.

<!-- Source: moq/demos@ef4d9005aba0 AGENTS.md -->
## moq/demos: overview

always run the tests before claiming you finished a feature. never deliver broken software.
