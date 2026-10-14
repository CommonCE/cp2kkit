# CP2K input generation

This guide describes cp2kkit **0.2.3**. Older defaults and migration notes are in
[the changelog](../CHANGELOG.md).

`generate-input` is an explicit write entry point added beyond the read-only MVP;
it neither submits nor runs calculations. It is a Python GPW subset developed
with reference to Multiwfn's `outCP2Kinp`, not a complete Fortran port or strict
clean-room implementation. Sources, custom terms, and the two required papers are
in [third-party notices](../THIRD_PARTY_NOTICES.md), [terms](../third_party/multiwfn/TERMS.md),
and [provenance](../third_party/multiwfn/PROVENANCE.md). Generated input/JSON include
the citations; related research must still cite the papers appropriately in the main text.

## Usage

```bash
cp2kkit              # Application menu: select a file, then generate/export.
cp2kkit solid.cif    # Load a structure before opening the application menu.
cp2kkit water.gjf
cp2kkit POSCAR
```

The application menu is separate from the settings editor below. Generation or
cancellation returns to the application menu. Without `--project`, PROJECT is the
source basename without suffix (POSCAR becomes POSCAR). Safe names contain letters,
digits, underscores, periods, and hyphens; override names containing unsupported
characters such as spaces. Edit the new output path before confirming; no files
are written until confirmation.

```bash
# Plain XYZ has unknown PBC: explicitly choose NONE or periodic directions.
cp2kkit generate-input water.xyz -o water.inp --project water --periodic NONE

# PBE-D3(BJ) geometry optimization; automatic isolated box with 6 angstrom per side.
cp2kkit generate-input water.xyz -o water-opt.inp --periodic NONE \
  --run-type GEO_OPT --dispersion d3bj --vacuum 6

# Preserve source cell/PBC, not the original method/charge/spin.
cp2kkit generate-input solid.extxyz -o solid.inp --run-type CELL_OPT \
  --scf diag --kpoints 3 3 3 --smearing 300 --added-mos 30

# Override orthorhombic lengths in angstrom; charge +1 and doublet.
cp2kkit generate-input radical.xyz -o radical.inp --periodic NONE \
  --cell 20 20 20 --charge 1 --multiplicity 2 --functional BLYP

# Verify local data names and hashes; D3 also requires dftd3.dat.
cp2kkit generate-input water.xyz -o checked.inp --periodic NONE \
  --data-dir /path/to/cp2k/data

cp2kkit generate-input --help
```

Outputs are `<output>` and `<output>.json`. If either exists, refuse overwrite
(exit 5); a sidecar collision rolls back the newly created input. There is no
`--force`. Parent directories must already exist.

## Multiwfn-style numbered TUI

```bash
# Interactive entry: prompt for structure and new output paths.
cp2kkit generate-input --tui
cp2kkit generate-input --interactive     # Equivalent option.

# CLI arguments seed the editor; no separate physical defaults.
cp2kkit generate-input water.xyz -o water-opt.inp --periodic NONE \
  --run-type GEO_OPT --dispersion d3bj --electron-density --tui

# A terminal invocation without structure/output automatically opens the editor.
cp2kkit generate-input
```

Application title: `cp2kkit Main menu`; editor title: `Main menu: current settings`.
All submenus, labels, prompts, validation, previews, confirmations, and documentation
are in English. Menu numbers, auto/q/quit/y/n operations, and parameter semantics
are unchanged; legacy Boolean input aliases remain accepted.

This is a revisitable settings editor, not a mandatory sequential wizard. It uses
standard-library line-oriented interaction for terminals/SSH without curses or extra
UI packages. Neither the Multiwfn executable nor adjacent development source is required.

| Editor action | Content |
|---:|---|
| 1 | Files, project and version: structure, XYZ frame, new output, project, target CP2K |
| 2 | Task and optimization: run type, optimizer, steps, pressure |
| 3 | Method, basis and dispersion: GPW functional, MOLOPT-GTH, dispersion, data directory |
| 4 | Charge and spin |
| 5 | Periodicity and cell: PBC, orthorhombic override, isolated padding (angstrom) |
| 6 | SCF, k-points and occupations: OT/diag, EPS_SCF, limits, k-points, smearing (K), empty orbitals |
| 7 | Integration grid: CUTOFF/REL_CUTOFF (Ry) |
| 8 | Electron/spin density cubes: switches and STRIDE |
| 9 | Validate/preview complete input, provenance warnings, and replayable CLI; no writing |
| 0 | Validate/show effective settings; write only after explicit y/yes |
| q / quit | Cancel the session without generation |

- Select a field inside a group; `0` returns to the editor menu. Enter keeps the value.
- Pressure appears only for CELL_OPT; padding only for effective NONE.
  OT hides smearing/empty orbitals and shows outer limits; diag does the reverse.
  Field numbers vary with available options. Switching algorithms does not silently
  clear explicit conflicts; edit them manually.
- PROJECT/MAX_SCF/ADDED_MOS accept `auto`. Project follows the current source;
  OT inner default is 25, diag 128. Automatic empty orbitals depend on atom count/smearing.
- Enumerations accept displayed numbers/names; Boolean values accept y/n;
  triples are space-separated.
- Optional `auto` restores defaults/removes overrides. PBC auto inherits source
  PBC, **not NONE**; smearing auto disables it; cell auto preserves the source;
  cube_stride auto restores the effective default.
- Paths may contain spaces: enter literal paths without shell quotes. `q`/`quit`
  cancel; use `./q`/`./quit` for literal filenames. Output parent directories must exist.
- Type/range errors retry locally. Cross-field/structure errors appear on preview/generation
  and return to editing. Spin density without UKS, OT+non-Gamma, and unknown PBC
  are not fixed by silently changing other settings.
- Confirmation defaults to no; Enter returns to editing. Existing targets still exit 5,
  with no overwrite button. EOF/Ctrl-C exits 2; unfinished writes roll back through
  the writer, while completed files are retained.
- TUI requires stdin TTY; pipes cannot impersonate interactive confirmation. Use CLI
  for scripts. stdout may be redirected to save menus/previews. Complete regular
  CLI calls do not enter TUI even from a terminal.

Both modes share `InputSettings`, `generate_input`, and `write_input`. Identical
structure/settings yield identical text/JSON; there are no TUI-only physical defaults
or schema changes. Replay commands are shell-quoted for display only, never executed.
The menu covers the current GPW subset, not all Multiwfn tasks/methods.

## Scope and defaults

| Setting | Support/default |
|---|---|
| Structure | `.xyz`/`.extxyz`/text `.restart`/`.gjf`/`.com`/`.cif`/POSCAR/CONTCAR/`.vasp`/`.poscar`; XYZ last frame |
| Task | ENERGY (default), ENERGY_FORCE, GEO_OPT, CELL_OPT |
| Method | Quickstep/GPW; PBE (default), BLYP |
| Basis | DZVP-MOLOPT-SR-GTH (default); SZV-MOLOPT-SR-GTH, DZVP/TZVP/TZV2P-MOLOPT-GTH |
| Potential | GTH-PBE/GTH-BLYP; basis and potential explicitly matched with `-qN` |
| Dispersion | none (default), D3, D3(BJ); dftd3.dat and REFERENCE_FUNCTIONAL |
| Charge/spin | 0/1; explicit valence-electron parity check; UKS for multiplicity > 1 |
| SCF | OT+FULL_ALL/DIIS+outer SCF (default), or diagonalization+Broyden mixing |
| EPS_SCF | ENERGY 5e-6, other tasks 1e-6; override allowed |
| SCF limits | OT inner/outer 25/20; diag 128; `--max-scf`/`--max-outer-scf` overrides |
| Grid | CUTOFF 400 Ry/REL_CUTOFF 55 Ry; NGRIDS 5 for non-SR, 4 for SR |
| k-points | Gamma default; non-Gamma requires XYZ+diag |
| Smearing/empty orbitals | Optional Fermi-Dirac K, requires diag; auto `max(30, NINT(atom_count/2))` with smearing, otherwise 0; OT rejects smearing/nonzero empty orbitals |
| Optimization | BFGS (default), LBFGS, CG; max 400 steps |
| CELL_OPT | Requires XYZ/lower-triangular cell; analytical stress; default pressure 1.01325 bar |
| Target version | 2026.2 default; common density syntax profiles 2024.1/2/3, 2025.1/2, 2026.1/2; not runtime certification |
| Density cubes | Optional electron/applicable UKS spin density; stride default 1 1 1; final-step policy in [cube guide](cube.md) |

SR/PBE presets cover 71 elements:

```text
H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar
K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr
Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba
Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn
```

Non-SR presets cover only H C N O F Si P S Cl. BLYP presets exclude
Nb Tc Cd Sn Hf Ta Re Os Ir Pt Hg Tl Po At Rn; missing entries are rejected.
This is not arbitrary element/potential inference; the actual installed library
must contain matching names.

## Additional structure readers

Standard-library readers preserve original hashes and do not run Gaussian/VASP/Multiwfn.

- **GJF/COM:** one Gaussian job with Cartesian geometry; symbols/atomic numbers,
  angstrom/bohr, and three TV vectors. Without TV, PBC is explicitly NONE.
  Charge/multiplicity are metadata only. Reject Z-matrices, freeze flags/complex
  labels, Link1 jobs, and checkpoint geometry.
- **POSCAR/CONTCAR:** VASP5 element line required. Supports Direct/Cartesian,
  one scale including negative target volume, three-direction scales, and selective
  dynamics. Constraint flags remain metadata, not CP2K constraints; generation warns.
  Reject VASP4 without elements and velocity/predictor/trailing sections.
- **CIF:** one data block with cell parameters/fractional coordinates; expand
  explicit symmetry and deduplicate across periodic boundaries. Supports x/y/z
  addition/subtraction, rational shifts, uncertainties, and semicolon text metadata.
  Without operations, only explicit P1 is accepted; do not silently treat a non-P1
  asymmetric unit as the full cell. Reject partial occupancy, disorder, overlapping
  species, missing coordinates, unsupported expressions. No space-group database
  lookup or Cartesian-only CIF support.

## Periodicity, cell, and scientific limitations

- Plain XYZ is not assumed isolated; unknown PBC requires `--periodic`.
- Preserve a source cell preferentially; `--cell A B C` overrides it with an orthorhombic cell.
- Only NONE without a cell gets an automatic box: atomic span plus vacuum on both
  sides per axis. Translate coordinates into it and record original/generated
  structures without modifying the source.
- Existing/explicit cells are not automatically centered. For isolated systems,
  ensure density vanishes at boundaries yourself.
- CELL/POISSON directions match: XYZ uses PERIODIC, NONE WAVELET, 1D/2D ANALYTIC.
  Low-dimensional convergence can be slow; verify vacuum/electrostatic error.
- This OT implementation lacks advanced metal rotation/occupation settings.
  Metals require diag and suitable k-points/smearing/empty orbitals. UKS explicitly
  writes equal alpha/beta ADDED_MOS values; keyword types were checked against
  [CP2K 2026.2 SCF](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/SCF.html).
  The heuristic follows Multiwfn's smearing branch (usually 300 K), not an exact
  electron/basis-based sufficiency guarantee. Check high-temperature/metals/orbital
  analysis and override as needed. Positive half-integer rounding matches Fortran NINT.
- Charge/multiplicity checks ensure explicit-electron consistency, not the correct
  magnetic state. No antiferromagnetism, broken-symmetry singlets, or per-KIND MAGNETIZATION.
- Restart provides **geometry only**: original KIND labels merge by element;
  method/U/constraints/moments/charge/solvent are not inherited. This is a new template,
  not a complete restart of the original job.
- Hybrid/ADMM, DFT+U, MD, frequencies, NEB, TDDFT, solvents, external fields, atomic
  constraints, and other advanced Multiwfn branches are not implemented.
  Electron/spin cubes are supported; potential/ELF/MO cubes are not.
- Default cutoff/basis/vacuum/k-points are not converged for the target system.
  Deprecated CELL_OPT TYPE DIRECT_CELL_OPT is not emitted.

## Electron/spin density output

```bash
cp2kkit generate-input AB.extxyz -o AB-density.inp --project AB \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1
```

Without a request, no density PRINT is added. `--spin-density` requires current
UKS eligibility (multiplicity > 1). CP2K's E_DENSITY_CUBE controls both fields,
so both are written under UKS. Routine optimization frequency is 0; ADD_LAST
NUMERIC requests the final recognized step, not proof of convergence or a guarantee
of output after abnormal termination. Frequencies/files/GPW valence meaning and
older-version differences are in the [cube guide](cube.md).

## Generated text formatting

- EPS_DEFAULT and inner/outer EPS_SCF use uppercase scientific notation, e.g.
  `1.0E-12`/`1.0E-06`. Numerical defaults remain ENERGY 1e-11/5e-6, other tasks
  1e-12/1e-6. Custom EPS retains float significant digits, not a fixed one-decimal rounding.
- CELL A/B/C and Cartesian COORD columns use eight decimal places, normalize
  `-0.00000000`, and retain separating spaces for values exceeding the column width.
- Omit `[angstrom]`/`UNIT angstrom` as requested, using CP2K's angstrom defaults;
  header/JSON still state units. Checked against CP2K 2026.2
  [CELL](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/SUBSYS/CELL.html) and
  [COORD](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/SUBSYS/COORD.html).
- Eight decimals round geometry: `source_structure` keeps original precision;
  `generated_structure` matches the actual text. Reject cells made singular by
  rounding. Source files and the separate high-precision `export-structure` are unchanged.

## Reproducibility and validation

JSON records generator version, complete input/SHA-256, parameters/units, effective
SCF threshold, each element's basis/potential/electron count, source path/hash/frame,
generated geometry, translation, and warnings. `runtime_version=null` and
`runtime_validated=false`: a target version is not an executed version.

`--data-dir` checks element/name headers in local BASIS_MOLOPT/GTH_POTENTIALS and
records hashes; D3 also records dftd3.dat. It does not certify coefficients/parameters.
Otherwise runtime CP2K_DATA_DIR resolves basenames; the actual installation has
not been verified. Record the executed CP2K binary version in subsequent calculations.

Synthetic regression, section balance, and geometry round-trips are tested.
CP2K has not been launched; actual native syntax/runtime certification remains open.

## References

- User-provided `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`, `outCP2Kinp`,
  lines 68-3448: basis names, Nval, tasks/sections.
  Inspected SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
  Original Fortran is not copied/distributed or required at runtime.
- CP2K database header checks, not execution certification:
  [BASIS_MOLOPT](https://github.com/cp2k/cp2k/blob/master/data/BASIS_MOLOPT),
  [GTH_POTENTIALS](https://github.com/cp2k/cp2k/blob/master/data/GTH_POTENTIALS).
- Official input references:
  [POISSON](https://manual.cp2k.org/trunk/CP2K_INPUT/FORCE_EVAL/DFT/POISSON.html),
  [OT](https://manual.cp2k.org/trunk/CP2K_INPUT/FORCE_EVAL/DFT/SCF/OT.html),
  [CELL_OPT](https://manual.cp2k.org/trunk/CP2K_INPUT/MOTION/CELL_OPT.html),
  [PAIR_POTENTIAL](https://manual.cp2k.org/trunk/CP2K_INPUT/FORCE_EVAL/DFT/XC/VDW_POTENTIAL/PAIR_POTENTIAL.html).
  Trunk changes over time; recheck the actual version before submission.
