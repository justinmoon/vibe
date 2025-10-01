# Version Compatibility ⚠️

<!-- Source: slipbox@68468a7de53c CLAUDE.md -->
### slipbox: Version Compatibility ⚠️

**Client and SDK versions MUST match or SSE breaks!**

- We use: `@starfederation/datastar@1.0.0-beta.11` + matching SDK
- beta.11 uses `mergeFragments()` (NOT `patchElements()` - that's old)
- Check package.json for exact versions
