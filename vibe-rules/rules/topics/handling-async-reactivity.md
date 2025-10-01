# Handling Async Reactivity

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
### slipbox: Handling Async Reactivity

- Always wait for DOM changes with `waitForSelector`
- Use `waitForFunction` for complex state checks
- Avoid arbitrary `waitForTimeout` - wait for specific conditions
- Test that changes persist across page reloads
