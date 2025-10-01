# Test Patterns

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
### slipbox: Test Patterns

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
