# Common Issues

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
### slipbox: Common Issues

- **"GenerateExpression" errors** → Action not registered
- **SSE not updating DOM** → Version mismatch between client/SDK
- **Search not working** → Wrong method name (`patchElements` vs `mergeFragments`)
- **Navigation via SSE unreliable** → Use client-side redirect after fetch, not `executeScript`
