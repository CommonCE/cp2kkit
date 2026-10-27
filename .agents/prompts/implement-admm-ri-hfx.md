# Implement the Initial Ordinary ADMM + RI-HFX Combination

Work in the cp2kkit repository. Implement Stage 1 below; do not implement ADMMS
or broaden the scientific scope in this session.

Use English for maintained development text unless the user explicitly requests
another communication language. Preserve original quotations, scientific keywords,
paths and user data verbatim.

## Read and establish current state

Read AGENTS.md, `.agents/DEVELOPMENT.md`, the applicable development prompts, and
`docs/admm-ri-hfx-audit.md`. Read the relevant current implementation, tests,
configuration/schema, input-generation documentation and third-party terms and
provenance before editing. Follow project rules for Python environment selection,
test logging, non-destructive output and version/documentation updates.

Inspect `git status` first. Preserve user changes, including the audit and this
prompt if uncommitted. Current source takes precedence over the historical audit.
Recheck its relevant source locators/hashes rather than assume external reference
trees are unchanged. Do not require adjacent Multiwfn sources at runtime.

## Goal and allowed scientific scope

Allow existing ordinary ADMM and RI-HFX together only for:

- CP2K target 2026.2;
- PBE0, GPW, Gamma, PERIODIC NONE;
- closed-shell RKS, OT, ENERGY;
- existing supported classic orbital basis families with actual checked ORB and
  AUX_FIT data, retaining current potential/q and Gaussian payload checks;
- existing BASIS_PROJECTION ADMM and its current purification behavior;
- RI_METRIC HFX, using existing AUTO_BASIS sizes, filtering and batching controls.

Keep all existing independent direct-HFX, ADMM and RI-HFX support unchanged.
Reject combination requests outside this intersection, including CDD bundles,
explicit magnetism/UKS, diagonalization, other tasks/functionals/PBCs and an
independent TRUNCATED RI metric. Do not reject these modes when used independently
if currently supported. Preserve all existing smearing/+U/model/data gates.
Do not silently change user charge, multiplicity, spin, solver, cell, basis,
potential, thresholds or physical operator to fit the scope.

## Key findings to preserve

1. Ordinary ADMM + RI does not require ADMMS. Do not automatically switch variants.
2. CP2K generates RI_HFX from AUX_FIT when ADMM is active, rather than from ORB.
3. Existing ADMM output uses BASIS_PROJECTION, solver-derived purification,
   exchange scaling NONE and correction DEFAULT. Preserve those semantics.
4. ADMMS instead means CHARGE_CONSTRAINED_PROJECTION, NONE purification and MERLOT
   scaling. It is deferred, not an alias to add to the existing block.
5. Source/manual evidence does not certify execution, convergence or accuracy.

## Implementation requirements

- Replace the unconditional ADMM/RI mutual exclusion with a bounded combination
  policy using existing validation abstractions; identify where resolved spin,
  task and PBC are available before choosing validation locations.
- Reuse resolved AUX_FIT records when deriving RI metadata. Record the parent role
  as AUX_FIT in combination mode, with traceability to actual parent data identity.
  Keep ORB parent behavior for independent RI. Do not invent or certify generated
  RI coefficients, basis-pair fitness or runtime basis completeness.
- Preserve HF fraction/operator, ADMM correction, data sources and protections.
  Continue omitting direct-only HF/MEMORY under RI and rejecting incompatible
  retained direct-memory requests.
- Keep CLI, menu 121/122/223, help, warnings, effective review, capabilities,
  configuration and generated-manifest replay consistent. No menu renumbering.
- Reuse existing whole/fragment identity checks; explicitly block combination CDD
  before publishing any files, while preserving independent-mode CDD.
- Do not add dependencies, duplicate parsers, automatic fallback, scheduler calls,
  native execution or unrelated refactors.
- Update relevant maintained docs, schema description, roadmap and third-party
  provenance honestly. Follow the repository version policy once for the feature
  round after inspecting current version; do not hardcode a version from the audit.
  Schema version changes require an actual contract reason, not a software bump.

## Validation

Add focused synthetic tests covering supported generation, correct nesting,
AUX_FIT parent identity, inherited physical settings, no ADMMS emission, resource
handling, invalid combinations, inactive/non-finite controls, configuration and
manifest replay, CLI/TUI entry-order behavior and non-destructive publication.
Preserve regression tests for the three independent acceleration paths and their
CDD behavior. Test unknown or incomplete parent data explicitly.

Select and verify the Python environment using the applicable skill. Run the
smallest relevant tests first and then the required regression checks. Capture
stdout/stderr in fresh log paths and report actual exit statuses. Run
`git diff --check` and verify relevant documentation links. Never reuse old test
counts as current results.

Do not execute CP2K or Multiwfn, submit jobs, overwrite scientific outputs, install
unnecessary dependencies, commit, push or rewrite Git history. Native calculation
validation is a separately authorized future stage.

If evidence reveals a hard incompatibility or a necessary model/API expansion
outside this scope, stop that portion and explain the finding rather than silently
widening the task.

## Delivery

Report changed paths, supported and rejected scope, actual checks and log paths,
compatibility effects, and remaining unverified native/numerical behavior. Clearly
state that synthetic passing tests do not establish CP2K execution or scientific
accuracy. End this development stage before moving on to ADMMS or native runs.
