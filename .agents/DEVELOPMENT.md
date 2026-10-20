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
  for input generation; [menu numbering/allocation](../docs/menu-numbering-draft.md)
  for implemented routing/migration and separately labeled future reservations.
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
  permission: ordinary single-input generation alone may replace a regular .inp
  target (not a source/data file or symlink), using staged publication. JSON is
  opt-in and exclusive. 0.2.9 density bundles require entirely new inputs/maps/JSON;
  reuse exclusive staged publication and roll back only owned inodes, without a
  crash-atomic multi-file transaction claim.
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
- 0.2.9 menu layout v1 uses compact shortcuts plus unexpanded category entrances,
  full IDs for category/direct access, shared applicability and semantic editors.
  Category/602 0 returns without writing. Generator-main 0 validates/publishes
  directly; w reviews and requires explicit y/yes confirmation. Successful generation
  returns immediately, without an extra Enter prompt. Basis registry v1 and atom
  indices remain independent namespaces;
  old 100+ function numbers require explicit migration, never ambiguous aliases.
- Whole-system multiplicity auto resolves from selected PP/AE electron counts
  minus charge: even -> 1, odd -> 2. Preserve explicit values; parity is not a
  ground-state spin prediction. Fragment states remain explicit. TUI -3/601 is
  the shared 0 None / 1 Electron density selector (UKS also prints spin density);
  CDD enables density output and prevents disabling it until CDD is off.
- Default UZH runtime references use BASIS_MOLOPT_UZH / POTENTIAL_UZH; keep
  resolved source paths/hashes separate in provenance and record emitted_data_files.
  Explicit file overrides win; generic aliases must resolve to the intended data.
- 602 density inputs: ENERGY/GPW, complementary nonempty fragments, explicit
  charges/multiplicities and charge conservation/parity. Resolve whole geometry
  once, preserve subsets/cell/PBC, map magnetic seeds explicitly and record CSV
  indices. No ghosts, separate centering, spin inference or automatic execution.
  Lock the whole-system NGRIDS policy across components; actual CUBE grids and
  reference-state fitness still need independent checks before subtraction.
  Local state option 4 updates six integers (whole/A/B charge/multiplicity) together;
  invalid input must not partially update them. Automatic output uses -CDD.inp
  while enabled, follows source changes, and never replaces an explicit path.
- 0.2.8 fixed atoms: optimization menu 9 / --fixed-atoms uses explicit 1-based
  indices/ranges, default off; no source inheritance or identity remapping.
  Bounds precede active expansion; fractional XYZ is not Cartesian pinning
  during CELL_OPT. Hidden requests are retained but never emitted outside optimization.
- Retained 0.2.8 policy: only classic non-SR TZVP/TZV2P/TZV2PX emit NGRIDS 5;
  otherwise omit it (metadata null). OT always explicitly emits PP STRICT / AE
  IRAC, including legacy auto/native names; manual overrides win. SCF and MOTION
  restart BACKUP_COPIES 0 does not disable writing. Keep only generator/Multiwfn
  header comments; restart suggestions are metadata/review only, never uncommented
  into active input. No permission to touch existing wavefunctions is implied.
  BFGS/LBFGS TRUST_RADIUS 0.2 angstrom and XYZ position trajectories are retained.
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
