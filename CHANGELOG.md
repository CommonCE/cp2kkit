# Changelog

Software and data-schema versions are maintained independently.
This file records actual implementation changes, not publication to a package
repository or certification with actual CP2K calculations.

Versions use **A.B.C**: A is decided manually by the user; features increment B
and reset C; fixes increment C with A/B unchanged. A mixed feature/fix round
increments B once. Explicit user version requests take priority.

## 0.2.5

### Parser correctness and shared interface operations

- BUG-1: replace the literal-backslash ENERGY suffix with a complete numeric-token
  boundary. Accept trailing whitespace and whitespace-delimited annotations while
  preserving original evidence lines/hashes. Adjacent garbage, incomplete exponents,
  non-finite values and missing completion/convergence remain rejected or not passed.
  Tests reproduced the old defect before the implementation fix.
- ARC-4: share structure suffix/name aliases, format recognition and reader dispatch
  between structure.py and menu discovery, including case-insensitive POSCAR/CONTCAR.
  Recognition is not content validation; non-XYZ frame restrictions remain unchanged.
- CLI-1: isolate menu_request and derive reserved command names from actual argparse
  registrations. Retain bare/path/--plain behavior; add explicit -- PATH handling for
  option-looking paths. Batch arguments/usage errors still belong to argparse;
  interactive entrypoints still require both stdin and stdout TTY.
- ARC-1: extract export_structure_files into export.py. CLI/menu call the same
  operation and receive paths/warnings directly, without argv round trips or stderr
  parsing. Preserve exact geometry/sidecar content, cell-loss permissions, exclusive
  creation, collision exit codes and multi-file exception rollback.
- Explicit requested version 0.2.5; schema remains 0.1.0. No scientific defaults,
  U-value dictionary, new dependencies, hard-link fallback or calculation execution.
  Remaining review items are planned in docs/roadmap.md, not claimed implemented.
- Validation: 193 tests passed, none skipped; focused boundary/registry/routing/export
  tests, full regression, compileall, diff, version and local-documentation links.
  This is synthetic/software regression, not CP2K runtime/scientific certification.

## 0.2.4

### Scrolling interactive workflow

- Group application actions into Structure/Calculation/Analysis, using continuous
  display numbers and separate stable IDs. Add real formula/atom/cell/angle/PBC
  summaries and full-path details. Unknown periodicity remains Unknown.
- Add independent quality/CUBE check/difference actions. Structure-dependent actions
  can load a file and resume; unsuccessful replacement preserves the prior structure.
- Keep all implemented input options together in one scrolling numbered menu,
  with fixed field numbers, current values, direct edits, compatibility feedback,
  preview/review, and explicit protected writing. Hide pressure outside CELL_OPT,
  padding unless effective PBC is NONE, smearing/empty orbitals for OT, and outer
  SCF for diag. Hidden fields cannot be selected; values are retained and validated.
  Remaining numbers stay fixed. OT review also omits inapplicable occupation fields.
  Remove the intermediate step-based workflow at the user's request; retain 0.2.4
  without an additional version bump.
- Move structure/frame to the header with s/f controls; remove output/project/target
  version from numbered settings. Default output is source-stem.inp; CLI overrides
  remain honored. Align corresponding main-menu IDs to inspected Multiwfn 2026.10.1:
  -7 PBC, -3 density cube, -1 task, 1–4 method/basis/dispersion/SCF, 6 smearing,
  8 k-points, 10 optimizer and 12 pressure. Unsupported upstream entries are omitted;
  remaining local controls use explicit 100+ extension IDs. Generator 0 reviews/
  generates with confirmation; -10 returns. Keep 0.2.4 without a further bump.
- Review includes physical/numerical/output settings, effective basis/potentials,
  source and absolute target paths, warnings, optional full input/replay details.
  Recover from collisions through a new-path prompt without overwriting.
- Add optional Rich ui extra, plain fallback, --plain and NO_COLOR; scrolling folded
  text only, no alternate screen/redraw/clearing. Add textual result statuses and
  distinguish successful parsing from calculation quality.
- Navigation migration: application main 0/q exits; ordinary submenu 0/back returns;
  generator 0 generates with confirmation and -10/back returns; q exits the whole
  session; cancel/Ctrl+C cancels operations; EOF exits cleanly. Parameter zero stays
  valid. Both stdin and stdout must be TTY; redirected menus fail without waiting.
  Use batch subcommands for machine-readable/redirected output.
- Explicit requested version 0.2.4; scientific defaults, batch contracts/exit codes,
  output protection and schema 0.1.0 unchanged. No calculation, publication, or
  CP2K runtime/scientific certification is implied.
- Replace menu 124/125 cell/data controls with actual DFT+U/magnetic initialization.
  Keep --cell/--data-dir CLI/API controls. New opt-in --dft-plus-u/--magnetism flags
  and menu prompts require explicit Ueff/L or UKS/element/atom spin seeds; opposite
  initial moments split same-element KIND labels without reordering geometry.
  Total charge/multiplicity stay unchanged; initial moments are not constraints.
  Ueff uses eV and MULLIKEN projectors, with no guessed U values. New requests are
  restricted to keyword-checked target 2026.2, not runtime-certified. UKS singlets
  also follow spin-density/two-spin empty-orbital rules. Default input text remains
  unchanged; schema 0.1.0 receives additive settings/KIND/reference metadata.
  Keep software 0.2.4 at the user's explicit request.
- Validation: 176 tests passed, none skipped, including a real POSIX PTY menu,
  navigation/state, generation equivalence, conflicts, collisions/rollback,
  independent export/CUBE/quality actions, plain/NO_COLOR/fallback, batch regression,
  and narrow layouts. Compileall, diff, version and local-link checks passed.

## 0.2.3

### English project content

- Translate all maintained Markdown titles/prose and development prompts into
  English, including architecture/schema/roadmap, the original MVP, and third-party
  notices/provenance. Consolidate the original MVP into the roadmap's historical
  planning section and remove the retired standalone file. Preserve original terms
  quotations, citations, scientific
  facts, source hashes, paths, and historical validation records.
- Require English development text by default in all agent templates; honor
  explicit communication-language requests and preserve user/original evidence.
- Keep legacy Boolean aliases through Unicode escapes without non-English
  literals in maintained source. Runtime behavior and input compatibility are unchanged.
- Update to 0.2.3 as explicitly requested; schema remains 0.1.0.
  No CP2K calculations, package publication, or runtime certification are implied.
- Full regression: 138 tests passed, none skipped; compileall, diff checks, and CLI
  version checks passed. Added maintained-language, local-link, English-prompt, and
  legacy-Boolean compatibility checks. Official quotations/source hashes are unchanged.

## 0.2.2

### Interaction changes

- Application title becomes `cp2kkit Main menu`; input editor title is
  `Main menu: current settings`.
- Translate all submenus, field labels, selection/validation prompts, status,
  previews, write confirmations, and cancellation messages into English.
- Menu numbers, operations, defaults, generated content, and overwrite protection
  stay unchanged; legacy Boolean aliases remain accepted.
- Version 0.2.2 was explicitly requested; retain the 0.2.1 format fixes and schema 0.1.0.
  No CP2K execution/runtime certification.
- Full regression: 134 tests passed, none skipped; new checks cover all submenus,
  previews/confirmation, and the application menu's English output.
  Compileall, diff checks, and CLI version checks passed.

## 0.2.1

### Fixes

- Remove floating-point display tails from EPS_DEFAULT and inner/outer EPS_SCF;
  use readable uppercase scientific notation such as `1.0E-12`/`1.0E-06`.
  Preserve custom EPS significant digits and existing numerical thresholds.
- Align CELL/COORD columns at eight decimal places, normalize negative zero,
  and preserve separators for oversized numbers. Add the geometry PBC comment.
  Omit unit keywords as requested, using CP2K's angstrom defaults.
- Generated-structure JSON matches the rounded text; original structure retains
  its precision. Reject cells made singular by rounding.
- Fix version increments C: 0.2.0 -> 0.2.1; A/B, schema 0.1.0, and CP2K target defaults unchanged.
  Geometry text/input SHA-256 changes; existing files are untouched. CP2K was not run.
- Full regression: 132 tests passed, none skipped. Compileall, diff/version checks passed.
  Added exact-format/custom-EPS/negative-zero/large-number/round-trip/singular-cell tests.

## 0.2.0

### Added

- `cp2kkit` opens the application menu; `cp2kkit STRUCTURE` loads a structure first.
  Load/change structures, generate inputs, export extXYZ, and report output quality.
- Standard-library Cartesian GJF/COM, CIF, VASP5 POSCAR/CONTCAR, `.vasp`, and
  `.poscar` readers alongside XYZ/extXYZ/restart.
- With diag+smearing and no explicit override, automatically set
  `ADDED_MOS = max(30, NINT(atom_count/2))`; write alpha/beta values separately for UKS.
- Configurable OT outer limit `--max-outer-scf`, default 20.
- `.agents/prompts/update-version-docs.md`, integrated with development rules,
  feature/Multiwfn templates, following the user's A.B.C convention.

### Defaults and interaction

- PROJECT changes from fixed `cp2kkit` to the structure filename without suffix; override allowed.
- CUTOFF/REL_CUTOFF change from 350/50 Ry to **400/55 Ry**.
- OT inner/outer defaults are **25/20**; diagonalization remains 128.
- Empty orbitals change from fixed 20 to the smearing heuristic, otherwise 0.
- Pressure appears only for CELL_OPT; isolated padding only for effective NONE.
  OT hides smearing/empty orbitals and rejects explicitly requested smearing or
  nonzero empty orbitals instead of silently ignoring them.

### Migration and limitations

- Existing batch commands remain. Application menus require TTY; scripts use subcommands.
- Reproduce old grid/project defaults with `--cutoff 350 --rel-cutoff 50 --project cp2kkit`;
  old OT inner limit with `--max-scf 128`; old diag empty orbitals with `--added-mos 20`.
  Do not pass nonzero empty orbitals to OT.
- GJF charge/multiplicity and POSCAR constraints are source metadata, not inherited
  CP2K settings. CIF requires explicit symmetry or declared P1; partial occupancy/disorder,
  VASP4 without elements, and GJF internal coordinates are rejected.
- The empty-orbital rule is Multiwfn's usual 300 K heuristic, not a guarantee for every
  system/temperature.
- Software becomes **0.2.0**; schema remains **0.1.0**, CP2K target default 2026.2.
- Full regression: 128 tests passed, none skipped; compileall/diff/CLI-version checks passed.
  Consistency tests cover package metadata/module, README/changelog, CLI, and generator.
- No CP2K/Multiwfn calculations. Synthetic fixtures are not scientific results;
  actual software certification and parameter convergence remain unverified.
