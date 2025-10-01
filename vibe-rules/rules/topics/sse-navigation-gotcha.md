# SSE Navigation Gotcha

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
### slipbox: SSE Navigation Gotcha

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
