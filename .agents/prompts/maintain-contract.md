# Prompt: maintain a public consumer contract

Copy this prompt and replace the placeholders. This is task guidance, not a
registered CLI/slash command or permission to change public interfaces.

---

Read `.agents/DEVELOPMENT.md`, `docs/contracts.md`, and the affected feature,
schema, implementation, callers, tests and fixture provenance first.
Use English for maintained development text and reports unless the user explicitly
requests another language. Preserve original quotations, citations, scientific
syntax, paths and user data. Current implementation and explicit scope win over
older descriptions; do not turn a desired interface into a documented fact.

Feature/change: <actual feature or externally visible behavior change>
Public surfaces: <Python calls, CLI, configuration/replay, output files/fields>
Compatibility target: <existing producer baseline; not assumed consumer integration>
User-specified software version: <version or existing version rules>

Requirements:

1. Decide whether a contract change is needed. Internal refactoring with unchanged
   public behavior may need only regression evidence. A parameter/default/unit,
   scope/rejection, output meaning, error or filesystem change requires assessment.
   Summarize affected callers and the smallest useful contract update.
2. Reuse the existing contract/schema/feature rules. Add a focused contract only
   for a genuinely useful new boundary; add an index link rather than duplicate
   every scientific rule. Do not create a new JSON envelope, schema version,
   capabilities endpoint or contract framework merely to satisfy a checklist.
3. Verify actual request/response signatures, types, units, defaults, auto versus
   explicit origins, index bases, optional/absent/null/zero/false distinctions,
   provenance and independent validation states. Distinguish normalized settings
   from original requests and generation metadata from observed results.
4. State supported/rejected scope, exceptions/CLI exit codes, stdout/stderr and
   file destinations, overwrite/source protection, staging/rollback limitations,
   determinism and replay prerequisites. Inspect code before promising behavior;
   describe known limitations instead of inventing stronger validation/atomicity.
5. Assess compatibility explicitly. Output-reader tolerance does not imply unknown
   request keys are accepted. Separate software/schema/target/runtime identities;
   optional output additions do not automatically require a schema bump. Renames,
   removals or changed meanings need an explicit version/migration decision.
   Document defaults/replay/rejection changes even when the JSON shape is stable.
6. Add a tiny public synthetic example and selected-field expectations only when
   they improve reproducibility. Label provenance and validation limits; compute
   actual source/input hashes during tests, not fabricated portable identities.
   Do not snapshot every path, warning, timestamp or generated field. Preserve
   room for additive output keys and independently check scalar types/absence.
7. Add the smallest meaningful executable checks through public interfaces:
   success and error cases, API/CLI/config/replay agreement where present, units,
   provenance, source immutability and applicable file protection. Reuse existing
   tests for covered scientific gates; do not duplicate validators in tests or UI.
   Verify example inclusion rules if new fixture formats affect packaging; do
   not build/install packages without separate task authorization.
8. Keep the producer independent of consumers such as chemops: no private models,
   database keys, credentials, adjacent repos or consumer-specific dependencies.
   Consumer adapter compatibility tests belong downstream. Producer contract
   tests do not prove an external adapter is integrated or that CP2K is accurate.
9. Run focused tests, regression and applicable text/version checks. Record actual
   outcomes and untested limitations. Keep machine-specific diagnostics, real
   calculation records and personal paths in ignored local notes or outside Git.
   Update feature docs/index/changelog and version documentation once; do not
   rewrite historical acceptance counts or claim a published/immutable baseline.

No scientific execution, scheduler submission, dependency installation,
commit/tag/push or publication is authorized by maintaining a contract.
Report changed surfaces, compatibility decision, paths, actual checks and gaps.

---

Related: [development rules](../DEVELOPMENT.md),
[public contracts](../../docs/contracts.md), [schema](../../docs/schema.md),
[feature prompt](implement-feature.md),
[version/documentation prompt](update-version-docs.md).
