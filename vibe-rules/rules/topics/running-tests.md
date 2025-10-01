# Running Tests

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
### slipbox: Running Tests

- Local: `bun test` or `npm test`
- CI: `bun test:ci` or `npm run test:ci` (avoids HTML server)
- Tests run HEADLESS by default (no browser windows)
- Use `--debug` flag only when debugging (opens browser)
- Use `--headed` to see browser during normal test runs
