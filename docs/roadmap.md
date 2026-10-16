# Development status and next steps

Current software: **0.2.5**, explicitly requested; schema: **0.1.0**.
See [the changelog](../CHANGELOG.md). This round fixes BUG-1 ENERGY numeric-token
boundaries, implements ARC-4 shared structure recognition, CLI-1 tested menu/batch
routing, and ARC-1 shared protected structure export. Whitespace-delimited energy
annotations are accepted without prefix-parsing adjacent garbage. Evidence/hashes,
conservative quality rules, batch contracts and output protection are retained.

The scrolling grouped application menu and single numbered editor introduced in
0.2.4 remain. No alternate screen, redraw or full-screen framework is used. Applicable
fields have fixed numbers, and hidden values remain without implicit resets. Source/
frame controls stay in the header; 0 reviews/generates with confirmation, -10 returns.
Slots 124/125 retain explicit Ueff/L and collinear initial moments for target 2026.2,
including split same-element KIND labels. U values, charge/multiplicity and scientific
defaults are not inferred or changed. No U-value dictionary is implemented.

Current validation: **193 tests passed, none skipped**; compileall, diff, CLI version,
and local Markdown-link checks passed. Added 17 test methods cover ENERGY whitespace/
annotations/malformed tokens, registry aliases, CLI routing, direct CLI/menu export
byte equality, cell-loss permissions, collisions, failure and interrupt rollback.
Existing PTY/navigation/generation/CUBE/plain/fallback regression remains passing.
No dependencies were installed and no calculations, submissions or package publication
were performed in this 0.2.5 work round. Runtime/scientific certification and real-file
version coverage remain unverified.

## Recent historical validation

- **0.2.4:** 176 tests passed, none skipped. Added scrolling menus, optional Rich
  styling/plain fallback, conditional settings and explicit Ueff/initial magnetism.
  Rich 15.0.0 import/render was verified in the existing environment; ui declares
  rich>=13.7. No real CP2K execution/scientific certification was performed.
- **0.2.3:** 138 tests passed, none skipped. Standardized maintained documentation,
  prompts and project text in English; preserved original quotations/hashes and
  consolidated the standalone MVP into this roadmap. No scientific/default changes.
- **0.2.2:** 134 tests passed, none skipped. Application/editor/submenu text became
  English; numbering/defaults and 0.2.1 formatting stayed intact. Compileall/diff
  checks passed; CLI reported 0.2.2. CP2K was not run.
- **0.2.1:** 132 tests passed. Fixed EPS notation and eight-decimal CELL/COORD;
  generated JSON matches rounded text, originals retain precision, thresholds unchanged.
- **0.2.0:** 128 tests passed. Added package/module/README/changelog/CLI/generator
  version-consistency tests.

All earlier counts below are historical, not current test totals.
The original estimate remains 22 person-days within a 25-person-day budget.
A runnable preliminary implementation **does not equal complete production acceptance**.

## Status

| Feature | Current state | Remaining validation |
|---|---|---|
| CLI/discovery | Implemented, synthetic regression | Real naming patterns, large-file performance |
| Output parser | Common-marker subset | Actual CP2K version matrix/run types |
| Structure export | Strict text subset | Real restart/extXYZ and more legal syntax |
| Quality reports | Conservative evidence rules | Real convergence/failure text and geometry thresholds |
| CSV/JSON | Versions/units/hashes/evidence | Schema freeze and user feedback |
| Plots | Segmented energies/SCF counts | Real restart paths; residual/gradient plots if needed |
| Input generation | GPW/density cubes/CLI/TUI implemented, incomplete | Full Multiwfn generation coverage is the goal; syntax checks through 2026.2, real execution still needed |
| Cube validation/difference | Streaming scalars, strict grids, multi-fragment subtraction/provenance | Real cubes, integration/sampling error; plane averages later |

## Initial implementation validation record

- Python 3.12.14, Matplotlib 3.11.1; no new dependencies installed.
- 41 unittest tests passed, including plotting; no skips.
- Compileall passed for source/tests.
- Subprocess CLI checks passed: help/version/discovery, JSON/CSV, strict report,
  extXYZ, energy/SCF PNG, hashes, overwrite protection.
- CP2K was not run; values were synthetic, not calculation results.
- Wheel/editable installation was not verified. At that stage setuptools was not
  installed; build dependencies were declared and validation used PYTHONPATH=src.

## Priorities

1. Add licensed, distributable, anonymized real output/restart fixtures: normal
   single points, SCF failure/truncation, geometry success/max steps/restarts.
2. Check formats per version and build an evidence-based compatibility matrix.
3. Inspect actual TIMER/force/stress/optimization thresholds before extending parsers.
4. Extend strict restart support using real examples; do not ignore physical settings to read more files.
5. Add CI, multiple Python versions, packaging/install/release checks. The owner decides licensing.
6. Assess streaming large output files and schema compatibility.
7. Extend CP2K generation in stages toward full Multiwfn coverage, recording provenance
   and checking versions/parameter combinations.

## Review follow-up backlog

These are deferred review recommendations, not implemented features or fixed dates.
In 0.2.5, BUG-1, ARC-4, CLI-1 and ARC-1 are completed with regression coverage.
Keep future rounds small and independently testable; no mass renaming/refactoring.

| Review ID | Deferred work | Constraints and acceptance boundary |
|---|---|---|
| ROB-1 | Improve unsupported-hard-link diagnostics and filesystem-specific tests | Current temporary files are already beside each target; failure cleans up safely and CLI returns I/O code 2. Prefer a clear supported-filesystem error first. Do not automatically copy to final paths without separately evaluating partial visibility, ownership-aware rollback and no-overwrite semantics. |
| ARC-2 | Clarify field/navigation/editor module responsibilities | Keep public run_interactive compatibility while extracting useful shared pieces. Renaming alone is not a priority; ignored bytecode is not a tracked-source defect. Preserve all menu IDs/navigation. |
| ARC-3 | Separate generator validation/resolution, rendering and manifest assembly | Keep generate_input's public signature and one authoritative CLI/TUI implementation. A validated intermediate state should not require text/manifest construction. Preserve physics, effective settings, text hashes, determinism and exclusive writers; compare old/new outputs before migration. |
| PERF-1 | Stream large output/restart reads and discovery | Preserve full-byte SHA-256, strict UTF-8, evidence line numbers, segmentation and malformed/truncated-record handling. Discovery must scan the whole file for multiple project names, not inspect only the header. Retain read_text for full-text consumers. |
| MNT-1 | Consider smaller CubeReader header/interpretation units when needed | Preserve bounded streaming, explicit unit/meaning assertions and source identity checks. Exhaustive semantics tests should precede extraction; no inference from magnitudes/charges. |
| MNT-2 | Share only truly common numeric conversion primitives | structure_formats already reuses structure.floats. Preserve context-specific errors, integer rules, Fortran exponents, finite checks and CIF uncertainty handling; avoid a permissive universal parser. |
| MNT-3 | Revisit structured settings/models only when semantic consumers require them | Intentionally defer dataclass/settings redesign. Keep original strings/evidence and null distinct from zero; do not normalize or merge physical settings implicitly. |
| PKG-1 | Add lightweight CI, optional lint/type checks and packaging metadata/checks | Keep unittest/compileall, standard-library core and optional Rich/plotting isolation. Add only verified links/authorship; the owner decides licensing and unresolved upstream terms remain explicit. No package release is implied. |
| TEST-1 | Expand bounded/property-style edge-case matrices incrementally | Use unittest loops/deterministic cases without new mandatory dependencies. Extend filesystem errors, parser segmentation and generator combinations; build on existing collision/race/inode-aware rollback tests rather than claiming these are absent. |

Hard-link portability is a compatibility enhancement, not evidence that current
rollback overwrites files. Refactoring is not automatically low-risk where physical
settings, provenance, or write safety are involved. No plugin/configuration engine,
mandatory UI dependency, relaxed quality rule or parallel CLI/TUI generator is planned.

## Input generation: incomplete by design

**Goal: cover all Multiwfn CP2K input-generation functionality.** Current generation
is a GPW subset with electron/applicable spin density, not a completed full port.
The initial baseline is user-provided Multiwfn 2026.10.1 cp2kmate.f90.
Record versions/hashes/new or changed branches for subsequent references.
The goal is useful capability coverage, not line-by-line copying, preserving every
old default, or emitting target-version-unsupported keywords without checking.

### Staged extensions

1. **Defaults/behavior:** verify differences, solvers, WAVELET box shapes, low-dimensional
   vacuum, centering, cell repetition, external structures, configuration.
2. **KIND/spin/constraints:** explicit element/atom magnetic guesses and Ueff/L
   are implemented for target 2026.2. Remaining: arbitrary independent KIND/basis/
   potential controls, richer +U projectors/occupations, CDFT, atom freezing,
   cell constraints, anisotropic pressure, and actual magnetic-state validation.
3. **Methods/bases:** GGA/meta-GGA, hybrids, ADMM/RI-HFX, GPW/GAPW, auxiliary/all-electron
   bases, correlated wavefunctions, semiempirical/force fields, dispersion/SCF options.
4. **Tasks:** frequencies/vibrations/Raman, MD, dimer TS, BAND/NEB, NMR, polarizability,
   BSSE, real-time electrons, PIMD, XAS, appropriate TDDFT.
5. **Environment/outputs:** SCCS, fields, surface dipole correction, trajectory/restart
   printing, cube/Molden, charges, orbitals/matrices, cutoff/k-point convergence templates.

### Acceptance and provenance

- Track upstream options/branches as implemented, partial, missing, or version-inapplicable.
- Register source/version/file/subroutine/hash, usage/differences/citations/permission
  for each module in [provenance](../third_party/multiwfn/PROVENANCE.md).
- Diagnose incompatible combinations without silently repairing physics.
- Add synthetic tests, representative input comparisons, and authorized actual execution
  per stage. Syntax acceptance is not scientific appropriateness.
- Preserve complete input/settings/units/source/protection. Never run/submit automatically.
- Full coverage is a goal, not completion, extra permission, or certification.
  Check terms and licenses before publication/relicensing/paid distribution.

### Initial GPW subset validation

See [input-generation scope](input-generation.md). Added generation without changing
analysis. Tests covered defaults/tasks/section balance/geometry/PBC/spin/electrons/
dispersion/SCF/k-points/local data headers/hashes/CLI/protection.

- 58 tests passed (41 previous + 17 generator tests), none skipped.
- Compileall/diff checks passed.
- Subprocess checks covered all four tasks, JSON/input hashes/citations, collision refusal, help.
- No new dependencies or CP2K execution; synthetic numbers were not scientific results.
- Terms/provenance/papers recorded in [notices](../THIRD_PARTY_NOTICES.md), not evidence
  of separate permission or settled relicensing boundaries.

Actual CP2K syntax execution and system-specific convergence remain necessary.

## Completed stage: density cubes and subtraction

- Added electron/applicable UKS spin switches, three-direction STRIDE, final-step policy.
- Syntax checks through **2026.2**, default target 2026.2; tagged definitions inspected
  for 2024.1/2/3, 2025.1/2, 2026.1/2, without whole-program certification.
- Added bounded streaming cube-check/cube-diff, unit/meaning evidence, nonorthogonal
  integrals, normalized-grid tolerance, multiple fragments, staged exclusive publication/rollback.
- Unknown scalars are not electron counts; atom fields do not imply valence counts;
  electron/spin differences remain separate and integrals are not fragment net transfer.
- Scope excludes Bader/interpolation/registration/plane averaging/DOS/bands/submission.
  Plane averaging awaits an explicit separate request.
- Retained 58 tests and added independent hand-derived density/cube cases:
  **92 passed**, no skips; compile/diff/local-link checks passed.
- Subprocess checks covered four task outputs, AB/A/B check/subtract/reread, hashes,
  protection/help. Streaming smoke: 120000 constant samples (~2.78 MB), Python
  tracemalloc peak ~11.4 KB for that case only, not a general performance guarantee.
- No new dependencies or CP2K installation/execution. No usable real cubes in tests/
  authorized test-workspace at implementation time; no real-cube regression.
  Official source checks and synthetic evidence remain distinct.
- Details in [cube guide](cube.md)/[schema](schema.md); Multiwfn references recorded.

## Completed stage: input editor

- Retained parameter CLI; added --tui/--interactive, seeded by arguments.
  Bare generation in a terminal can open the editor; non-TTY scripts stay noninteractive.
- Standard-library editor covers all InputSettings with grouped revisits, units,
  complete previews, quoted replay commands, default-no confirmation.
- Local range/type vs shared scientific validation; invalid drafts remain editable
  without automatic charge/spin/SCF/PBC/k-point changes.
- Existing writer/manifest/schema/protection reused; no shell/CP2K/Multiwfn execution.
  UI references registered separately, not a full upstream-menu port.
- Added 19 tests: **111 passed**, none skipped. Covered mode equivalence, seeds/edits,
  previews/cancel, conflicts/manual fixes, collisions, EOF/Ctrl-C, non-TTY refusal,
  actual POSIX PTY subprocess sessions. Compile/diff/link checks passed.
- No new dependencies or actual CP2K certification.

## Completed stage: application menu and structure formats

- Bare/path invocations open the application menu; select current-directory files
  or paths. Generate/cancel returns to it. Batch commands retained.
- Strict standard-library GJF/COM, CIF (explicit symmetry/P1), VASP5 POSCAR/CONTCAR;
  reject occupancy/disorder/incomplete/unsupported data. Record constraints/source
  without inheriting calculation settings.
- PROJECT from filename; 400/55 Ry; OT 25/20, diag 128; automatic smearing empty
  orbitals max(30,NINT(natoms/2)), override allowed; explicit UKS spin values.
- Pressure only CELL_OPT, padding only NONE, OT hides/rejects smearing/nonzero empty orbitals.
- **125 tests passed**, none skipped; compile/diff passed. Real POSIX PTY smoke:
  load CIF -> generate -> application menu -> exit.
- No new dependencies or CP2K/Multiwfn runs; no convergence/runtime certification.
  Format restrictions/provenance updated.

Deferred Bader/multi-directory/NEB-DOS post-processing/submission remain outside scope.
BAND/NEB goals above concern input generation only, not post-processing/submission systems.

## Original MVP planning baseline

This historical section replaces the retired standalone early-development document;
it is not the current feature list. Goal: connect result reading and traceable analysis.
Weights were user value 40, frequency 20, foundations/enabling value 15, ease 25.
Six selected modules totaled 22 person-days against 25 budgeted. Estimates excluded
learning/waiting/review; prerequisite closure was complete.

| Feature | Priority | Difficulty | Days | Prerequisite |
|---|---:|---:|---:|---|
| CLI/project discovery | 87 | 2/5 | 3 | None |
| Output parser | 90 | 3/5 | 6 | CLI/discovery |
| Structure/cell export | 92 | 2/5 | 4 | CLI/discovery |
| Convergence/quality | 92 | 2/5 | 3 | Parser |
| CSV/JSON/provenance | 87 | 2/5 | 3 | Parser |
| Energy/convergence plots | 77 | 2/5 | 3 | Parser and exports |

Original acceptance/dependencies:
- CLI: deterministic valid/missing/multiple-project handling, help/exit codes; Python/filesystem.
- Parser: normal/truncated/unconverged regression, units/source/defined compatibility;
  Python and actual CP2K output examples.
- Structures: matching counts/coordinates/cells, explicit unknown XYZ PBC, no silent
  cell loss; restart/XYZ and optional ASE were initial candidates (ASE is not required now).
- Quality: separate electronic/geometry assessment, no success for unfinished jobs,
  evidence links; rules/parser.
- Exports: versioned schema, units, missing vs zero, deterministic repeated results;
  standard library.
- Plots: explicit axes/units, correct restart/reset handling, matching exported data;
  Matplotlib.

Initially deferred: multi-directory summaries, cube checks, Multiwfn batches/logs,
Bader/transfer, density differences, plane averages/cumulative integrals, PDOS,
bands, adsorption/reaction tables, AIMD thermodynamics/trajectories, RDF/MSD/coordination,
orbital/real-space entry points, analysis input fragments, reproducible reports.
Some later additions are documented above; the original deferral is not current status.

Original boundaries: independent CP2K/Multiwfn installations, evidence-based version
claims, units/settings/source on every result, no invalid data promoted to science,
physicochemical judgment not replaced by automation, read-only analysis/no auto-submission.
