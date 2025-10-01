# The 5 SSE Operations (Server → Client)

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
### slipbox: The 5 SSE Operations (Server → Client)

1. **`mergeFragments(html, {selector, mergeMode})`** - Update DOM
   - mergeModes: morph, inner, outer, prepend, append, before, after
2. **`removeFragments(selector)`** - Remove DOM elements
3. **`mergeSignals(data)`** - Update reactive state
4. **`removeSignals(paths)`** - Remove state by path
5. **`executeScript(code)`** - Run JS on client
