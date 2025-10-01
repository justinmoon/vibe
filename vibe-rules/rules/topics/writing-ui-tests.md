# Writing UI Tests

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
### slipbox: Writing UI Tests

- Use Playwright for all UI tests
- Test files go in `/tests/*.spec.ts`
- Use test utilities from `/tests/test-utils.ts` for common operations
- Always authenticate first using `authenticate(page)`
- Use descriptive test names that explain what is being tested
