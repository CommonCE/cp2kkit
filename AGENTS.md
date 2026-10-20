# cp2kkit Agent Instructions

Before changing code, tests, or maintained documentation, read
[the development rules](.agents/DEVELOPMENT.md) and follow their applicable
requirements. Keep detailed project rules there rather than duplicating them here.

Use the actual repository state as the implementation reference. Inspect relevant
source, configuration, tests, fixture provenance, and existing user changes before
editing. Preserve unrelated changes.

Read additional documents according to the task:

- [README](README.md) and [project configuration](pyproject.toml) for scope and setup.
- [Architecture](docs/architecture.md) for architectural changes.
- [Schema](docs/schema.md) for data contracts.
- [Input generation](docs/input-generation.md) for generator behavior and limits.
- [Menu numbering](docs/menu-numbering-draft.md) for UI routing and identifiers.
- [Third-party notices](THIRD_PARTY_NOTICES.md), [Multiwfn terms](third_party/multiwfn/TERMS.md),
  and [provenance](third_party/multiwfn/PROVENANCE.md) for third-party references.

Use [the development prompts](.agents/README.md) as task-specific guidance when
relevant. Files in `.agents/prompts/` are not automatically registered Pi slash
commands.

Do not run CP2K or submit calculations as part of ordinary development tests.
Actual calculation validation requires explicit authorization and a new run
directory. Distinguish synthetic tests, keyword checks, actual execution,
convergence, and scientific validation; passing one level does not establish the
others.

Follow the testing and delivery requirements in `.agents/DEVELOPMENT.md`. Report
checks actually run and any unverified limitations. Do not commit or push unless
explicitly requested.
