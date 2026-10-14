# cp2kkit development prompts

This directory stores project-specific development rules and reusable prompts for Git.
It is not runtime configuration, a third-party license, or a calculation-results store.

## Usage

Start a session with the [development rules](DEVELOPMENT.md), then choose a template:

| Template | Purpose |
|---|---|
| [Implement a feature](prompts/implement-feature.md) | Add features/fix defects while preserving unrelated interfaces and behavior |
| [Reference Multiwfn](prompts/multiwfn-reference.md) | Inspect upstream source, extend CP2K generation in stages, and record provenance |
| [Review](prompts/review.md) | Read-only review of implementation, scientific settings, tests, and authorization |
| [Update version and documentation](prompts/update-version-docs.md) | Bump once per feature round, update documentation/changelog, and verify consistency |

Replace `<...>` with actual tasks, files, or versions; do not guess missing information.
For example:

> Read `.agents/DEVELOPMENT.md` and `.agents/prompts/multiwfn-reference.md`.
> Extend only per-KIND initial magnetic moments in CP2K input generation.
> Inspect existing interfaces and sources before proposing a minimal implementation.
> Do not start calculations or automatically commit/push.

**Do not assume tools automatically load `.agents/`.** Reference these files explicitly.
If automatic loading is needed, configure it according to the actual tool's rules;
these templates are not a universal automatic-loading entry point.

## Maintenance rules

- Use English by default for all development, documentation, prompts, comments,
  messages, and reports. Follow explicit user language requests; preserve original
  third-party text, citations, scientific syntax, paths, and user data.
- Versions use A.B.C: A is the user's decision only; features increment B/reset C;
  fixes increment C with A/B unchanged. Bump once per round and update documentation.
- Current code/tests and explicit user requirements override historical notes.
  Templates do not expand authorization.
- Store reusable rules only: no secrets, personal data, raw conversations, large
  calculation results, or transient logs.
- Goals/progress follow the [roadmap](../docs/roadmap.md); planned outcomes are not completed results.
- Keep third-party authorization/provenance in [notices](../THIRD_PARTY_NOTICES.md)
  and `third_party/`, not here or in ignored directories.
- Recheck these templates as implementation changes. Do not freeze obsolete test
  counts, environment paths, or unverified compatibility claims.
