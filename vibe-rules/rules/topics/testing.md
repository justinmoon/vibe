# Testing

<!-- Source: hypermedia-starter@0985c255ef3d CLAUDE.md -->
## hypermedia-starter: Testing

Use `bun test` to run tests.

```ts#index.test.ts
import { test, expect } from "bun:test";

test("hello world", () => {
  expect(1).toBe(1);
});
```
