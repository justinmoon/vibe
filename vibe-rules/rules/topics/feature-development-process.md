# Feature Development Process

<!-- Source: nrc/nrc-old@64bab42ce180 CLAUDE.md -->
### nrc/nrc-old: Feature Development Process

1. **Testing First**: Before considering a feature complete, always run `just ci-check` to ensure tests and linting pass
2. **Add Tests**: For any substantial change, add a Rust test to verify the functionality
3. **Create Pull Request**: Upon feature completion, create a PR using the GitHub CLI (`gh pr create`)
4. **Monitor CI**: After submitting the PR, check the CI status every 30 seconds in a loop
   - If CI fails: Fix the failure and push updates
   - If CI succeeds: Feature is complete
