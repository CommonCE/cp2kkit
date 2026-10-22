# cp2kkit

A Python toolkit connecting CP2K output reading, traceable post-processing, and
non-destructive input generation. The original MVP planning baseline is preserved in
[the roadmap](docs/roadmap.md). **v0.3.4 preliminary implementation**, not a production
release certified with actual CP2K runs.

- Analysis remains read-only: no submission/execution or modification of existing
  inputs, restart files, or raw output.
- The six MVP features have entry points, with additional `generate-input`,
  `cube-check`, and `cube-diff` commands; calculations are never run automatically.
- The core uses Python's standard library; Rich styling and Matplotlib are optional.
- Outputs include schema, units, SHA-256, line numbers, and original text.
  Missing values are not zero.
- Analysis/CSV/JSON/images remain overwrite-protected. Input generation may replace
  an existing regular `.inp`; sources, data files and symlinks remain protected.
- Energies can be extracted from failed jobs without becoming valid scientific results.

## Planned 0.3.x functional and method coverage

The [functional/method expansion proposal](docs/functional-roadmap-0.3.md) uses
Multiwfn 2026.10.1's CP2K generator as the primary coverage/assembly reference:
21 DFT selections, including complete nonlocal methods, plus the **GFN-xTB
series (GFN0, GFN1 and GFN2)**. GFN0/1 use CP2K-native implementations; GFN2
requires tblite. Delivery is staged with target-version/data/combination checks;
upstream defaults and correlated methods are not enabled automatically.
Version 0.3.0 implements the 15 non-hybrid DFT profiles below. Version 0.3.1
adds the three GFN-xTB methods. Version 0.3.2 adds PBE0, HSE06 and B3LYP direct-HFX
input generation; version 0.3.3 adds BHandHLYP, M06-2X and configurable PBEh.
All 21 referenced DFT selections now have bounded generation support; this is
not full Multiwfn feature/combination coverage.

## Current version: 0.3.4

The ADMM follow-up retains version 0.3.4 by user request and fixes auxiliary-library emission: ADMM inputs generated with
`--data-dir` or `CP2K_DATA_DIR` retain the resolved `BASIS_ADMM_UZH` path,
rather than incorrectly replacing it with the orbital alias `BASIS_MOLOPT_UZH`.
No explicit `--basis-file` workaround is needed. Regenerate affected 0.3.4
inputs into new paths; existing files are not repaired automatically. Orbital
UZH aliases, method parameters, CLI/config interfaces and schema remain unchanged.
This is an input-generation fix, not native CP2K or scientific validation.

### PBE0/HSE06 ADMM and AUX_FIT infrastructure

ADMM is opt-in, not a new functional. `--admm` (menu **122**) enables
`BASIS_PROJECTION` with operator-consistent `EXCH_CORRECTION_FUNC DEFAULT`
and exchange scaling `NONE`. Purification defaults to **MO_DIAG for OT** or
**NONE for diagonalization**; explicit MO_DIAG with diagonalization fails without
changing the solver. All existing hybrid task/model restrictions still apply.

Menu **223** selects the independent AUX_FIT registry: **200 admm-dz /
201 admm-dzp (default) / 202 admm-tzp / 203 admm-tz2p** from
`BASIS_ADMM_UZH`. CLI/config use stable string IDs, not these numbers.
Actual ORB and AUX_FIT files are required; element/q, selected Gaussian payloads,
conflicting aliases across the complete emitted file union, paths and hashes are
checked. No coefficients or catalog-only auxiliary templates are bundled.

```bash
cp2kkit generate-input water.xyz -o water-pbe0-admm.inp --periodic NONE \
  --functional PBE0 --admm --aux-basis admm-dzp \
  --data-dir /path/to/cp2k/data --write-json
```

Explicit sources use `--basis-file` and repeatable `--aux-basis-file`;
menu 223's **f** edits the auxiliary-file list. Config/replay, split magnetic
KINDs, density bundles and source-file overwrite protection share this resolution.
RI-HFX, UZH-PBE0, GAPW and ADMM with the other four hybrids remain unavailable.
Checked data/q is not auxiliary-basis convergence, physical-pairing certification,
native CP2K acceptance or scientific validation. See
[ADMM details](docs/input-generation.md#admm-and-auxiliary-bases-034).

### Six direct-HFX hybrid profiles

The shared CLI/API/TUI generator now supports these six hybrid profiles for target
**CP2K 2026.2**, with classic MOLOPT/UCL GPW bases, Gamma points, NONE/XYZ PBC,
ENERGY/ENERGY_FORCE/GEO_OPT, RKS or collinear UKS, and OT or diagonalization
without smearing. DFT+U, GAPW, CELL_OPT, non-Gamma, RI-HFX and UZH-PBE0
protocols remain outside this hybrid scope. ADMM is separately opt-in for PBE0/HSE06 only.

- **PBE0**: 25% HF + 75% PBE exchange + full PBE correlation.
- **HSE06**: 25% short-range HF with matching XC/HF ω=0.11 bohr⁻¹.
- **B3LYP**: 20% HF and explicit **VWN3**, the Gaussian/Multiwfn convention.
- **BHandHLYP**: Libxc HYB_GGA_XC_BHANDHLYP + 50% HF.
- **M06-2X**: Libxc HYB_MGGA_X_M06_2X + MGGA_C_M06_2X + 54% HF;
  kinetic-energy-density/grid convergence needs independent checking.
- **PBEh**: explicit `--pbeh-fraction A`, dimensionless `0 < A <= 1`, no default;
  `(1-A)` PBE exchange + full PBE correlation + `A` HF. Use PBE for zero HF.
- The two new Libxc profiles require `--libxc-available`; M06-2X permits D3,
  not D3(BJ). BHandHLYP/PBEh currently permit no extra pair dispersion.
- Isolated global hybrids use full Coulomb HFX; periodic global hybrids use truncated
  Coulomb HFX. Automatic radius is min(6 angstrom, minimum cell face spacing/2.01),
  including skew cells. Converge radius/supercell separately.
- Chooser **1/110** appends **16 PBE0 / 17 HSE06 / 18 B3LYP / 19 BHandHLYP / 20 M06-2X / 21 PBEh** without changing
  the original 15 or xTB 30/31/32. Menu **120** edits direct-HFX controls and the explicit PBEh fraction when selected.
- Prefer real exact-hybrid potential entries when supplied; otherwise use
  **GTH-BLYP for B3LYP** and **GTH-PBE for all five other hybrids** automatically.
  These standard semilocal-family potentials need no approximation approval;
  provenance still distinguishes them from exact-hybrid potentials. Missing family
  entries fail without cross-family or q substitution. No auxiliary bases are invented.

```bash
cp2kkit generate-input water.xyz -o water-pbe0.inp --periodic NONE \
  --functional PBE0
cp2kkit generate-input solid.extxyz -o solid-hse06.inp \
  --functional HSE06 --hf-memory 1024
cp2kkit generate-input water.xyz -o water-b3lyp-opt.inp --periodic NONE \
  --functional B3LYP --run-type GEO_OPT
```

Direct HFX defaults: EPS_SCHWARZ=1e-6, MAX_MEMORY=512 **MiB per MPI process**,
EPS_STORAGE_SCALING=0.1, SCREEN_ON_INITIAL_P=F (no restart-dependent screening).
Override with `--hf-eps-schwarz`, `--hf-memory`, and periodic-global-hybrid-only
`--hf-cutoff-radius` [angstrom]. Memory is not total job memory or a scheduler
request. Nondefault HF controls fail on non-hybrid/xTB methods rather than being
silently ignored. No CP2K calculations were run for this feature; source checks
and synthetic generation do not certify the executable, convergence or properties.
See [complete hybrid scope and provenance](docs/input-generation.md#direct-hfx-hybrids-032).


Parser compatibility follow-up (version retained by user request): total-energy
records accept both `[a.u.]` and `[hartree]`, with values stored in hartree and
original evidence preserved. Numeric-token boundaries and conservative quality
rules are unchanged; parsing does not establish convergence or scientific validity.

### GFN-xTB input generation

Method selection **1 / 110** adds the exact Multiwfn xTB chooser numbers:
**30 GFN1-xTB**, **31 GFN0-xTB**, **32 GFN2-xTB (tblite)**.
Existing DFT chooser positions, basis registry numbers and global function IDs
are unchanged. **140** selects DFT/GFN-xTB, **141** asserts tblite availability,
and **142** edits dimensionless tblite ACCURACY for target 2026.2 only.

```bash
cp2kkit generate-input water.xyz -o water-gfn1.inp --periodic NONE --method GFN1-xTB
cp2kkit generate-input water.xyz -o water-gfn0-opt.inp --periodic NONE \
  --method GFN0-xTB --run-type GEO_OPT
cp2kkit generate-input water.xyz -o water-gfn2.inp --periodic NONE \
  --method GFN2-xTB --scf diag --tblite-available --xtb-accuracy 1.0
```

Target-version coverage: **GFN1 on 2024.2-2026.2**, **GFN0 from 2025.1**,
**GFN2 from 2025.2 with tblite linked**. Releases checked: 2024.2, 2024.3,
2025.1, 2025.2, 2026.1, 2026.2. Unavailable upstream model/version pairs fail
explicitly; no model substitution. GFN1 defaults to OT. GFN2 OT generation is
enabled only for target **2026.2**; legacy targets **2025.2/2026.1 require explicit
`--scf diag`** (menu 320). Omitted/default OT is rejected before writing, never
silently replaced. This guard follows a local 2026.1 tblite/OT crash; 2025.2 is
conservatively restricted without native validation. GFN0 is non-SCC and needs D4 build support. Legacy tblite
syntax differs from 2026.2; ACCURACY/native SCC controls are emitted only
where available. GFN2 OT convergence uses EPS_SCF; 2026.2 native SCC with diag
uses ACCURACY. Linked-build availability is user-asserted, not detected.
The bounded scope remains H-Rn, isolated Gamma ENERGY/ENERGY_FORCE/GEO_OPT,
closed-shell multiplicity 1. Intrinsic D4/GFN0, D3(BJ)/GFN1 and D4/GFN2 are retained;
no additional DFT-D correction is added. xTB does not use MOLOPT/GTH or the
DFT valence table. Incompatible nondefault DFT/density requests fail explicitly.
Periodic/open-shell/CELL_OPT/CDD/+U and custom refits remain outside this subset.
See [model/data/solver details](docs/input-generation.md#gfn-xtb-methods-031).
Earlier user-authorized water diagnostics found GFN2 diagonalization converged on
local 2026.1/git:5e54ba2, while OT crashed; local 2026.2/git:c92cc08 OT converged.
These narrow build-specific checks are not general CP2K/tblite certification.
Changing `--cp2k-version` does not upgrade the actual executable.

### Retained non-hybrid DFT profiles

The non-hybrid XC scope follows Multiwfn's actual component/nonlocal assembly,
with target **CP2K 2026.2** checks:

| Family | Implemented profiles |
|---|---|
| LDA | PADE (LDA alias) |
| GGA | PBE, revPBE, PBEsol, BP86 (BP alias), BLYP, RPBE |
| Meta-GGA | TPSS, revTPSS, SCAN, r2SCAN, MN15L (MN15-L alias), HLE17 |
| Required nonlocal correlation | B97M-rV, BEEF-vdW |

RPBE, all meta-GGAs and **BEEF-vdW** require `--libxc-available` / menu 113;
BEEF-vdW's native shortcut uses Libxc PW92 internally. This is an explicit user
build assertion, not detection. Matched potentials are preferred; missing matches
require `--allow-pbe-potential` / menu 114, never automatic relabeling.
B97M-rV includes rVV10 with b/C = 6.0/0.01; BEEF-vdW includes LMKLL. Their
`dispersion=none` means **no additional pair correction**, not disabled intrinsic
nonlocal correlation. Supply `--data-dir` to check/read/hash the required kernel;
without it, kernel resolution remains an unchecked runtime requirement.

Initial meta-GGA/nonlocal scope is GPW, Gamma, ENERGY/ENERGY_FORCE/GEO_OPT,
without +U. GAPW/non-Gamma/CELL_OPT/+U require separate validation; these are
cp2kkit scope limits, not CP2K-wide prohibitions. Existing GGA paths, basis IDs,
CLI/config/replay controls and default PBE input physics remain compatible.
Schema stays 0.1.0 with additive XC/kernel, HFX and model provenance. No new
Python runtime dependency or native calculation is included. See the
[full capability/dispersion matrix](docs/input-generation.md#non-hybrid-xc-profiles-030).

### Retained 0.2.9 workflows

Version **0.2.9** simplifies 602 option 4 to one six-integer line:
`all_charge all_multiplicity A_charge A_multiplicity B_charge B_multiplicity`.
All six values update together; invalid input leaves them unchanged.
Generator-main `0` validates and writes directly; `w` reviews and asks for
confirmation. Category/602 `0` only returns. Successful generation returns to
the application menu without an extra Enter prompt.

Whole-system multiplicity defaults to electron parity (even -> 1, odd -> 2),
not a ground-state spin prediction; explicit requests are preserved. Automatic
TUI output naming uses `<source-stem>-CDD.inp` while CDD is enabled. Default
UZH inputs emit portable `BASIS_MOLOPT_UZH` / `POTENTIAL_UZH` references;
resolved data paths/hashes remain in provenance and explicit file overrides win.

Version **0.2.9** implements the first menu-allocation round: compact common
shortcuts, category browsing and full-number direct access (menu layout v1),
plus **602 two-fragment density-difference input preparation**. It creates the
whole/A/B ENERGY inputs and an atom-mapping CSV, with optional combined JSON;
all bundle targets must be new. Geometry/cell/grid controls are shared, fragment
charges/spins require explicit values, and no CP2K execution or automatic cube
subtraction is performed. Advanced 700-1000 features remain deferred.
Software/schema/target/menu/basis versions are independent; schema stays 0.1.0.
See [workflow details](docs/input-generation.md#two-fragment-density-difference-inputs-029)
and [number migration](docs/menu-numbering-draft.md#14-migration-from-the-028-extension-numbers).


Version **0.2.8** adds **9. Fixed atoms** to GEO_OPT/CELL_OPT menus.
Enter 1-based indices/ranges such as `1,3-5,8`; `off` or `0` clears,
Enter keeps. CLI: `--fixed-atoms '1,3-5,8'`. The atom table uses the selected
frame/expanded geometry, not CIF site labels. Defaults remain unconstrained.
Only target 2026.2 is keyword-checked for active constraints. CP2K fixes
**fractional XYZ coordinates**: CELL_OPT can still move atoms with the cell.
Selections are retained, not remapped, after structure changes; source constraints
are never inherited. See [fixed-atom details](docs/input-generation.md#fixed-atoms-028).
Schema stays 0.1.0; no native execution/convergence certification.
The retained-version follow-up defaults EPS_SCF to **1e-6 for all tasks**, including
ENERGY; explicit `--eps-scf` overrides still win. EPS_DEFAULT is unchanged.

Version **0.2.7** now writes only the input by default and allows replacing an
existing regular `.inp`. Use `--write-json` or menu **501** for optional provenance
JSON (still exclusive). Existing JSON is never deleted/updated implicitly.
Basis/potential filenames, like D3 filenames, are emitted without quotes.

Version **0.2.7** fixes D3/D3(BJ) PARAMETER_FILE_NAME serialization: emit the
whole-line filename without quotes, avoiding a blank-prefix parser failure in
the inspected CP2K implementation. No physical parameters change. See the
[filename notes](docs/input-generation.md#d3-parameter-filenames-027).

Version **0.2.7** adds all-electron orbital choices **50-59** with automatic
GAPW/ALL and core-inclusive electron counts. The retained 0.2.8 policy now emits
NGRIDS 5 only for classic non-SR TZVP/TZV2P/TZV2PX-MOLOPT-GTH; other bases
omit NGRIDS. GAPW split tolerances and atomic grids use CP2K defaults.
Full ID **324 ALGORITHM** appears only for OT: choose IRAC/STRICT, or `auto`
for the basis-aware default; explicit selection wins. CLI: `--ot-algorithm IRAC`.
The automatic AE setup is a starting profile, not convergence certification;
both legacy auto/native profile names now default to explicit IRAC for all AE
bases. PP defaults to explicit STRICT; manual OT selections still win.
Charge/spin, functional, dispersion, cutoff and periodicity are not repaired.
See [the AE guide](docs/basis-selection.md#all-electron-automatic-setup-027).

The retained 0.2.8 follow-up keeps only generator/Multiwfn header comments.
Restart suggestions follow PROJECT (.wfn for Gamma, .kp otherwise) in metadata/
review only; no SCF_GUESS or WFN_RESTART_FILE_NAME hint is emitted or enabled.
Optimizations use explicit BFGS/LBFGS TRUST_RADIUS 0.2 angstrom (menu **403**,
`--trust-radius`), and **-5** / `--trajectory-format pdb|xyz|extxyz` selects
MOTION position output (XYZ default; EXTXYZ checked for target 2026.2).
Both SCF wavefunction and MOTION restart backup copies are set to 0; restart
writing remains enabled,
so archive old results before running. See [restart/output details](docs/input-generation.md#restart-hints-and-optimization-output-027-follow-up).

The preceding 0.2.6 basis follow-up added a
[permanent numbered registry](docs/basis-selection.md) with stable string IDs,
classic/UCL and paired UZH-PBE choices, explicit custom ORB files, actual-entry
alias/q checks, source ambiguity rejection and per-KIND provenance. PBE0 numbers
are allocated but unavailable. Version 0.3.4 separately enables the checked
PBE0/HSE06 AUX_FIT subset above; this does not enable paired UZH-PBE0 protocols.
Registry version 1 distinguishes the new contract from earlier positional menus;
old family names remain accepted, old numbers need explicit migration. This is
not a 1.0.0 release. With no actual data, output is an unverified template;
installed-data checks and CP2K execution are separate. Default input physics stays
unchanged. Analysis JSON/CSV and schema 0.1.0 are retained; generator settings now
serialize stable basis IDs. See the guide for those metadata/migration changes.

The initial 0.2.6 round added PBEsol, revPBE and Libxc RPBE profiles, TZVP/TZV2P short-range and
TZV2PX MOLOPT families, and explicit element-specific mixed bases. Header catalogs
pin CP2K v2026.2 source hashes and select actual basis files/potential q values.
Unmatched-functional GTH-PBE approximations require explicit user approval; RPBE
requires an explicit assertion that the target CP2K build has Libxc. New profiles
require target 2026.2, not runtime certification. Default PBE/DZVP-MOLOPT-SR-GTH,
physical settings, scrolling menus, batch exit codes and schema 0.1.0 are retained;
JSON receives additive method/catalog metadata. See the examples below.
Use `cp2kkit --plain -- -water.xyz` for an option-looking structure path; bare single
unknown words still mean paths.
See [the changelog](CHANGELOG.md), [architecture](docs/architecture.md), and
[remaining review work](docs/roadmap.md#review-follow-up-backlog).
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
# Optional scrolling-menu styling (plain mode works without Rich).
uv pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e '.[ui]'
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

The menu groups implemented actions into **Structure**, **Calculation**, and
**Analysis**, with continuous numbers and `0. Exit`. The header shows the source
basename, formula, atom count, cell lengths (angstrom), angles (degrees), and
periodicity. Unknown PBC stays Unknown, not NONE; full paths appear in details.
Output quality and CUBE analysis do not require a loaded structure. A marked
structure-dependent action can load a file and then resume automatically.
Failed replacement loads preserve the previous structure.

```bash
cp2kkit --plain
cp2kkit --plain crystal.cif
NO_COLOR=1 cp2kkit crystal.cif
```

Navigation:
- Application main menu: `0` or `q` exits; ordinary submenus use `0`/`back` to return.
- Input generation uses common shortcuts plus category browsing/full IDs.
  **Generator-main 0 validates/writes directly; w reviews and confirms;
  category 0/back returns without writing.** Generator-main -10/back/cancel returns; q exits the session.
  Hidden fields are retained; direct access cannot bypass applicability.
- Structure/frame remain in the header (s/f or 201/202). Output/project/version
  are editable in category 500; source/data/results remain protected.
- Parameter prompts: Enter keeps the value, `back` abandons that edit; literal
  `0` is a value, not navigation, except in the basis chooser where it returns.
  Optional `auto` restores source/default behavior.
- Use `r` to review or `p` to preview the full input/replay command without writing.
  Use generator-main `0` to validate/write directly, or `w` to review/write with
  explicit y/yes confirmation. Automatic output uses the source stem plus `.inp`
  in the current directory (`-CDD.inp` while CDD is enabled); explicit paths win.
  Ordinary generation may replace an existing regular `.inp`; CDD bundle targets
  must all be new. JSON/non-input collisions remain protected; a recovery prompt
  accepts another path.
- Ctrl+C cancels an operation back to main; at main it exits. EOF exits cleanly.
  Completed files are retained; unfinished writes use the existing rollback.
- Result summaries show Success/Warning/Error and full generated paths.
  Parsing success is distinct from calculation quality. Analysis summaries use
  Enter to return and `d` for full details; successful input generation returns
  immediately to the application menu.

These are ordinary line-oriented menus: no clearing, alternate screen, continuous
redraw, curses, or Textual. Narrow terminals fold text rather than truncate paths.
Rich is optional via `.[ui]`; `--plain` or any `NO_COLOR` disables styling entirely.
Interactive entry points require **both stdin and stdout TTY**. Redirected/pipe use
never waits for menu input; use explicit batch subcommands below instead.

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
| 3 | Ambiguous project/output/data-source selection |
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

The scrolling generator shows compact common shortcuts plus unexpanded category
entrances **100-600**. Open a category to browse full IDs or enter a full ID
directly, e.g. **101** for charge, **324** for OT ALGORITHM, **501** for JSON,
**602** for whole/A/B density-difference inputs. Category **500 owns output**;
**600 owns properties**. Unimplemented future categories are not displayed.

Generator-main 0 validates and writes directly; w reviews and writes only after
y/yes. Category 0/back returns without writing. Edits return to the originating menu; direct entry shares the same
applicability and validator as category browsing. Hidden values remain retained.
Source/frame s/f remain available (201/202); output/project/version also have
category editors (502/503/504). Common shortcuts, semantic CLI/config/replay
fields, and the independent immutable basis registry numbers remain supported.
**Old 100+ TUI scripts must migrate**: old 112 ADDED_MOS becomes 341, while
new 112 is DFT+U; no ambiguous numeric aliases. See the
[full numbering/migration guide](docs/menu-numbering-draft.md).

Complete CLI calls remain noninteractive. Rich is optional; --plain/NO_COLOR
disables styling; neither curses nor Multiwfn is a runtime dependency.
See [input generation](docs/input-generation.md).

Supported: ENERGY/ENERGY_FORCE/GEO_OPT/CELL_OPT subject to the
[per-profile limits](docs/input-generation.md#non-hybrid-xc-profiles-030), 15 non-hybrid
XC profiles plus the six [bounded direct-HFX hybrid profiles](docs/input-generation.md#direct-hfx-hybrids-032),
MOLOPT-GTH, checked D3/D3(BJ) combinations, charge/multiplicity,
cell/PBC, OT/diagonalization, and k-points on the existing semilocal paths.
For target CP2K **2026.2**, explicit Hubbard Ueff/L and collinear magnetic initial
states are also supported, including same-element opposite-spin KIND splitting.
`112`: enter `Element:L:Ueff_eV` entries separated by semicolons; `off` disables.
`103`: enter `uks`, or `Element=moment; @atom=moment`; `auto` restores the original
multiplicity-based spin behavior. Atom selectors are 1-based loaded/expanded order.
Element seeds apply first; atom seeds override them. Initial moments are alpha-minus-
beta electron numbers, not fixed moment constraints. No U, charge or multiplicity
is inferred/adjusted. For example, `Fe:2:4.0` and `Fe=4; @2=-4` illustrate syntax,
**not recommended parameters or a validated magnetic ground state**.
The matching CLI flags are `--dft-plus-u` and `--magnetism` (quote semicolon lists).
Without these explicit requests, generated CP2K input text/default physics stays unchanged.
By default only the input is written; existing regular `.inp` can be replaced.
`--write-json` / menu 501 adds an exclusively created `<output>.json`. If that
JSON already exists, generation fails before changing the input.
Structures include XYZ/extXYZ, restart, Cartesian GJF/COM, CIF, and VASP5 POSCAR/CONTCAR.
PROJECT defaults to the source filename without suffix; grid defaults to 400/55 Ry;
OT inner/outer limits are 25/20. With diag+smearing, empty orbitals default to
`max(30, NINT(atom_count/2))`, with manual override.
Plain XYZ requires explicit periodicity. Sources provide geometry, not calculation settings.
`--data-dir` or explicit `--basis-file` / `--potential-file` checks selected entries,
real names/aliases/q and records data-file hashes; see [basis selection](docs/basis-selection.md).
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

## Additional GGA and basis profiles (0.2.6)

Current menu IDs for these CLI controls: `221` / `--basis-overrides`, `114` / `--allow-pbe-potential`,
`113` / `--libxc-available`. Approval is shown outside PBE/BLYP; the Libxc
assertion follows each profile's requirement, including BEEF-vdW's native shortcut.
Hidden values are retained, not silently reset.

```bash
# Syntax examples only: inputs, spin, U, dispersion and convergence need system-specific checks.
cp2kkit generate-input solid.extxyz -o solid-pbesol.inp --functional PBEsol \
  --allow-pbe-potential --dispersion d3bj
cp2kkit generate-input surface.extxyz -o surface-rpbe.inp --functional RPBE \
  --allow-pbe-potential --libxc-available
# UCL triple-zeta SR families do NOT contain H/C/N/O at current q presets.
# Choose mixed bases explicitly rather than silently substituting a different family.
cp2kkit generate-input FeO.extxyz -o FeO-mixed.inp --basis TZV2P-MOLOPT-GTH \
  --basis-overrides 'Fe=TZV2P-MOLOPT-SR-GTH'
```

TZVP-SR/TZV2P-SR each cover 54 current preset elements; non-SR DZVP covers 11,
TZVP/TZV2P/TZV2PX cover 10. These are basis/PBE q matches, not unrestricted functional
or convergence guarantees. Actual basis libraries may include additional elements/
q values that cp2kkit intentionally does not enable. The existing default valence
policy is unchanged. No automatic q changes or SR/non-SR fallbacks are performed.
The registry follow-up checks selected-entry payload structure as well as headers,
using explicit files, `--data-dir`, or the actual CP2K_DATA_DIR environment directory.
Without actual files, installed availability is unverified. The Libxc flag is a user assertion, not build detection.
PBEsol/revPBE/RPBE D3 and D3(BJ) reference names were checked in tagged CP2K sources;
no PBE dispersion parameters are substituted. See [the full guide](docs/input-generation.md#functional-and-basis-profiles-026).

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

- Supports `ENERGY| Total FORCE_EVAL (...) energy [a.u.]` and `[hartree]` labels;
  energy stays in hartree without numerical conversion.
  A complete numeric token may be followed by whitespace or whitespace-delimited
  annotations; adjacent garbage/incomplete exponents remain unsupported. Original
  lines/hashes are preserved. Parsing an energy does not infer convergence.
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
