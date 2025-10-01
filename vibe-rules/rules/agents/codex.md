# Codex Agent Guidelines

<!-- Source: nrc/nrc-bare@e6151fa1fcc0 AGENTS.md -->
## nrc/nrc-bare: AGENTS.md

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

<!-- Source: projects/nostrdb-zig@c9f497fa7c3f AGENTS.md -->
## projects/nostrdb-zig: AGENTS.md

- If you want to test out nix builds or debug issues on linux, you can `ssh hetzner` and experiment there

<!-- Source: moq/demos@ef4d9005aba0 AGENTS.md -->
## moq/demos: AGENTS.md

always run the tests before claiming you finished a feature. never deliver broken software.

<!-- Source: moq/av-demo@bce94ba724d2 AGENTS.md -->
## moq/av-demo: AGENTS.md

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
