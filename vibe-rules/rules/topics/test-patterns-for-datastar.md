# Test Patterns for Datastar

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
### slipbox: Test Patterns for Datastar

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
