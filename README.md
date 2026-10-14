# cp2kkit

A Python toolkit connecting CP2K output reading, traceable post-processing, and
non-destructive input generation. The original MVP planning baseline is preserved in
[the roadmap](docs/roadmap.md). **v0.2.3 preliminary implementation**, not a production
release certified with actual CP2K runs.

- Analysis remains read-only: no submission/execution or modification of existing
  inputs, restart files, or raw output.
- The six MVP features have entry points, with additional `generate-input`,
  `cube-check`, and `cube-diff` commands; calculations are never run automatically.
- The core uses Python's standard library; Matplotlib is optional.
- Outputs include schema, units, SHA-256, line numbers, and original text.
  Missing values are not zero.
- All existing targets, including derived CSV/JSON/images, are protected from overwrite.
- Energies can be extracted from failed jobs without becoming valid scientific results.

## Current version: 0.2.3

All maintained documentation, headings, development prompts, and project text are
in English. Development templates now require English by default while preserving
original third-party quotations/citations and user data. The version is 0.2.3 as
explicitly requested. CLI behavior, scientific defaults, and schema 0.1.0 are unchanged.
The English menus from 0.2.2 and EPS/geometry formatting fixes from 0.2.1 remain.
See [the changelog](CHANGELOG.md) for changes and migration notes.
A version number is not CP2K runtime certification.

## Quick start

Python >= 3.10. Run from the repository root without installing:

```bash
export PYTHONPATH="$PWD/src"
python -m cp2kkit --help
python -m cp2kkit discover tests/fixtures
python -m cp2kkit parse tests/fixtures/normal.out
python -m cp2kkit report tests/fixtures/unconverged.out --strict
```

Install into the existing Python environment:

```bash
uv pip install -e .
# Install the optional dependency only when plotting is needed.
uv pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e '.[plot]'
cp2kkit --help
```

Files in `tests/fixtures` are **synthetic format examples, not calculation results**.

## Default main menu and CLI

```bash
cp2kkit                 # Select a current-directory file by number or enter a path.
cp2kkit crystal.cif     # Load a structure, then open the main menu.
cp2kkit water.gjf
cp2kkit POSCAR
```

The menu provides loading/changing structures, input generation, extXYZ export,
and output quality reports. Generation or cancellation returns to the application
menu; a failed load does not replace the current structure. Interactive entry points
require a TTY; scripts retain the batch subcommands below.

## CLI subcommands

```bash
# Scan one directory level; return an empty list if no projects are found.
cp2kkit discover /path/to/run

# Select a project in multi-project directories; select an explicit file for multiple outputs.
cp2kkit parse /path/to/run --project water -o parsed.json
cp2kkit parse /path/to/run/water.out --format csv -o energy.csv

# Electronic and geometry convergence are separate; strict failure exits with 7.
cp2kkit report /path/to/run/water.out --strict -o quality.json

# Default frame -1 is the last frame; extXYZ preserves the cell.
cp2kkit export-structure /path/to/run/water.restart -o water.extxyz
cp2kkit export-structure /path/to/run/water-pos-1.xyz --frame 0 -o first.extxyz
# Explicitly permit cell loss when exporting a known cell to plain XYZ.
cp2kkit export-structure water.restart --format xyz --allow-cell-loss -o water.xyz

# Write curve.png, curve.csv, and curve.json; reject the operation if any target exists.
cp2kkit plot /path/to/run/water.out -o curve.png
cp2kkit plot /path/to/run/water.out --kind scf -o scf.png
```

Without `--output`, discover/parse/report/cube-check write machine-readable stdout;
diagnostics go to stderr. Parent directories must exist; commands do not create
large directory trees. Structure export also writes `<full-output-filename>.json`
with the original cell, coordinates, provenance, and warnings.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Command completed; not a guarantee of calculation quality |
| 2 | Argument, path, or filesystem problem |
| 3 | Ambiguous project/output selection |
| 4 | Unsupported, damaged, or unparseable data |
| 5 | Target exists; overwrite refused |
| 6 | Missing optional plotting dependency |
| 7 | `report --strict` quality assessment not passed |

## CP2K input generation

The GPW subset was developed with reference to Multiwfn's `cp2kmate.f90`:

```bash
cp2kkit generate-input water.xyz -o water.inp --periodic NONE --project water
cp2kkit generate-input water.xyz -o water-opt.inp --periodic NONE \
  --run-type GEO_OPT --dispersion d3bj
cp2kkit generate-input solid.extxyz -o solid.inp --run-type CELL_OPT \
  --scf diag --kpoints 3 3 3 --smearing 300
```

A Multiwfn-style numbered menu complements the unchanged argument-based interface:

```bash
cp2kkit generate-input --tui
# Supplied arguments seed editable menu settings.
cp2kkit generate-input water.xyz -o water.inp --periodic NONE --tui
# In a terminal, no structure/output arguments also opens the editor.
cp2kkit generate-input
```

The editor supports grouped settings, full previews, replayable commands, and
explicit confirmation before writing. `q` cancels without generation.
It is a standard-library line-oriented numbered TUI, not a full-screen arrow-key UI;
curses and Multiwfn are not runtime dependencies. Non-terminal batch use remains CLI-only.
See [input generation](docs/input-generation.md).

Supported: ENERGY/ENERGY_FORCE/GEO_OPT/CELL_OPT, PBE/BLYP, MOLOPT-GTH,
D3/D3(BJ), charge/multiplicity, cell/PBC, OT/diagonalization, and k-points.
Input and `<output>.json` are both overwrite-protected.
Structures include XYZ/extXYZ, restart, Cartesian GJF/COM, CIF, and VASP5 POSCAR/CONTCAR.
PROJECT defaults to the source filename without suffix; grid defaults to 400/55 Ry;
OT inner/outer limits are 25/20. With diag+smearing, empty orbitals default to
`max(30, NINT(atom_count/2))`, with manual override.
Plain XYZ requires explicit periodicity. Sources provide geometry, not calculation settings.
`--data-dir` checks basis/potential names and records data-file hashes.
**No CP2K runtime validation or full Multiwfn port is claimed.**
Details/defaults/limitations are in the [generation guide](docs/input-generation.md).
[Third-party notices](THIRD_PARTY_NOTICES.md) record Multiwfn sources, custom terms,
and required papers; they do not establish separate permission or relicensing/paid-distribution boundaries.

## Density cubes and differences

```bash
# Run from the repository root without installing.
export PYTHONPATH="$PWD/src"
python -m cp2kkit generate-input AB.extxyz -o AB-density.inp --project AB \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1
python -m cp2kkit cube-check AB.cube -o AB-cube-check.json
python -m cp2kkit cube-diff AB.cube A.cube B.cube -o delta-density.cube
python -m cp2kkit cube-check delta-density.cube
```

Generation supports `--electron-density`, `--spin-density`, and `--cube-stride`.
GPW/GTH produces pseudopotential valence electron density; UKS also produces
alpha-minus-beta spin density. Target version defaults to 2026.2, with checked
common density-print syntax profiles for 2024.1-2026.2, not runtime certification.
Optimization disables routine cube printing and requests the final step.
For subtraction, prefer final fixed-geometry single points.

Cubes are read line by line; reports include grids, hashes, unit evidence, and integrals.
Unknown scalars produce only raw numerical integrals. Subtraction is
`rho[0] - sum(rho[1:])`, allows multiple fragments/different atom counts, and strictly
compares unit-normalized grids without interpolation/registration.
Cube/JSON outputs are staged then published exclusively; existing targets are refused.
**Positive/negative difference integrals are not fragment net charge transfer.
Matching grids do not establish matching reference states.**
See [the cube guide](docs/cube.md) for formats, units, physics, AB/A/B examples, and validation.

## Implemented scope and limitations

| MVP feature | Preliminary implementation |
|---|---|
| CLI/project discovery | Deterministic order, one-level scan, explicit ambiguity handling, stable exit codes |
| CP2K parsing | Total energies, SCF summaries, geometry success/failure, version/project/run type, diagnostics, some settings |
| Structure/cell export | Strict XYZ/extXYZ/restart subset, triclinic cells, bohr conversion, scaled coordinates |
| Quality reports | Completion/electronic/geometry evidence; unknown/truncated jobs cannot pass |
| CSV/JSON/provenance | Schema 0.1.0, units, null/empty values, original text/lines/hashes, quality flags |
| Energy/convergence plots | Energy and SCF iteration counts per cycle; disconnected segments; CSV/JSON sidecars |

### Compatibility statement

**Synthetic format regression is complete; no CP2K release is certified by actual calculation fixtures.**
Parsing follows explicit output markers, not suffix/version guesses.
The illustrative "2026.1" is not evidence of compatibility.
Real fixtures and source-format checks remain a release gate.

- Supports `ENERGY| Total FORCE_EVAL (...) energy [a.u.]`; energy stays in hartree.
- `PROGRAM ENDED AT` proves a normal-end marker, not convergence by itself.
- Positive quality rules cover ENERGY/ENERGY_FORCE/GEO_OPT/CELL_OPT only.
  MD/BAND/NEB records may parse but cannot be classified passed by these rules.
- `passed` means text evidence passed, not suitable basis/potential/functional,
  dispersion, k-points, charge/spin, or periodicity for the scientific target.
- Missing version, force/stress, settings, timing, or process exit codes are not inferred.
  Only explicit `Total wall time [s]`/`WALL TIME [s]` are read, not the full TIMER table.
- Settings retain original strings; absent values are not filled with CP2K defaults
  or implicitly merged from input files.
- Current SCF plots show **iteration counts**, not residuals/optimization gradients.
- New-start markers or non-increasing step numbers split segments; restarted energy
  continuity is not inferred.
- XYZ without a cell is warned about, not assumed non-periodic.
- Restart supports one SUBSYS, explicit CELL/COORD and KIND/ELEMENT; no preprocessor,
  external coordinates, or nested CELL/COORD sections. Unknown relevant syntax is rejected.
- UTF-8 decoding is strict. Existing output/restart readers load whole files;
  streaming very large outputs is future work. Cube reading is bounded line-by-line
  and supports only single-scalar files.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m compileall -q src tests
```

Tests do not run quantum chemistry or require pytest. Plot tests are skipped only
if Matplotlib is missing. See [architecture](docs/architecture.md),
[schema](docs/schema.md), [roadmap](docs/roadmap.md), and
[fixture provenance](tests/fixtures/README.md).
