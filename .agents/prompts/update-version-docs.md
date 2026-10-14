# Prompt: update the version and documentation after feature work

Copy this prompt and replace the placeholders; feature templates must follow this workflow too.

---

Read `.agents/DEVELOPMENT.md`; inspect actual source, versions, documentation, and Git status.
Use English for development text, documentation headings/prose, prompts, comments,
messages, commit messages, and reports unless the user explicitly requests another
communication language. Preserve original quotations, citations, paths, and user data.

Completed features: <actual implementation, not unfinished plans>
Compatibility changes: <interfaces, defaults, format restrictions, breaking changes>
User-specified version, if any: <version; otherwise apply the rules below>

Requirements:

1. Update software version and relevant documentation after each feature round.
   Bump once for a round containing multiple features, not once per file.
   Documentation/prompt-only edits do not independently require a bump.
2. Follow the user's A.B.C convention:
   - A is the major version, decided manually by the user. Never increment A
     automatically, even for breaking changes; ask first.
   - B is the minor version; increment it for new/updated features and reset C.
   - C increments for functionality/bug fixes; leave A/B unchanged.
   - A mixed feature/fix round increments B and resets C; bump once per round.
   - Explicit user versions take priority. Ask if the target is not higher than
     the current version or requirements conflict; do not downgrade.
   Explain default/interface migration impacts without using them to change A.
3. Synchronize `pyproject.toml`, `src/cp2kkit/__init__.py`'s `__version__`,
   README, and CLI `--version`. Do not hand-edit ignored egg-info, build outputs,
   or versions in old results. Software, schema, and target CP2K versions differ:
   do not blindly replace all version numbers. Assess schema changes independently.
4. Update `CHANGELOG.md` with actual additions/changes, defaults/migration,
   limitations, and validation boundaries. Do not invent history, release dates,
   or publication status. Preserve existing history.
5. Update README, `docs/roadmap.md`, and affected feature documents.
   Recheck architecture/schema for interface/data changes; update third-party
   provenance/terms when references change. Preserve historical versions/test counts.
   Check English-language consistency and local links.
6. Check version consistency; run focused tests, full regression, compileall,
   `git diff --check`, and `python -m cp2kkit --version`. Use counts from the
   actual run; state checks not run.
7. Report old -> new version, changed documentation paths, actual validation,
   and compatibility limitations in English unless another language is requested.
   A version bump is not publication or CP2K certification. Do not install, build,
   commit, or push automatically; preserve results and unrelated user files.

---

Related: [development rules](../DEVELOPMENT.md), [feature template](implement-feature.md),
[README](../../README.md), [changelog](../../CHANGELOG.md).
