# Development handoff: vibration results and follow-up priorities

Task keyword: **CP2KKIT-NEXT**. This is a reference label for this document.

Use English for maintained documentation, code, CLI/TUI messages and tests unless
the user explicitly requests another communication language. Preserve original
scientific keywords, quotations, units, paths and user data.

## Start here

Read [AGENTS.md](../AGENTS.md) and the
[development rules](../.agents/DEVELOPMENT.md), then inspect Git status and the
actual implementation. The bounded **0.4.4 molecular vibrational-result
observation stage** is closed; see the [acceptance record](closeout-0.4.4.md)
and [result contract](vibration-results-contract.md). The original
[implementation prompt](../.agents/prompts/implement-vibration-postprocessing-0.4.4.md)
and delivery steps below are retained as scope and acceptance history. Choose a
bounded follow-up only after reconciling the candidates with the current code.

## Historical 0.4.3 baseline

At handoff preparation, software is **0.4.3** and exchange schema is **0.1.0**.
The bounded vibrational input generator exists; a vibrational-result parser and
the planned application menu grouping do not. See the
[0.4.3 closeout](closeout-0.4.3.md) for historical acceptance evidence.

Existing working changes include the 0.4.4 implementation prompt, its index entry,
and roadmap/menu planning. Preserve these and unrelated user work. Historical
test counts and native checks are evidence of earlier stages, not current results.

## Original delivery plan: 0.4.4

1. Establish supported CP2K 2026.2 frequency-block formatting from tagged native
   source/manual and available existing output. Record headings, units, printed
   mode identities, block boundaries and completeness evidence before choosing
   parsing rules. Do not infer mode counts or scientific validity from a filename.
2. Implement one shared read-only parser/report/writer path. Preserve signed
   frequencies in cm^-1, source hashes, line evidence, observed order, incomplete
   records and explicit segment/block selection. Keep the raw negative count
   separate from threshold-dependent categories; the reporting threshold does
   not modify frequencies or establish numerical convergence.
3. Expose the same results through Python, the planned batch vibration command,
   and TUI. Keep the result implementation distinct from input-generation policy
   in `vibration.py`. Follow the final public contract rather than treating the
   proposed signatures in the implementation prompt as existing APIs.
4. Apply the [menu migration](menu-numbering-draft.md#application-workflow-layout-044):
   retain main 1-4, group output analysis at 5 and CUBE analysis at 6, and put
   vibration at 7. Old main-7 subtraction moves to 6/2. Preserve structure state,
   cancellation, terminal behavior and existing batch commands.
5. Complete the public result contract, deterministic JSON/CSV, opt-in exclusive
   file export, error/ambiguity behavior and relevant executable examples/tests.
   Preserve existing GEO_OPT observation meanings and source protection.
6. Run the focused and regression checks required by the implementation prompt
   with verified available interpreters. Report actual outcomes, skips and limits.
   Update software to the assigned 0.4.4 once; assess schema compatibility
   independently. Formal package builds remain deferred to the planned 0.5 stage.

The implementation prompt contains the full acceptance matrix, including malformed
numbers, partial/repeated blocks, strict reporting, file collisions and PTY cases.
Finish those applicable checks before reporting the stage complete. Reading a
frequency block, observing an end marker, and establishing a stationary point
remain separate conclusions.

## Original roadmap maintenance scope

Update the [roadmap](roadmap.md) to match the delivered state. Keep current status,
the next bounded milestone and future candidates visibly separate. In particular:

- Reconcile the old status table's deferred plane-average wording with the
  implemented 0.4.0 native-grid profiles.
- Distinguish existing bounded RI-HFX and vibrational input support from broader
  combinations and tasks that remain deferred.
- Preserve historical closeout counts, failed candidates and provenance. Link
  historical records rather than silently rewriting them as current acceptance.
- Retain full Multiwfn generator coverage as a long-term goal. Order subsequent
  increments by useful research workflows and their evidence requirements.

Keep this documentation update proportional; a repository-wide documentation
reorganization is not a prerequisite for completing 0.4.4.

## Follow-up candidates, not additional 0.4.4 implementation

| Priority | Candidate | Required boundary before implementation |
|---|---|---|
| Next | Representative native-format fixtures and compatibility matrix | Separate synthetic tests, format evidence, actual execution and numerical/scientific validation. Use small distributable examples with provenance. |
| Next | Energy/structure/frequency association | Define evidenced step/frame/run relationships and unknown/ambiguous states. Preserve last-observed energy semantics; do not infer final structures from filenames or the last frame. |
| Toward 0.5 | Delivery readiness | Propose a current support matrix, lightweight CI, install/package checks and compatibility/distribution boundaries. These are readiness recommendations, not authorization to publish. |
| Separate track | Read-only Agent/MCP adapter | Reuse stable public parsing/quality contracts. Follow AGENT-1 in the roadmap; a complete generator refactor is not its prerequisite. |
| Later molecular workflow | Shermo-related thermochemistry | First inspect official versioned interfaces/formats/terms; define exchange, result import and execution as separate capabilities with independent provenance. |
| Later independent workflows | Periodic phonons, trajectories, MD and reaction paths | Establish each workflow's inputs, normalization, scientific meaning and acceptance separately. Do not expand the molecular frequency parser to imply these capabilities. |

Choose the next bounded task after reporting 0.4.4; do not automatically implement
this candidate table. Incrementally separate generator validation/resolution,
rendering and manifest assembly when a concrete preview/capability consumer needs
it, following ARC-3 in the roadmap. Avoid broad preparatory refactoring.

## Execution boundaries and delivery report

This handoff does not authorize CP2K/Shermo execution, scheduler submissions,
replacement of scientific results, dependency installation, package publication,
Git commits, tags or pushes. Use existing outputs read-only and disposable test
artifacts; retain unknown evidence as unknown. Do not add consumer-specific
databases, private fixtures or workflow-engine dependencies.

Report changed paths, actual API/CLI/menu usage, contract and migration impacts,
representative synthetic results, checks actually run and remaining gaps. Distinguish
completed work from follow-up proposals. Do not claim native/scientific validation
or downstream integration from producer tests.
