# Changelog

Software and data-schema versions are maintained independently.
This file records actual implementation changes, not publication to a package
repository or certification with actual CP2K calculations.

Versions use **A.B.C**: A is decided manually by the user; features increment B
and reset C; fixes increment C with A/B unchanged. A mixed feature/fix round
increments B once. Explicit user version requests take priority.

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
