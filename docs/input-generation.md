# CP2K input generation

This guide describes cp2kkit **0.2.9**. Older defaults and migration notes are in
[the changelog](../CHANGELOG.md). AE automatic setup is described in
[the basis guide](basis-selection.md#all-electron-automatic-setup-027).
The [registry-v1 basis guide](basis-selection.md) defines permanent numbering toward
1.0.0, data requirements, UZH protocols, custom 900 and explicit migration from
legacy list positions; it does not claim a 1.0.0 release or native validation.

`generate-input` is an explicit write entry point added beyond the read-only MVP;
it neither submits nor runs calculations. It is a Python GPW/GAPW subset developed
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
characters such as spaces. Set the output path before generating. Generator-main
`0` validates/writes directly; `w` reviews first and requires confirmation. Complete
batch calls write noninteractively. Ordinary single-input generation may replace a
regular `.inp`; density bundles and requested JSON always require new targets.

```bash
# Plain XYZ has unknown PBC: explicitly choose NONE or periodic directions.
cp2kkit generate-input water.xyz -o water.inp --project water --periodic NONE

# PBE-D3(BJ) geometry optimization; automatic isolated box with 6 angstrom per side.
cp2kkit generate-input water.xyz -o water-opt.inp --periodic NONE \
  --run-type GEO_OPT --dispersion d3bj --vacuum 6

# Preserve source cell/PBC, not the original method/charge/spin.
cp2kkit generate-input solid.extxyz -o solid.inp --run-type CELL_OPT \
  --scf diag --kpoints 3 3 3 --smearing 300 --added-mos 30 --trajectory-format EXTXYZ

# Override orthorhombic lengths in angstrom; charge +1 and doublet.
cp2kkit generate-input radical.xyz -o radical.inp --periodic NONE \
  --cell 20 20 20 --charge 1 --multiplicity 2 --functional BLYP

# Verify local data names and hashes; D3 also requires dftd3.dat.
cp2kkit generate-input water.xyz -o checked.inp --periodic NONE \
  --data-dir /path/to/cp2k/data

cp2kkit generate-input --help
```

Ordinary generation writes `<output>` only by default; density bundles additionally
write both fragment inputs and the atom map. JSON is opt-in with `--write-json` or menu
**501**. The in-memory review/manifest remains available even with JSON off.
Existing regular `.inp` (case-insensitive suffix) may be replaced; other existing
outputs, directories, symlinks, original structure and selected data files are
protected. There is no `--force`. Parent directories must already exist.

Input text is staged beside the target, flushed and atomically published. Failed
validation/staging/optional JSON serialization or collision leaves the old input
intact. Optional `<output>.json` remains exclusive (exit 5 if it exists); it is
never overwritten. With JSON off, existing sidecars are left untouched and warned
as potentially stale. This changes input-generation defaults only, not analysis,
structure-export or cube/plot output protections. No multi-file power-loss atomicity
is promised.

## Fixed atoms (0.2.8)

Main-menu **9. Fixed atoms** appears for GEO_OPT/CELL_OPT only. Selecting it
shows 1-based atom indices, elements and Cartesian positions [angstrom] from the
currently loaded frame/expanded structure. Enter `1,3-5,8` or space-separated
entries; `off`, `none` or `0` clears, Enter keeps, `back` abandons the edit.
Ranges must ascend and must not duplicate/overlap. The default is off.
This first subset fixes all XYZ components; per-component selectors, element
selectors and Multiwfn's optH shortcut are not implemented.

```bash
cp2kkit generate-input slab.extxyz -o slab-opt.inp --run-type GEO_OPT --fixed-atoms '1,3-5,8' --trajectory-format EXTXYZ
```

Explicit selections add this section inside MOTION, alongside GEO_OPT/CELL_OPT
and PRINT, not inside an optimizer subsection:

```text
  &CONSTRAINT
    &FIXED_ATOMS
      COMPONENTS_TO_FIX XYZ
      LIST 1 3 4 5 8
    &END FIXED_ATOMS
  &END CONSTRAINT
```

CP2K fixes **fractional** coordinates. With a fixed cell this fixes atom positions;
during CELL_OPT those atoms can move in Cartesian space with the changing cell.
This is not an absolute-Cartesian pinning implementation. The review and warnings disclose the distinction; generated inputs omit explanatory
comments except for generator/Multiwfn header citations. Fixing every atom is permitted with a warning,
not treated as evidence of optimized geometry.

Active nonempty constraints are keyword-checked only for target **2026.2**.
Out-of-bounds active indices fail before writing or replacing any input. Ranges
remain compact until checked against the actual atom count, avoiding huge
unchecked expansion. LIST is emitted in repeated lines of at most 20 indices.

Indices refer to the selected XYZ frame / symmetry-expanded CIF / generated
atom order, never CIF site labels or split KIND labels. No atom is reordered.
Source/header/POSCAR constraints are not inherited. Changing structure/frame
retains the selection and warns to review it; no identity remapping or clearing
is performed. ENERGY/ENERGY_FORCE hide and retain selections but emit no
constraints; inactive bounds are checked when optimization is enabled again.

CLI, menu, config/replay, full preview, and optional JSON share the generator.
`InputSettings.fixed_atoms` is compact text (default `'off'`), normalized
deterministically; the manifest's `constraints` object records the active atom
indices and fractional XYZ semantics. Old configs without the setting stay
unconstrained. No CP2K execution or convergence guarantee is implied.

## Restart hints and optimization output (0.2.7 follow-up)

Updated within retained **0.2.8**: generated inputs retain only the opening
generator/Multiwfn comments and citations. Explanations remain in review/docs/JSON.
The commented SCF_GUESS and WFN_RESTART_FILE_NAME templates are removed, not
uncommented; no restart read is enabled. CP2K's guess default applies (ATOMIC in
the inspected source). Filename suggestions remain metadata/review only.

All tasks now emit the following within DFT/SCF:

```text
      &PRINT
        &RESTART
          BACKUP_COPIES 0
        &END RESTART
      &END PRINT
```

This suppresses SCF wavefunction restart backups (.wfn at Gamma, .kp otherwise),
not restart writing. To suppress wavefunction writing, manually use RESTART OFF
only when intended; that is not the generated default. No cadence/name override
or automatic reuse of existing wavefunctions is introduced.

The name follows the actual **PROJECT**, not a separately selected input-output
basename. Gamma uses `PROJECT-RESTART.wfn`; non-Gamma k-points use
`PROJECT-RESTART.kp`, matching the inspected CP2K writers and Multiwfn templates.
To restart manually, first verify file compatibility with the system, electron
model, basis and spin, then explicitly add WFN_RESTART_FILE_NAME in DFT and
SCF_GUESS RESTART in SCF. No restart is searched, read or modified by generation.
The naming rule assumes the generated single FORCE_EVAL/default restart print names;
it is not evidence that a wavefunction file exists or was written successfully.

GEO_OPT and CELL_OPT now write `TRUST_RADIUS [angstrom] 0.2` in the selected
`&BFGS` or `&LBFGS` subsection. Use `--trust-radius 0.15` or main-menu
**403** to change this positive finite radius. CG does not use this setting;
its hidden value is retained. This is an explicit starting value referenced to
Multiwfn, not a claim of optimality or CP2K's default: the inspected local BFGS
default is 0.25 angstrom and LBFGS defaults to a disabled radius.

Main-menu **-5** / `--trajectory-format pdb|xyz|extxyz` selects optimization
position output (case-insensitive in CLI/menu; stored as PDB/XYZ/EXTXYZ). The
default is XYZ for both tasks; unlike Multiwfn's task-switching reset, changing
to CELL_OPT does not silently select PDB. XYZ loses cell information, PDB has
limited coordinate precision, and EXTXYZ is checked only for target 2026.2.
Prefer EXTXYZ when preserving changing cell vectors matters. Unsupported older
target + active EXTXYZ output is rejected, without changing the selection.

Both optimization tasks append:

```text
  &PRINT
    &TRAJECTORY
      FORMAT XYZ
    &END TRAJECTORY
    &RESTART
      BACKUP_COPIES 0
    &END RESTART
  &END PRINT
```

This is inside MOTION, after GEO_OPT/CELL_OPT. Backup count 0 disables backup
copies of the **MOTION restart**, not restart writing. The separate SCF block
above suppresses wavefunction backups too. Archive existing results before executing in a reused directory; cp2kkit
does not execute the input or change any existing restart/wavefunction file.
No custom trajectory cadence or filename is imposed. ENERGY/ENERGY_FORCE omit
MOTION; hidden format/radius preferences remain in settings and replay commands.

NGRIDS now follows Multiwfn's explicit branch: emit 5 only for non-SR
TZVP/TZV2P/TZV2PX-MOLOPT-GTH (upstream ibas 3/4/5). Other bases, including
SR, UZH and AE, omit the keyword; metadata records null, not a guessed runtime
default. With element overrides, any effective matching basis triggers 5;
a completely overridden global choice does not. Custom aliases are not inferred
from name substrings. This supersedes the earlier universal-five-grid policy.

Every OT block explicitly emits ALGORITHM: STRICT for PP, IRAC for all AE bases,
including auto/native profiles. Manual menu 324 / --ot-algorithm overrides win;
diagonalization hides/retains the request and emits no OT block. The all-AE IRAC
rule is the user's explicit policy, broader than Multiwfn's pob-only IRAC branch.
Static checks and synthetic tests are not native acceptance or convergence proof.

## D3 parameter filenames (0.2.7)

Use `PARAMETER_FILE_NAME dftd3.dat`, without wrapping this whole-line filename
in quotes. The inspected local CP2K lchar_t parsing/chunk-joining path can produce
leading blanks for a quoted filename even when the text inside the quotes has
none. This is not an SCF, OT or AE convergence issue. Default and explicit data-dir
filenames use a dedicated whole-line serializer. The inspected BASIS_SET_FILE_NAME
and POTENTIAL_FILE_NAME definitions are also whole-line strings, so both now use
the same unquoted serializer. Literal internal spaces are kept;
leading/trailing whitespace and #/! comment markers are rejected, not silently
removed. Choose an unambiguous data location for rejected filenames. Existing
calculation results remain protected; generated regular .inp replacement is allowed
only under the policy above. Do not reuse an old calculation's result directory
without reviewing restart/checkpoint behavior.
Static source and synthetic regression checks are not native execution evidence.

## Categorized input-generation menu (0.2.9)

```bash
cp2kkit generate-input --tui
cp2kkit generate-input --interactive
cp2kkit generate-input water.xyz -o water-opt.inp --periodic NONE \
  --run-type GEO_OPT --dispersion d3bj --electron-density --tui --plain
cp2kkit generate-input   # Both streams must be TTY.
```

Menu layout **v1** shows compact common shortcuts and **unexpanded category
entrances**, not every advanced setting on the main menu. Type a category number
to browse its applicable implemented entries, or a full function ID directly.
For example, `100` lists electronic settings; `101` immediately edits total charge.
Categories show full numbers (101, 102), not another local 1/2 numbering layer.

| Entrance | Implemented scope |
|---:|---|
| 100 | Charge/spin, functional, dispersion, U, explicit method assertions |
| 200 | Source/frame, cell/PBC, basis/overrides, data and custom aliases |
| 300 | Cutoffs, SCF threshold/limits, k-points, OT algorithm, occupations |
| 400 | Optimizer/steps/radius, fixed atoms, CELL_OPT pressure |
| 500 | JSON, output path, PROJECT, target version, trajectory, read-only summary |
| 600 | Electron/spin density, two-fragment difference inputs, cube stride |

Only applicable categories/children appear. The implemented registry is
`src/cp2kkit/menu_registry.py`; [the allocation guide](menu-numbering-draft.md)
contains the complete current migration and separately labeled future reservations.
There are no empty 700-1000 placeholder menus. Existing common shortcuts remain:
-7 PBC, -5 trajectory, -3 density, -1 task, 1 functional, 2 basis, 3 dispersion,
4 SCF, 6 smearing, 8 k-points, 9 fixed atoms, 10 optimizer, 12 pressure.
They and full IDs share one setting, validator and editor.

Important migrated IDs: charge/multiplicity 101/102, magnetism 103, functional 110,
dispersion 111, **DFT+U 112**, approvals 113/114, basis 220, overrides 221,
GAPW profile 225, cutoffs 301/302, EPS_SCF 303, k-points 310, SCF 320,
limits 321/322, **OT ALGORITHM 324**, smearing 340, **ADDED_MOS 341**,
optimizer/steps/radius 401/402/403, fixed atoms 420, pressure 430, JSON 501,
path/project/version 502/503/504, trajectory 510, summary 550,
electron density 601, difference inputs 602, spin density 603, stride 605.
Old 100+ numeric TUI scripts must migrate: old 112 ADDED_MOS is **not** accepted
as an alias of new 112 DFT+U. Semantic CLI/config/replay names and immutable
basis registry v1 numbers do not change.

- For all tasks, main-menu `0` validates and writes directly, without a settings
  review or y/yes prompt. Main-menu `w` retains review and explicit y/yes
  confirmation. Both use the same writer and produce the same files/settings.
  Category `0`/`back`/`-10` returns to the generator main menu without writing;
  category `w` explains that writing requires the main menu.
- Parameter Enter keeps; `back` abandons the current edit. Zero remains a value,
  except in the basis chooser and navigation contexts. Basis numbers and atom
  indices are not function IDs; function routing never intercepts value prompts.
- `s`/`f` remain source/frame shortcuts (201/202); invalid replacements preserve
  the old source. Automatic output follows source stem until explicitly overridden.
- Output path, PROJECT and target version now also have category editors.
  231/232 accept JSON lists of explicit file paths. 233/234 edit file/real-alias
  pairs transactionally; back abandons the pair and auto clears it. These controls
  do not select custom basis 900 automatically.
- Direct access uses the same applicability rules as category rendering. Hidden
  settings are retained, not reset. Inapplicable direct requests explain the
  conflict without switching task, SCF, electron model or PBC.
- `r` reviews; `p` adds all input previews and a replay command. Neither writes.
  Both return to the originating menu. 550 is a read-only review entrance.
- Enter defaults to no at confirmation. Collision/I/O recovery offers another path.
  Ordinary single-input generation alone may replace a regular .inp; **602
  bundles require entirely new targets**. Sources/data/results remain protected.
- Type/range errors retry locally. Shared scientific validation retains invalid
  drafts with warnings; no charge/spin/SCF/PBC repair or index identity remapping.
- Successful generation returns immediately to the parent application menu (or
  finishes a standalone generation command), without an extra Enter prompt.
- Generator-main `-10`/`back`/`cancel` cancels generation; q/EOF exits the session.
  Ctrl+C cancels. Completed outputs remain intact.

Optional Rich has a standard-library fallback; `--plain`/`NO_COLOR` disables styling.
Scrolling text folds without clearing/redrawing the screen. Complete batch calls
stay noninteractive; both streams must be TTY for menus. Schema stays 0.1.0.

## Two-fragment density-difference inputs (0.2.9)

602 is input preparation, not a CP2K run or cube subtraction. Initial scope:
**ENERGY, GPW pseudopotential valence electron-number density, exactly two
complementary nonempty fragments, charge-conserving partition**.

```bash
# Syntax example: atom selection and fragment states must fit the actual system.
cp2kkit generate-input AB.extxyz -o AB-density.inp --density-difference \
  --fragment-a-indices '1-12,15' \
  --fragment-a-charge 0 --fragment-a-multiplicity 1 \
  --fragment-b-charge 0 --fragment-b-multiplicity 1 \
  --cube-stride 1 1 1 --write-json
```

Whole-system charge/multiplicity remain --charge/--multiplicity (101/102).
The default charge is 0 (not inherited from the source). When multiplicity is
omitted, use 1 for an even explicit-electron count and 2 for an odd count,
using the selected PP valence/AE electron model and subtracting charge.
An explicit multiplicity is preserved and validated, never repaired automatically.
Menu 102 accepts `auto` to restore parity selection; the menu shows its effective
value. Generated input/JSON records the resolved integer. This is only a minimal
parity-compatible default, not a ground-state spin prediction. The six-integer
602 electronic-state entry and both fragment states still require explicit values.
All four fragment charge/multiplicity values must be explicitly supplied, including
zero and singlet; missing values are null, not inferred neutral singlets.
Require Q_whole = Q_A + Q_B and valid positive electron counts/parity in each
component. Fragment spins need not add to the whole spin. Zero-electron fragments
are outside the current generator subset. Charged fragments warn about reviewing
boundary/background treatment; no electrostatic correction is inferred.

Select A by 1-based loaded/frame/symmetry-expanded **whole** indices; B is the
complement. Relative order is preserved. Bounds precede expansion. Source changes
retain selections and warn to review them; no automatic molecule recognition,
identity remapping, source charge/spin inheritance, or arbitrary fragmentation.

602 has explicitly local options: 1 enable, 2 select A (direct index entry, no atom listing),
3 inspect B/mapping, 4 enter all three electronic states, 5 review, 0 return. None publishes.
Option 1 toggles immediately between True and False without a second prompt.
With automatic output naming, enabling CDD changes the suggestion to
`<source-stem>-CDD.inp`; disabling restores `<source-stem>.inp`. Loading another
source updates the suggestion with the same rule. Explicit output paths (CLI -o,
menu 502 or collision recovery) are preserved. Existing CDD bundles remain
protected; the suffix is not an automatic overwrite or unique-run counter.
After returning to the generator main menu (and leaving any category), `0`
directly writes the enabled CDD bundle. Invalid settings or collisions still fail
without replacing existing files. This does not print a configuration JSON;
a JSON sidecar is written only when explicitly enabled via 501/--write-json.
Option 4 accepts six whitespace-separated integers in one line:
`all_charge all_multiplicity A_charge A_multiplicity B_charge B_multiplicity`.
For example, `0 1 0 1 0 1` sets three neutral singlets;
`-1 1 1 1 -2 1` sets the whole system to -1, A to +1 and B to -2,
all singlets. This also updates the shared total charge/multiplicity (101/102).
All multiplicities must be positive and charges must conserve the total.
Malformed input leaves all six values unchanged and retries; Enter keeps and
back abandons the edit. Component electron-count/parity checks still apply at review/generation.
In the editor, enabling 602 automatically turns on electron-density cube output
and updates the shared -3/601 display. While CDD is enabled, -3/601 cannot disable
that output; disable CDD first. Disabling CDD retains the enabled density request.
CLI/API bundle generation also forces effective density output for all components,
regardless of the raw global density toggle.

Main-menu **-3** and **601** share a Multiwfn-style numbered cube selector,
limited to implemented types: **0 None**, **1 Electron density** (UKS also prints
spin density). Selecting 0 clears both electron/spin requests; Enter keeps and
back returns unchanged. Other Multiwfn cube types are not offered.

The shared generator resolves the whole-system box/translation **once**, then
extracts subsets of its generated geometry. Cell, PBC, origin convention, geometry,
functional, dispersion, cutoff/rel_cutoff, k-points, SCF and stride are common.
Derived automatic SCF limits/ADDED_MOS are resolved once from the whole system.
When the whole effective basis policy emits NGRIDS 5, lock that value for both
fragments, even if one subset alone would omit it; otherwise all three omit it.
This workflow-specific common-grid lock is recorded, not a new general grid default.
Actual CUBE grids **must still be checked before subtraction**.

Corresponding per-element basis/potential names, selected files and source hashes
must match the whole system. Per-element overrides/+U/initial moments follow included
atoms; @whole magnetic seeds are explicitly mapped to local indices using the same
atom mapping, and explicit UKS remains enabled even if a fragment has no seeds.
No automatic spin/moment repair. All magnetic/+U version gates remain in force.
UKS density-print channels remain coupled; this is not a spin-difference workflow.
No ghost functions, separate recentering, independent fragment relaxation, new
GAPW density semantics, BSSE treatment, or convergence guarantee is introduced.

For output `AB-density.inp`, publish together:

- `AB-density.inp`: whole-system input.
- `AB-density-fragment-A.inp` / `AB-density-fragment-B.inp`.
- `AB-density-atom-map.csv`: whole index, element, fragment, local index,
  generated x/y/z in angstrom (eight decimals).
- Optional `AB-density.inp.json`: settings, all three complete component manifests,
  source/data hashes, full input texts/hashes, mapping, output paths and warnings.

Output must end in .inp; parent directory must already exist. Component PROJECTs
derive from the whole PROJECT with unique -fragment-A/-fragment-B suffixes.
Existing input/map/JSON/symlink/directory collisions fail without replacement.
Same-directory staging and exclusive publication roll back only this operation's
published inodes on ordinary errors/interrupts; **not a crash-atomic transaction**.
JSON off does not delete an existing sidecar; a stale-sidecar warning is returned.
No existing CUBE, wavefunction, restart or result is touched or reused.

After independently running and checking the three inputs, use
`cube-diff whole.cube A.cube B.cube -o delta.cube`. The expression is
n_whole - n_A - n_B: positive means electron accumulation, not positive electric
charge. Integrals are not fragment net charge transfer. See [cube checks](cube.md).

## Scope and defaults

| Setting | Support/default |
|---|---|
| Structure | `.xyz`/`.extxyz`/text `.restart`/`.gjf`/`.com`/`.cif`/POSCAR/CONTCAR/`.vasp`/`.poscar`; XYZ last frame |
| Task | ENERGY (default), ENERGY_FORCE, GEO_OPT, CELL_OPT |
| Method | Quickstep/GPW; PBE (default), BLYP; target 2026.2 adds PBEsol/revPBE/Libxc RPBE |
| Basis | DZVP-MOLOPT-SR-GTH (default); SZV-SR, DZVP/TZVP/TZV2P non-SR; target 2026.2 adds TZVP-SR/TZV2P-SR/TZV2PX and explicit element overrides |
| Potential | Catalog-checked GTH entries with fixed `-qN`; prefer actual matched functional, explicitly approved PBE approximation otherwise |
| Dispersion | none (default), D3, D3(BJ); dftd3.dat and REFERENCE_FUNCTIONAL |
| Charge/spin | Default charge 0; automatic multiplicity: even electrons 1, odd electrons 2; explicit values override; UKS for multiplicity > 1 or explicit magnetic request |
| SCF | OT+FULL_ALL/DIIS+outer SCF (default), or diagonalization+Broyden mixing |
| EPS_SCF | 1e-6 for all tasks, including ENERGY; explicit override allowed |
| SCF limits | OT inner/outer 25/20; diag 128; `--max-scf`/`--max-outer-scf` overrides |
| Grid | CUTOFF 400 Ry/REL_CUTOFF 55 Ry; NGRIDS 5 only for classic non-SR TZVP/TZV2P/TZV2PX, omitted otherwise; no GAPW control overrides |
| k-points | Gamma default; non-Gamma requires XYZ+diag |
| Smearing/empty orbitals | Optional Fermi-Dirac K, requires diag; auto `max(30, NINT(atom_count/2))` with smearing, otherwise 0; OT rejects smearing/nonzero empty orbitals |
| Optimization | BFGS (default), LBFGS, CG; max 400 steps; BFGS/LBFGS TRUST_RADIUS 0.2 angstrom |
| Restart hints | PROJECT-based .wfn/.kp suggestion in metadata/review only; no active guess override |
| Motion output | Optimization only: XYZ (default), PDB, EXTXYZ (target 2026.2); MOTION restart BACKUP_COPIES 0 |
| Fixed atoms | Off by default; 1-based selection, fractional XYZ, target 2026.2; GEO_OPT/CELL_OPT only |
| CELL_OPT | Requires XYZ/lower-triangular cell; analytical stress; default pressure 1.01325 bar |
| Target version | 2026.2 default; common density syntax profiles 2024.1/2/3, 2025.1/2, 2026.1/2; not runtime certification |
| Density cubes | Optional electron/applicable UKS spin density; stride default 1 1 1; final-step policy in [cube guide](cube.md) |
| DFT+U / magnetic seeds | Explicit opt-in, target 2026.2 only; Ueff/L per element, MULLIKEN projectors; collinear UKS/atom seeds with split KIND labels |

SR/PBE presets cover 71 elements:

```text
H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar
K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr
Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba
Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn
```

The original non-SR core is H C N O F Si P S Cl. Target 2026.2 adds UCL Cu for
DZVP and Br for DZVP/TZVP/TZV2P/TZV2PX. BLYP presets still exclude
Nb Tc Cd Sn Hf Ta Re Os Ir Pt Hg Tl Po At Rn; missing entries are rejected.
See the per-family coverage below rather than assuming every family covers all 71.
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
  magnetic state. Explicit collinear magnetic guesses (including opposite-spin
  atoms of one element and UKS singlets) are supported as described below, not
  certified converged states. No noncollinear spin, SOC, local-spin constraints,
  occupation matrices, or automatic magnetic-order search.
- Restart provides **geometry only**: original KIND labels merge by element;
  method/U/constraints/moments/charge/solvent are not inherited. This is a new template,
  not a complete restart of the original job.
- Hybrid/ADMM, MD, frequencies, NEB, TDDFT, solvents, external fields, atomic
  constraints, and other advanced Multiwfn branches are not implemented.
  Electron/spin cubes are supported; potential/ELF/MO cubes are not.
- Default cutoff/basis/vacuum/k-points are not converged for the target system.
  Deprecated CELL_OPT TYPE DIRECT_CELL_OPT is not emitted.

## Functional and basis profiles (0.2.6)

New functional names, new families, UCL coverage extensions and nonempty element
overrides are restricted to target **2026.2**. Existing PBE/BLYP/core basis requests
retain their older target profiles. Defaults remain PBE / DZVP-MOLOPT-SR-GTH,
charge 0 / automatic multiplicity (even electrons 1, odd 2), GPW and no dispersion. No calculation is executed.

### Functional definitions and approval

| CLI/menu name | Actual XC definition | Requirement |
|---|---|---|
| PBE / BLYP | Existing native shortcuts | Unchanged matched GTH presets |
| PBESOL (PBEsol) | PBE with PARAMETRIZATION PBESOL | Prefer matched GTH-PBESOL; explicitly approve PBE where absent |
| REVPBE (revPBE) | PBE with PARAMETRIZATION REVPBE | Explicitly approve PBE where matched entries are absent |
| RPBE | Libxc GGA_X_RPBE + GGA_C_PBE | Explicit target-build Libxc assertion plus potential approval where needed |

RPBE and revPBE are different functionals, not aliases. CLI names are case-insensitive.
The v2026.2 GTH_POTENTIALS catalog contains matched **B GTH-PBESOL-q3**;
that entry is preferred even when approximation approval is enabled. For missing
matches, generation errors until `--allow-pbe-potential` / menu **114** is explicitly
enabled. Every affected KIND records the actual potential and approximation status,
and review warns that this is not a matched-functional potential. No unverified
GTH-RPBE/GTH-REVPBE names are fabricated, and no q values are changed.

RPBE additionally requires `--libxc-available` / menu **113**. This is a user assertion
about the target CP2K build, not probing, installation, a detected Libxc version, or
runtime certification. Native PBEsol/revPBE do not require Libxc in these profiles.
The menu hides 114 outside the new GGA choices and 113 outside RPBE; values remain
retained for later edits. Selecting a functional never automatically grants approval.

All five profiles explicitly allow none/D3/D3(BJ); the new reference identifiers
PBESOL, REVPBE and RPBE were checked in the zero/BJ parameter branches of tagged
CP2K `src/qs_dispersion_utils.F`. The generator emits the actual functional reference,
not PBE as a substitute. D3 parameters remain CP2K's responsibility; no numerical
parameter table is copied. Availability of runtime libraries/data is still unverified.

### Per-element basis catalog and mixed bases

Header-only name/q/file catalogs come from tagged v2026.2 BASIS_MOLOPT,
BASIS_MOLOPT_UCL and GTH_POTENTIALS. No coefficients or potential parameters are bundled.
Counts below use the existing fixed 71-element valence policy and matching PBE q
values; functional-specific potential restrictions still apply.

| Family | Current matching elements | Primary library |
|---|---|---|
| SZV-MOLOPT-SR-GTH / DZVP-MOLOPT-SR-GTH | 71 each, unchanged | BASIS_MOLOPT |
| DZVP-MOLOPT-GTH | 11: original nine plus Cu/Br | BASIS_MOLOPT + UCL where needed |
| TZVP-MOLOPT-GTH / TZV2P-MOLOPT-GTH / TZV2PX-MOLOPT-GTH | 10 each: original nine plus Br | BASIS_MOLOPT + UCL where needed |
| TZVP-MOLOPT-SR-GTH / TZV2P-MOLOPT-SR-GTH | 54 each | BASIS_MOLOPT_UCL |

The new triple-zeta SR families **lack H/C/N/O**. UCL Mg-q2 does not satisfy the
existing Mg-q10 preset; the generator refuses it instead of changing electron counts.
Lanthanide/other q entries in the upstream libraries do not expand the generator's
element/valence policy automatically. No family is an implicit substitute for another.

Use `--basis-overrides 'Element=basis; Element=basis'` or menu **221** for explicit
mixed bases. `off`/`auto` clears overrides. Each selector must be a unique present
element; each family/q must actually exist. Element overrides apply to all of that
element's split magnetic KINDs; source atom order, +U, charge and multiplicity remain
unchanged. Changing the source may invalidate a retained override and will warn,
not clear or repair it.

```bash
# Syntax examples, not validated magnetic states or converged computational settings.
cp2kkit generate-input solid.extxyz -o pbesol.inp --functional PBEsol \
  --allow-pbe-potential --dispersion d3bj
cp2kkit generate-input surface.extxyz -o rpbe.inp --functional RPBE \
  --allow-pbe-potential --libxc-available
cp2kkit generate-input FeO.extxyz -o mixed.inp --basis TZV2P-MOLOPT-GTH \
  --basis-overrides 'Fe=TZV2P-MOLOPT-SR-GTH' --data-dir /path/to/cp2k/data
```

Only actually needed basis libraries are emitted, in deterministic order, using
repeatable BASIS_SET_FILE_NAME. With `--data-dir`, each selected file/header is
checked separately and raw bytes are hashed. An entry in the wrong library or with
a different q cannot satisfy a selection. Registry-v1 actual files are authoritative for an enabled family at the fixed q;
explicit files may supply entries beyond pinned catalog coverage. They do not add
new method templates or change q. Use custom 900 for a literal custom ORB alias.
NGRIDS is emitted as 5 only when an effective basis is classic non-SR
TZVP/TZV2P/TZV2PX-MOLOPT-GTH; otherwise it is omitted. CUTOFF/REL_CUTOFF
remain 400/55 Ry by default, not property-converged values. Larger Gaussian bases,
grid convergence and overlap conditioning are separate checks.

### Evidence and remaining work

`src/cp2kkit/data_catalog.py` contains exact versioned URLs/SHA-256 for inspected
headers, native XC, Libxc registration/wrapper, D3 parameter lookup, and repeatable
basis-file definitions. `method_profile` in JSON records backend, assertions,
basis files, approved approximation elements and those references with
build_verified/runtime_validated=false. Local supplied-file hashes remain separate
from bundled reference-source hashes. Schema stays 0.1.0 with additive fields.

Multiwfn 2026.10.1 outCP2Kinp informed the parametrized-PBE, separated Libxc RPBE,
q-suffix and D3-reference branches; see [provenance](../third_party/multiwfn/PROVENANCE.md).
The UCL header credits Sanliang Ling and Ben Slater, and follows the MOLOPT strategy
of VandeVondele and Hutter, J. Chem. Phys. 127, 114105 (2007),
DOI [10.1063/1.2770708](https://doi.org/10.1063/1.2770708).
Header checks/synthetic round trips are not native CP2K acceptance, converged
energies/forces/stress, recommended bases/U, or validation of an adsorption model.

The registry follow-up enables paired UZH-PBE DZVP/TZVP/TZV2P for target 2026.2
and explicit custom pseudopotential ORB files. r2SCAN/meta-GGAs, hybrids/HF/ADMM,
UZH-PBE0 templates, arbitrary q changes, auxiliary and reserved
families remain unimplemented; see [basis selection](basis-selection.md).

## DFT+U and magnetic initialization (112 / 103)

These are real generator features, not renamed placeholders. They are opt-in and
currently keyword-checked only against CP2K **2026.2**; explicit requests with other
target profiles are rejected rather than presented as verified. These controls
were introduced in 0.2.4 and remain compatible with the 0.2.6 method/basis profiles. Schema 0.1.0 retains the
additive settings/extension metadata.

- **112 — DFT+U:** enter `Element:L:Ueff_eV`, separated by semicolons.
  `L=0/1/2/3` means s/p/d/f; Ueff is finite, nonnegative, in eV, and equals U-J.
  `off`/`auto` clears the correction. One entry per present element is supported.
  No element-specific U values or orbital channels are guessed.
  The generator writes `DFT/PLUS_U_METHOD MULLIKEN` and active
  `SUBSYS/KIND/DFT_PLUS_U` sections with `L` and `U_MINUS_J [eV]`.
  User-selected U/L must be justified for the functional, basis and projector
  definition; no native runtime/shell-suitability validation has been performed.
- **103 — magnetic initialization:** `uks` explicitly enables UKS without local seeds;
  `Element=moment; @index=moment` enables UKS and supplies atomic initial guesses.
  `auto` (also `off`/`none`) clears explicit magnetic requests and restores the
  original multiplicity-based UKS rule; it does not force RKS when multiplicity > 1.
  The edit prompt shows loaded atoms with **1-based indices and angstrom coordinates**.
  These indices follow expanded structure/selected-frame order, not CIF site labels.
- Element requests apply first; explicit `@index` overrides apply second. Signed
  values and zero are retained; selectors must be unique, present and finite.
  Moments are initial alpha-minus-beta electron numbers, with magnitude no greater
  than the preset explicit valence count, not fixed local moments.
- Different initial moments on one element produce separate generated KIND labels
  (`Fe_m1`, `Fe_m2`, etc.) and matching COORD labels. No atom reordering occurs.
  Basis/potentials retain the actual ELEMENT; element-specific +U is copied to
  all split kinds of that element. Unassigned atoms retain default initial guesses.
  Source KIND labels/moments are not inherited.
- Explicit magnetic requests may enable a UKS singlet, but **never change total
  charge or multiplicity**. The existing electron/parity check still applies.
  A requested-moment sum different from MULTIPLICITY-1 is warned about, not repaired.
  Local moments may change during SCF; initial seeds do not certify FM/AFM stability.
  UKS spin-density output and two-spin ADDED_MOS also apply to explicit UKS singlets.
- Old menu cell/data-directory entries are removed; `--cell` and `--data-dir`
  remain CLI/API controls. The new flags are `--dft-plus-u` / `--magnetism`:

```bash
# Syntax example ONLY; these U/moment values are not recommendations.
cp2kkit generate-input Fe2O2.extxyz -o Fe2O2-afm.inp \
  --dft-plus-u 'Fe:2:4.0' --magnetism 'Fe=4; @2=-4' --multiplicity 1
```

No U ramping, independent U/J, LOWDIN selection, constrained occupations, or
noncollinear magnetism is implemented in these controls. Without explicit requests,
the previous input-text defaults remain unchanged; provenance records raw requests.
Reviewed keyword sources:
[DFT_PLUS_U](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/SUBSYS/KIND/DFT_PLUS_U.html),
[KIND/MAGNETIZATION](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/SUBSYS/KIND.html),
[DFT/UKS and PLUS_U_METHOD](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT.html).

## Electron/spin density output

```bash
cp2kkit generate-input AB.extxyz -o AB-density.inp --project AB \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1
```

Without a request, no density PRINT is added. `--spin-density` requires current
UKS eligibility (multiplicity > 1 or an explicit magnetic request). CP2K's E_DENSITY_CUBE controls both fields,
so both are written under UKS. Routine optimization frequency is 0; ADD_LAST
NUMERIC requests the final recognized step, not proof of convergence or a guarantee
of output after abnormal termination. Frequencies/files/GPW valence meaning and
older-version differences are in the [cube guide](cube.md).

## Generated text formatting

- EPS_DEFAULT and inner/outer EPS_SCF use uppercase scientific notation, e.g.
  `1.0E-12`/`1.0E-06`. EPS_DEFAULT/EPS_SCF defaults are ENERGY 1e-11/1e-6, other tasks
  1e-12/1e-6. The uniform SCF default supersedes the earlier Multiwfn-derived
  ENERGY 5e-6 policy within retained version 0.2.8; explicit overrides still win. Custom EPS retains float significant digits, not a fixed one-decimal rounding.
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

Registry-v1 checks actual selected-entry basis/GTH payload structure, aliases and
q from explicit files, `--data-dir`, or the CP2K_DATA_DIR environment directory,
recording full-byte hashes and resolved paths. D3 also records dftd3.dat when a
local data directory is used. Unknown source versions remain null, not inferred
from filenames. With no actual files the result is an unverified template; even
`data_checked` is not whole-library validity, verified physical pairing or native
CP2K acceptance. Record the executed binary/version in subsequent authorized runs.

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
