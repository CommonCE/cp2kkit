# Development status and next steps

Current software: **0.2.9**; schema: **0.1.0**.

### 0.2.9 implemented development scope

- Menu layout v1: compact common shortcuts, unexpanded categories 100-600,
  full IDs for category/direct access, shared semantic state/applicability/editors
  and return context. 500 is output, 600 properties; empty/future menus are hidden.
- Explicit extension-number migration, e.g. old 112 ADDED_MOS -> 341, new 112 U.
  Existing CLI/config/replay names and immutable basis registry v1 are unchanged.
- 602: shared ENERGY GPW whole/A/B density inputs and atom-map CSV; explicit
  fragment charges/spins, charge-conserving complementary partition, original
  relative order and common generated geometry/grid controls. Map magnetic seeds,
  filter per-element requests to included atoms, verify basis/potential sources.
- Exclusive staged bundle publication and optional combined JSON; no existing
  target replacement. Ordinary single-input writer policy remains unchanged.
- Generator-main 0 validates/writes directly; w reviews and confirms. Category/602
  0 returns without writing; successful generation returns without an extra pause.
- Whole-system multiplicity defaults to electron parity after charge (even 1,
  odd 2); explicit values are preserved and fragment states remain explicit.
  This is not a ground-state spin prediction.
- Shared -3/601 cube selector (0 None / 1 Electron density); CDD enables density
  output and blocks disabling it while active. 602 option 4 edits six whole/A/B
  state integers transactionally; option 2 prompts directly for atom indices.
- Automatic TUI output naming follows the source stem with -CDD.inp while CDD is
  active, .inp otherwise; explicit paths win. Default UZH runtime references use
  BASIS_MOLOPT_UZH / POTENTIAL_UZH while provenance retains resolved sources.
- [Numbering/allocation guide](menu-numbering-draft.md) distinguishes this
  implemented subset from provisional unimplemented electronic/property models
  and categories 700-1000. [Workflow guide](input-generation.md) records limitations.
- Latest validation: **403 tests passed, none skipped**, including menu/workflow
  tests, migrated UI regressions and follow-up parity/cube/naming/navigation cases;
  compileall, CLI version, maintained-text/link and diff checks passed. Synthetic
  generation and PTY/CLI smoke only.
- Actual CUBE grids, CP2K native acceptance/convergence and scientific reference
  fitness remain unverified. No calculations, new dependencies, commit/push or
  publication authorized by input generation.

### 0.2.8 implementation (historical baseline)

Latest retained-version policy supersedes the historical universal grid/OT/hint
defaults below: only effective classic non-SR TZVP/TZV2P/TZV2PX emit NGRIDS 5;
all others omit it (null metadata). OT always emits PP STRICT / AE IRAC in both
legacy AE profiles; explicit overrides win. Numerical profile v4 retains native
GAPW controls. SCF wavefunction and MOTION restart backups are explicitly zero,
without disabling writing. Only generator/Multiwfn opening comments remain;
restart suggestions are metadata/review only, not enabled or emitted directives.
EPS_SCF now defaults to 1e-6 for every task, including ENERGY (previously 5e-6).
Explicit overrides still win; task-dependent EPS_DEFAULT remains unchanged.
Optimization menu 9 / --fixed-atoms adds explicit 1-based fixed-atom selections,
including ranges, with default off. Shared CLI/menu/config/replay handling writes
fractional XYZ constraints only for GEO_OPT/CELL_OPT and target 2026.2. Atom/frame/
expanded-CIF order is explicit; source changes warn without identity remapping.
Malformed/overlapping/active out-of-bounds selections fail before publication;
inactive requests remain compact and hidden. No source constraints are inherited.
CELL_OPT can move fixed fractional positions with the cell. Existing defaults,
protected-result writes and native-validation boundaries are retained.
Historical 0.2.8 validation: **346 tests passed, none skipped**, including 22 fixed-atom
methods and nine latest-policy regressions; compileall, CLI version, documentation links/text and diff checks passed.
No calculations, submissions, new dependencies, publication, commit or push in this round.

### 0.2.7 implementation (historical)

Version 0.2.7 was retained by explicit request, including the D3 filename fix; schema 0.1.0.
D3/D3(BJ) PARAMETER_FILE_NAME now uses literal whole-line serialization instead
of quoted-token output; the input-writing follow-up extends it to basis/potential
filenames. Default output is input-only, JSON is opt-in (132/--write-json).
Existing regular .inp may be atomically replaced; sources/data/symlinks, optional
JSON and all other results remain protected. This fixes
the statically identified blank-prefix path, without claiming native execution.
Historical validation: **315 tests passed, none skipped**, including 22 AE/OT tests,
five filename regressions, 17 input-writing tests and 17 restart/motion tests;
compileall, CLI version, documentation links/text and diff checks passed. All 10
local reference hashes matched in the preceding audit. Default PP physics still
keeps the old method/charge/spin/cutoffs, with an explicitly changed NGRIDS=5;
bytes differ by grid count, basis/potential filename quote removal and inactive
restart hints replacing explicit SCF_GUESS ATOMIC. The isolated-O regression
restores only those known text changes for the historical SHA-256 comparison.
Optimizations now use BFGS/LBFGS TRUST_RADIUS 0.2 angstrom (133), selectable
PDB/XYZ/EXTXYZ trajectories (-5, XYZ default), and MOTION restart backups=0
without disabling restart writing. EXTXYZ is checked only for target 2026.2;
CG hides/retains the radius but never emits it. PROJECT-based restart hints use
.wfn for Gamma, .kp otherwise. Multiwfn's explicit NGRIDS 5 branch applies only
to ibas 3/4/5; the local universal five-grid policy remains a separate user request.
No CP2K/Multiwfn execution, new dependencies, publication, commit or push.
AE choices 50-59 derive GAPW/ALL, core-inclusive electron counts, a disclosed
basis-aware pob IRAC. Numerical profile v3 leaves GAPW split tolerances and
atomic grids to CP2K defaults (no five extra lines); NGRIDS=5 is universal for
PP/AE and SR/non-SR bases. Old profile inputs are not rewritten. OT-only main-menu 110
selects IRAC/STRICT (explicit overrides win); AE-only 131 selects auto/native.
No physical-state repair or native-execution/convergence certification.
Read-only local-data checks cover 332 AE basis/nuclear-potential pairs; local
REVISION git:c92cc08 is not assumed equivalent to upstream v2026.2.
Remaining AE work includes heavy-element/ECP/relativistic protocols, mixed AE/PP,
GAPW density reconstruction/charge analysis, +U and cell/stress/k-point validation.

### Registry follow-up (historical 0.2.6)

Software 0.2.6 was explicitly retained for that round; schema was 0.1.0.
The [registry-v1 basis follow-up](basis-selection.md) adds permanent allocated
numbers, stable string settings/replay IDs, explicit legacy-position migration,
SZV non-SR, paired UZH-PBE DZVP/TZVP/TZV2P, custom pseudopotential ORB 900,
actual alias/payload/q/source checks, cross-KIND shadowing/ambiguity rejection and
per-KIND origin/version metadata. PBE0 IDs 30-32 remain unavailable: no hybrid
method template; reserved/auxiliary/all-electron families are not selectable.
The 71-element fixed-valence policy, charge/spin/U, 400/55 Ry and protected writes
are unchanged. No data yields an explicitly unverified template, not runnable
certification. Software 0.2.6 alone does not distinguish legacy and registry menus;
registry_version=1 does. Analysis/CSV contracts remain unchanged.

Current validation: **254 tests passed, none skipped**, including 38 new registry
methods; compileall, diff, CLI version and local documentation tests passed.
Actual pinned CP2K v2026.2 data were parsed read-only for **213 UZH-PBE pairs**
(3 families x 71 preset elements), with full source hashes and selected-entry/q
checks. This is real-data parsing, **not CP2K execution**. A default synthetic-O
input hash matches the earlier generator at commit 229d09d. No dependencies,
calculations, submissions, package publication, commit or push were performed.

### Initial 0.2.6 GGA/profile round (historical)

See [the changelog](../CHANGELOG.md). That round added native PBEsol/revPBE and Libxc
RPBE, TZVP/TZV2P short-range and TZV2PX MOLOPT families, and explicit element basis
overrides. Tagged v2026.2 header catalogs select actual basis files and fixed-q
potentials. Matched potentials are preferred; unmatched GTH-PBE approximations need
explicit approval. RPBE requires a user target-build Libxc assertion, not probing.
New requests are gated to target 2026.2, not runtime/scientific certification.

The scrolling grouped application menu and single numbered editor introduced in
0.2.4 remain. No alternate screen, redraw or full-screen framework is used. Applicable
fields have fixed numbers, and hidden values remain without implicit resets. Source/
frame controls stay in the header; 0 reviews/generates with confirmation, -10 returns.
Slots 124/125 retain explicit Ueff/L and collinear initial moments for target 2026.2,
including split same-element KIND labels. U values, charge/multiplicity and scientific
defaults are not inferred or changed. No U-value dictionary is implemented.
Menu 128 edits element basis overrides, 129 approves a potential approximation,
and 130 asserts Libxc availability; 129/130 follow functional applicability without
resetting values. New UCL triple-zeta SR families cover 54 current elements and lack
H/C/N/O. Mixed bases must be explicit; q values and source files are never rewritten.
Multiple libraries are checked/hashed separately. Schema 0.1.0 gets additive method,
file-identity and reference metadata; default PBE/DZVP-SR/400-55 Ry is unchanged.

Initial profile-round validation: **216 tests passed, none skipped**; compileall, diff, CLI version,
and local Markdown-link checks passed. Added 23 profile test methods cover fixed-q
family availability, XC definitions, approval/build assertions, actual potential
identities, multi-file name/hash checks, malformed API maps, combined RPBE/+U/AFM/
mixed bases, CLI replay and menu edit/clear/hidden flags. All legacy parser, export,
PTY/navigation, generation, CUBE and collision/rollback tests remain passing.
No Python dependencies were installed; no calculations, submissions or package
publication were performed. RPBE's target CP2K Libxc requirement is not detected or
installed by cp2kkit. Runtime/scientific validation remains pending.

## Recent historical validation

- **0.2.5:** 193 tests passed, none skipped. Fixed ENERGY token boundaries and
  completed ARC-4 shared format recognition, CLI-1 menu routing, ARC-1 shared
  protected export. Remaining architecture review items were explicitly deferred.
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

## UZH protocol follow-up: modc.py reference

The original 0.2.6 planning below is retained for provenance. The registry-v1
follow-up now implements paired UZH-PBE selections, audited over all 71 current
preset elements; UZH-PBE0/hybrid templates remain unimplemented. See
[basis selection](basis-selection.md) for current scope and permanent numbers. User-provided `test-workspace/modc.py` was inspected read-only (SHA-256
`b37f4c2cb1b7051f6fd4d3a19cd00dbb511f9aca355e0fb936f3d033362e7dbd`),
not executed, copied, modified or committed. No redistribution authorization for
that user script is inferred. It demonstrates preserving q while selecting UZH
basis/potential libraries, but string renaming alone is not protocol verification.

Confirmed tagged v2026.2 header examples include H/C/O/Fe
TZVP-MOLOPT-PBE-GTH-q1/q4/q6/q16 and TZV2P equivalents with corresponding
POTENTIAL_UZH GTH-PBE aliases. This is representative header evidence, not complete
coverage or CP2K execution. Future protocol implementation must audit every enabled
pair and retain library identity even when aliases match an older library.

- [BASIS_MOLOPT_UZH_2026.2](https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/BASIS_MOLOPT_UZH_2026.2),
  SHA-256 `8ca617142cc73b02e47d5806d97e91d2c3312444c411c5a093f4dfe8fb9355c4`.
- [POTENTIAL_UZH_2026.2](https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/POTENTIAL_UZH_2026.2),
  SHA-256 `8ab49093391f67f2705679f0b3bfc5b84bbeb4003955b556ded322e9d1d6093d`.

Do not port the script's in-place overwrite default, forced EPS_SCF/cutoff resets,
order-dependent KIND rewriting or substring replacements. In particular, switching
BASIS_MOLOPT without reliably replacing GTH_POTENTIALS can mix protocols, and a
BASIS_MOLOPT prefix substitution can produce an invalid UZH_UCL filename. Quoted
paths, units, numeric exponents and basis roles require structured handling.
A future UZH feature should be an explicit paired profile in the protected generator,
not a general overwrite-based regex migration. r2SCAN and hybrids/HF/ADMM remain
separate later stages; arbitrary q changes require their own charge/spin review.

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
3. **Methods/bases:** 0.2.6 adds PBEsol/revPBE/RPBE and explicit catalog-backed
   MOLOPT/UCL mixed bases; the registry follow-up adds UZH-PBE pairs and custom ORB.
   Remaining: r2SCAN/meta-GGAs, native/scientific UZH validation, UZH-PBE0,
   hybrids/HF/ADMM/RI-HFX, GPW/GAPW, auxiliary/all-electron bases, additional families/
   q policies, correlated wavefunctions, semiempirical/force fields and SCF options.
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
