# cp2kkit development rules

You are the coding assistant for this project. Use English for development by default:
documentation headings and prose, prompts, code comments/docstrings, identifiers,
user-facing messages, commit messages, and development reports. Follow an explicit
user request for another communication language. Preserve original third-party
quotations, citations, scientific keywords, file paths, and user data verbatim.
Distinguish verified facts, unverified items, and planned work. Read the relevant
implementation before changing it; do not guess interfaces, scientific keywords, or formats.

## 1. Starting a task

Read the materials relevant to the task:

- [README](../README.md) and [project configuration](../pyproject.toml).
- [Architecture](../docs/architecture.md) and [roadmap](../docs/roadmap.md).
- [Schema](../docs/schema.md) for data exchange; [input generation](../docs/input-generation.md)
  for input generation.
- [Third-party notices](../THIRD_PARTY_NOTICES.md), [Multiwfn terms](../third_party/multiwfn/TERMS.md),
  and [provenance](../third_party/multiwfn/PROVENANCE.md) for third-party references.
- Git status, relevant source, tests, and fixture provenance; identify existing user changes.

The original analysis MVP baseline and later input-generation requirements are
preserved in `docs/roadmap.md`. The current generator is an incomplete GPW/GAPW subset.
Full coverage of Multiwfn's CP2K input generator is a long-term goal, not a completed
port or evidence of validation with the actual software.

## 2. Code and interfaces

- Python >= 3.10, conventional `src/` layout. The core uses the standard library;
  plotting and Rich presentation dependencies are optional.
- Prefer small targeted changes; do not refactor unrelated code, add unnecessary
  dependencies, or create duplicate parsers.
- Reuse `Structure`, `InputSettings`, existing readers/writers, and domain exceptions.
  Check their actual definitions first.
- CLI handles arguments and dispatch only. Parsing, quality assessment, structures,
  input generation, and exports remain separate.
- Preserve exit codes: 0 complete; 2 usage/I/O; 3 ambiguity; 4 parse;
  5 output collision; 6 missing optional dependency; 7 strict quality not passed.
- Update tests and relevant documentation for CLI/API/data-contract changes.
  After each feature round, update the software version and documentation once,
  following the [version/documentation prompt](prompts/update-version-docs.md).
  Use A.B.C: A changes only by the user's explicit decision; features increment B
  and reset C; fixes increment C without changing A/B. Explicit user versions take priority.
  Software and data-schema versions are independent; do not bump the schema merely
  because the software version changed.
- Use the configured Python environment. Check installed/declared dependencies before
  installing only necessary missing packages; do not upgrade unrelated packages.

## 3. Non-destructive operation and evidence

- Analysis is read-only; generation creates new files only and never submits or runs CP2K.
- Do not overwrite/delete sources, data libraries, restart files, outputs,
  wavefunctions, cubes, checkpoints, or other expensive results. Explicit 0.2.7
  permission: input generation alone may replace a regular .inp target (not a
  source/data file or symlink), using staged publication. JSON is opt-in and exclusive.
- Reuse `io.new_file` for exclusive outputs; preserve the shared generator's
  narrowly scoped staged .inp writer. Test collisions
  and rollback for multi-file outputs.
- Do not silently select ambiguous projects or concatenate restarts.
  Sort candidates deterministically; do not guess from modification time.
- Unknown values use null/empty fields, not zero. Preserve actual zero values.
- Record paths, original text/line numbers or source hashes, units, and parameters.
  Keep outputs deterministic and avoid unnecessary timestamps.
- Diagnose partial/truncated files, non-finite values, damaged formats, and unsupported
  syntax explicitly; do not silently skip important evidence.
- Do not commit scientific binaries, large outputs, or sensitive data.

## 4. Scientific settings and validation boundaries

- Check target CP2K version, keywords/nesting/units, method/basis/potential, dispersion,
  spin/charge, periodicity, magnetic state, k-points/SCF, and combinations.
  State important limitations.
- Plain XYZ has unknown periodicity, not NONE. Reading a restart structure does not
  inherit its calculation settings.
- Elements, KIND labels, and magnetic moments have different meanings; do not merge
  or discard them without explanation.
- Do not silently change periodicity, magnetism, constraints, or other physical models
  merely to make generation succeed.
- Coordinates/cells are standardized to angstrom; energies remain hartree.
  Give other parameters explicit units.
- Generation, balanced sections, round-trip reading, syntax acceptance, actual
  convergence, and scientifically correct results are distinct validation levels.
- Synthetic fixtures are not calculations; their version strings do not certify CP2K support.
- Missing completion/convergence evidence cannot become passed. Normal termination
  or a single energy value is not proof of complete convergence.
- Retained 0.2.7 defaults: universal NGRIDS 5; commented PROJECT-based .wfn/.kp
  restart hints; BFGS/LBFGS optimization TRUST_RADIUS 0.2 angstrom; XYZ position
  trajectories and MOTION restart BACKUP_COPIES 0. Keep inactive hints/hidden raw
  settings distinct from emitted controls. Never treat disabled backups as
  disabled restart writing or permission to touch existing wavefunctions.
- Do not start expensive calculations. Actual CP2K validation requires explicit
  authorization and a new run directory.
- For failed-job diagnosis, load `qchem-error-diagnosis`, collect software/version
  and actual failure evidence, then propose changes with reasons.

## 5. Multiwfn references and authorization

- Identify the upstream version/file/subroutine and hash; deployment must not require
  an adjacent source directory.
- Describe reference ideas, parameter tables, rewrites, or direct ports honestly.
  Do not claim unverified clean-room development.
- Multiwfn has custom terms, not MIT/BSD/GPL. Free access, public source, a Python
  rewrite, or citations do not automatically authorize arbitrary relicensing or paid distribution.
- Update `third_party/multiwfn/PROVENANCE.md` for each referenced feature: actual
  source, usage, differences, citations, authorization, and validation boundaries.
  Unknown permission must not be recorded as granted.
- Preserve copyright notices and required papers. Check other authors' code separately.
- Do not assign a project/third-party license without authorization. Record extra
  permission only within the evidenced scope.
- Detailed comparisons belong in the conversation by default. Do not create long
  comparison documents or temporary reports unless requested.

## 6. Testing and delivery

From the project root, run relevant tests first, then regression:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m compileall -q src tests
git diff --check
```

Cover normal, boundary, invalid-combination, damaged-input, provenance/unit,
determinism, and overwrite-protection cases. Add CLI subprocess smoke tests where
needed. Tests must not run quantum-chemistry calculations or alter user results.
Keep maintained text in English and check documentation links after translation.

Report implementation scope, file paths, checks actually run/passed/skipped,
remaining limitations, and unverified items in English unless the user explicitly
requests another language. Do not reuse old test counts as current results.
Commit/push only when explicitly requested. Never force-push, reset, or rewrite
history automatically; preserve existing user changes.
