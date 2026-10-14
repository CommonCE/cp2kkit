# Prompt: implement a feature or fix a defect

Copy this prompt and replace the placeholders.

---

Read `.agents/DEVELOPMENT.md` and inspect the actual repository state first.
Use English throughout development: documentation, prompts, comments/docstrings,
identifiers, user-facing messages, and reports, unless the user explicitly requests
another communication language. Preserve original quotations, citations, paths, and user data.

Task: <feature to implement or defect to fix>
Scope: <modules, interfaces, files; locate them first if unclear>
Acceptance criteria: <observable behavior, I/O, error handling, compatibility>

Requirements:

1. Read relevant source/configuration/tests and fixture provenance. Explain current
   behavior and the smallest change plan first.
2. Ask about ambiguous scope/scientific settings; do not expand to unrelated modules
   or silently change the physical model.
3. Reuse project interfaces, exceptions, and exclusive writers; preserve unrelated
   behavior and exit codes.
4. Verify scientific keywords/formats against the actual target-version manual/source.
   Record actual external sources affecting implementation; do not invent defaults.
5. Check terms and record provenance/citations before referencing third-party implementations.
6. Add normal/error/boundary/overwrite-protection tests; run focused tests, then
   regression and syntax checks.
7. Change development goals only when requested. After a feature round, follow
   `.agents/prompts/update-version-docs.md` and update version/changelog/documentation once.
8. Do not run CP2K, overwrite results, install unnecessary dependencies, or commit/push automatically.

Report implementation, paths, validation, and unverified limitations in English
unless the user explicitly requests another language.

---

Related: [development rules](../DEVELOPMENT.md), [architecture](../../docs/architecture.md).
