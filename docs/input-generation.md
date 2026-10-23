# CP2K input generation

This guide describes cp2kkit **0.3.5**. Older defaults and migration notes are in
[the changelog](../CHANGELOG.md). AE automatic setup is described in
[the basis guide](basis-selection.md#all-electron-automatic-setup-027).
The [registry-v1 basis guide](basis-selection.md) defines permanent numbering toward
1.0.0, data requirements, UZH protocols, custom 900 and explicit migration from
legacy list positions; it does not claim a 1.0.0 release or native validation.

`generate-input` is an explicit write entry point added beyond the read-only MVP;
it neither submits nor runs calculations. It is a Python GPW/GAPW/GFN-xTB subset developed
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

DFT active nonempty constraints are keyword-checked only for target **2026.2**.
The 0.3.1 xTB branch has target-specific references for checked releases
2024.2-2026.2; see [the xTB version matrix](#gfn-xtb-methods-031).
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
| Method | Quickstep/GPW; 15 non-hybrid profiles plus six direct-HFX hybrid profiles at target 2026.2; per-profile limits below; PBE default |
| Basis | DZVP-MOLOPT-SR-GTH (default); SZV-SR, DZVP/TZVP/TZV2P non-SR; target 2026.2 adds TZVP-SR/TZV2P-SR/TZV2PX and explicit element overrides |
| Potential | Catalog-checked GTH entries with fixed `-qN`; prefer actual matched functional, then standard hybrid family (B3LYP: BLYP; other hybrids: PBE); other unmatched profiles require explicit PBE approval |
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
- Hybrids beyond the six bounded profiles, ADMM/RI-HFX beyond PBE0/HSE06, their combination,
  MD, frequencies, NEB, TDDFT, solvents, external fields, richer
  constraints beyond fixed atoms, and other advanced Multiwfn branches are not implemented.
  Electron/spin cubes are supported; potential/ELF/MO cubes are not.
- Default cutoff/basis/vacuum/k-points are not converged for the target system.
  Deprecated CELL_OPT TYPE DIRECT_CELL_OPT is not emitted.

## Direct-HFX hybrids (0.3.2)

PBE0 → HSE06 → B3LYP are implemented through the same generator, not an external
executable or a second input writer. Version **0.3.3** extends this shared path
with BHandHLYP, M06-2X and configurable PBEh. Target **2026.2** only;
arbitrary XC mixtures remain unsupported.

| Capability | Initial hybrid scope |
|---|---|
| Tasks | ENERGY, ENERGY_FORCE, GEO_OPT; no CELL_OPT/stress |
| Electronic model | GPW, classic MOLOPT/UCL orbital bases and fixed-q GTH potentials |
| Spin | RKS, UKS (explicit multiplicity or magnetic seeds); no automatic spin change |
| Boundary | NONE or XYZ; source PBC/cell preserved; low-dimensional PBC rejected |
| k-points / SCF | Gamma only; OT or diagonalization; no smearing |
| Dispersion | PBE0/HSE06/B3LYP: none/D3/D3(BJ); M06-2X: none/D3 (reference M062X); BHandHLYP/PBEh: none only |
| Density | Existing GPW electron/spin cubes and explicit whole/A/B CDD inputs; reference states and actual cube-grid compatibility still need validation |
| Excluded | GAPW/AE, +U, UZH-PBE0/custom orbital protocols, non-Gamma, correlated methods; ADMM and RI-HFX are separately opt-in for PBE0/HSE06 only, not together |

`FUNCTIONALS` retains the original 15 entries, then PBE0/HSE06/B3LYP,
then BHANDHLYP/M06-2X/PBEH (canonical IDs; names are case-insensitive).
The method chooser **1/110** uses local positions **16/17/18** (not a claim of
Multiwfn number equivalence), then **19/20/21** for the added profiles;
xTB remains **30/31/32**. Menu **120** edits the three direct-HFX numerical
controls in sequence (MAX_MEMORY hidden for RI), followed by the HF fraction for PBEh only. **121** edits the bounded RI-HFX subset;
**122** explicitly enables the bounded ADMM subset below. Neither ADMM nor
RI-HFX is enabled by selecting a hybrid. Basis IDs are unchanged;
UZH-PBE0 30-32 remain unavailable pending their own paired-data/protocol audit.

### Complete XC/HF definitions

The first three definitions use native CP2K XC without a Libxc assertion.
BHandHLYP and M06-2X require `--libxc-available` (menu **113**). HFX requires a suitable Libint-enabled target build; this
tool neither probes nor certifies the build.

| Profile | Semilocal XC | HF |
|---|---|---|
| PBE0 | PBE SCALE_X=0.75, SCALE_C=1.0 | FRACTION=0.25 |
| HSE06 | XWPBE SCALE_X=-0.25, SCALE_X0=1.0, OMEGA=0.11; PBE SCALE_X=0.0, SCALE_C=1.0 | FRACTION=0.25, SHORTRANGE OMEGA=0.11 |
| B3LYP | LYP SCALE_C=0.81; BECKE88 SCALE_X=0.72; VWN FUNCTIONAL_TYPE=VWN3, SCALE_C=0.19; XALPHA SCALE_X=0.08 | FRACTION=0.20 |
| BHandHLYP | Libxc HYB_GGA_XC_BHANDHLYP (already includes semilocal mixing) | FRACTION=0.50 |
| M06-2X | Libxc HYB_MGGA_X_M06_2X + MGGA_C_M06_2X (no extra scaling) | FRACTION=0.54 |
| PBEh | PBE SCALE_X=(1-A), SCALE_C=1.0 | FRACTION=A, explicit 0 < A <= 1 |

HSE06's ω is **0.11 bohr⁻¹**, consistently in both XC and HF. B3LYP deliberately
uses **VWN3**, matching the inspected Multiwfn/Gaussian convention, not the native
B3LYP shortcut's implicit variant. Do not compare different B3LYP definitions as
though they were identical. Fractions and ω are method definitions, not exposed
tuning controls except for the separate PBEh family. PBEh requires explicit
`--pbeh-fraction A` (dimensionless, not percent), with no inferred default.
Zero HF is deliberately outside this hybrid path: select PBE instead.
A retained PBEh fraction fails on any other DFT/xTB method until explicitly
reset (API/config null; TUI PBEh menu 120 auto). XC, HF and manifest use one
resolved profile; no Libxc coefficient or HF contribution is double-counted.
M06-2X uses kinetic-energy density; retained 400/55 Ry cutoffs are not grid
convergence evidence. BHandHLYP/PBEh extra dispersion remains blocked:
no unverified BHLYP alias or fixed-fraction D3 parameter is assumed.

### Interaction operator, radius and resources

- Isolated global hybrids: explicit **COULOMB**, no radius or truncated-gamma table.
- XYZ global hybrids: explicit **TRUNCATED**. Auto radius:
  `min(6 angstrom, minimum cell face spacing / 2.01)`, referencing Multiwfn.
  Perpendicular face spacings, not cell-vector lengths, handle skew cells;
  bounds use the cell rounded to the actual emitted eight decimal places.
  This is a finite-cell HFX approximation, not convergence evidence.
- Override with `--hf-cutoff-radius R` [angstrom]. Require strictly less than half
  the minimum face spacing; reject invalid values without clipping or enlarging
  the cell. A radius request on isolated hybrids or HSE06 fails explicitly.
- HSE06: **SHORTRANGE** with ω=0.11. Omit CUTOFF_RADIUS; CP2K derives the
  short-range numerical cutoff from ω and EPS_SCHWARZ.
- `--hf-eps-schwarz`: finite 0 < threshold < 1; default **1e-6**.
- `--hf-memory`: positive integer **MiB per MPI process**, default **512**.
  This follows CP2K's native memory default, not Multiwfn's 3000 setting. It is
  an HFX budget, not the total process memory or a scheduler allocation.
- Explicit **SCREEN_ON_INITIAL_P F**, unlike upstream's restart-dependent T.
  EPS_STORAGE_SCALING is fixed at **0.1**; no wavefunction restart is required.
- Nondefault HF controls on pure DFT or xTB fail until explicitly reset; hidden
  requests are retained, not silently applied to an unrelated method.

Periodic global hybrids need **t_c_g.dat** for truncated-gamma evaluation.
With `--data-dir` (or CP2K_DATA_DIR), require the file, record absolute path,
raw-byte SHA-256/size in `data_sources.hfx_truncated_gamma`, emit T_C_G_DATA,
and protect it from output replacement. T_C_G_DATA is a single char_t token:
paths containing spaces are quoted, unlike whole-line basis/kernel filenames.
Without a data directory, emit the
basename and warn that CP2K must resolve it at runtime. Byte checks do not
validate the numerical table. HSE06/isolated global hybrids do not require it.

Since 0.3.2, actual matched hybrid potential entries are preferred if supplied;
otherwise **B3LYP uses GTH-BLYP**, and **the other five hybrids use GTH-PBE**
as standard semilocal-family choices, matching the inspected Multiwfn branches.
These family choices do not
require `--allow-pbe-potential` / **114**. If the required family/q entry is
missing, fail without crossing families, changing q, or inventing labels (even
when PBE approximation approval is enabled). Other functional approval policies
are unchanged. `potential_functional` records the actual family, and
`potential_approximation=true` still distinguishes it from an exact-hybrid
potential; the warning identifies automatic family selection, not user approval.
Real file names, q and hashes stay in existing KIND/source provenance.

```bash
cp2kkit generate-input water.xyz -o water-pbe0.inp --periodic NONE \
  --functional PBE0 --write-json
cp2kkit generate-input solid.extxyz -o solid-hse06.inp \
  --functional HSE06 --hf-memory 1024
cp2kkit generate-input solid.extxyz -o solid-pbe0.inp \
  --functional PBE0 --hf-cutoff-radius 5 \
  --hf-eps-schwarz 1e-7 --data-dir /path/to/cp2k/data
cp2kkit generate-input water.xyz -o water-b3lyp-opt.inp --periodic NONE \
  --functional B3LYP --run-type GEO_OPT
cp2kkit generate-input water.xyz -o water-m062x.inp --periodic NONE \
  --functional M06-2X --libxc-available --dispersion d3
cp2kkit generate-input water.xyz -o water-pbeh.inp --periodic NONE \
  --functional PBEh --pbeh-fraction 0.45
```

The existing staged .inp/optional exclusive JSON writer and CDD bundle collision
rules are reused. Source checks and synthetic section/coefficient/CLI/TUI/replay/
protection tests are not native syntax acceptance, derivative accuracy,
convergence or scientific validation. **No CP2K run or submission in this round.**

References: CP2K v2026.2
[input_cp2k_xc.F](https://github.com/cp2k/cp2k/blob/v2026.2/src/input_cp2k_xc.F),
[input_cp2k_hfx.F](https://github.com/cp2k/cp2k/blob/v2026.2/src/input_cp2k_hfx.F),
[xc_xwpbe.F](https://github.com/cp2k/cp2k/blob/v2026.2/src/xc/xc_xwpbe.F),
[xc_vwn.F](https://github.com/cp2k/cp2k/blob/v2026.2/src/xc/xc_vwn.F),
[hfx_derivatives.F](https://github.com/cp2k/cp2k/blob/v2026.2/src/hfx_derivatives.F)
and [qs_dispersion_utils.F](https://github.com/cp2k/cp2k/blob/v2026.2/src/qs_dispersion_utils.F).
Exact inspected hashes are in hybrid.py and [feature provenance](../third_party/multiwfn/PROVENANCE.md).
The derivative path was inspected, not numerically validated.

## Hybrid returned-run hardening (0.3.5)

These fixes change hybrid deployment/output text, not the selected physical model.
They apply to newly generated inputs; existing inputs, outputs, wavefunctions and
submission records are not modified or resubmitted.

- Automatic hybrid ORB/AUX_FIT and potential files use short runtime filenames
  when the corresponding basename in the selected data root resolves to the
  checked source. Explicit `--basis-file`, `--aux-basis-file` and
  `--potential-file` overrides retain their paths; files outside that root are
  not blindly rebased. Existing UZH aliases remain unchanged. Absolute source
  paths/hashes remain in provenance and publication protection. Pure-DFT and
  xTB filename policies are unchanged.
- `T_C_G_DATA` always emits `t_c_g.dat`, avoiding the native char_t 80-character
  limit. A supplied data root still requires the readable source and records its
  absolute path/hash. On the execution machine, set **CP2K_DATA_DIR** to matching
  data or stage matching files in the actual run directory. Short names do not
  certify the contents of another machine's libraries.
- Hybrid **ENERGY_FORCE** explicitly enables **FORCE_EVAL/PRINT/FORCES ON**, with
  FILENAME __STD_OUT__ and FORCE_UNIT hartree/bohr. The target-2026.2 default
  print threshold is HIGH, so retaining GLOBAL PRINT_LEVEL LOW alone had hidden
  the vectors despite force computation. ENERGY/GEO_OPT and non-hybrid print
  policies are unchanged; global verbosity is not raised.
- Periodic HSE06 preflight estimates the initial HFX range by solving
  erfc(omega*r)/r = EPS_SCHWARZ in bohr and compares with half the minimum
  perpendicular spacing of the rounded emitted cell. It warns, never resizes
  the cell or changes omega, screening or an exchange cutoff. The estimate is
  source-derived, **not runtime-observed**; RI may extend the range further.
  An independent TRUNCATED RI metric radius does not fix this exchange range.

### Returned native evidence and limits

User-returned water tests identify CP2K **2026.2, git:c92cc08**, with GPW
DZVP-MOLOPT-SR-GTH/GTH-PBE, 400/55 Ry grids, EPS_SCF=1e-6 and 16 Angstrom cells.
Neutral singlets and charge +1 doublets were tested; charged XYZ is a software
smoke model, not an ionization benchmark. All 71 refreshed, input-hash-matched
outputs have SCF-converged energy records and PROGRAM ENDED, but **all 71 stderr
files report SIGSEGV with _dl_fini frames**. This includes direct HFX as well as
RI, so no RI-only cause or responsible library is established. One direct-HFX
reference is still an old absolute-path failure, not a new-input failure.

All 16 GEO_OPT cases report optimization convergence. All 24 ENERGY_FORCE cases
have force-computation timing entries, but no atom-resolved vectors were retained;
force accuracy/finite differences remain unverified. Thirty available RI/direct
pairs give positive total-energy differences of approximately 1.103-1.868 mHa
(1 mHa = 0.001 hartree) with AUTO_BASIS MEDIUM and optional independent RI radius
1.7 Angstrom. These are provisional pre-crash observations, not converged RI
approximation errors or a chemical-accuracy guarantee. Eighteen HSE06/XYZ cases
warn about an effective range of 14.279 Angstrom versus a half-cell spacing of
8.000 Angstrom, including eight of those energy pairs. Such totals require a
physical model/range review. No reliable speedup is established.

**RI-HFX remains experimental.** Check stderr, actual process/scheduler exit,
SCF/geometry convergence and numerical/model convergence separately.
PROGRAM ENDED and sbatch acceptance alone are not clean execution. Resolve the
shutdown failure, recover the missing fresh reference, assess periodic HSE06 and
collect forces/RI size-radius convergence before release acceptance. Full local
evidence is retained under
`test-workspace/ri-hfx-035-native-analysis-JHBwYX/REPORT.md` and `native-review/`
(ignored artifacts, not shipped fixtures). The 0.3.5 generator fixes have only
software/static validation until separately authorized new native runs.

References: target-2026.2 [FORCES](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/PRINT/FORCES.html)
and [INTERACTION_POTENTIAL](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/XC/HF/INTERACTION_POTENTIAL.html).

## RI-HFX and hybrid acceleration matrix (0.3.5)

RI-HFX is opt-in at **121** / `--ri-hfx`, independent of functional selection
and ADMM. The first subset supports **PBE0/HSE06**, target **2026.2**, classic
MOLOPT/UCL GPW, Gamma, NONE/XYZ, ENERGY/ENERGY_FORCE/GEO_OPT, RKS/UKS and
OT/diagonalization without smearing or +U. Force paths are source-inspected,
not numerically validated. These are generator limits, not CP2K-wide restrictions.

| Profile | Direct HFX | ADMM + four-center HFX | RI-HFX | RI-HFX + ADMM |
|---|---|---|---|---|
| PBE0 | Supported | Supported | Supported | Blocked: separate combination audit deferred |
| HSE06 | Supported | Supported | Supported | Blocked: separate combination audit deferred |
| B3LYP | Supported | Blocked: correction audit deferred | Blocked: profile audit deferred | Blocked |
| BHandHLYP | Supported, Libxc assertion | Blocked: correction audit deferred | Blocked: profile audit deferred | Blocked |
| M06-2X | Supported, Libxc assertion | Blocked: correction audit deferred | Blocked: profile audit deferred | Blocked |
| PBEh | Supported, explicit HF fraction | Blocked: correction audit deferred | Blocked: profile audit deferred | Blocked |

All supported columns retain the common hybrid task/model/spin/solver gates
above. None enables GAPW, low-dimensional PBC, non-Gamma, CELL_OPT/stress,
smearing, +U, custom orbital bases, UZH-PBE0 protocols or correlated methods.
Required build support is not detected. No column is certified by native CP2K runs.

```bash
cp2kkit generate-input water.xyz -o water-pbe0-ri.inp --periodic NONE \
  --functional PBE0 --ri-hfx --data-dir /path/to/cp2k/data --write-json
cp2kkit generate-input solid.extxyz -o solid-hse06-ri.inp \
  --functional HSE06 --ri-hfx --ri-basis-size LARGE \
  --ri-eps-filter 1e-10 --ri-memory-cut 5 --data-dir /path/to/cp2k/data
```

RI auxiliary policy is **AUTO_BASIS RI_HFX**, default **MEDIUM**, with explicit
SMALL/MEDIUM/LARGE/HUGE sizes. Actual selected ORB files, Gaussian payloads,
aliases/q and hashes are checked using existing resolution; use `--data-dir`,
CP2K_DATA_DIR or explicit `--basis-file`. Catalog-only RI templates are rejected.
CP2K constructs the RI basis from ORB at runtime; cp2kkit neither constructs nor
certifies those auxiliary functions. No new basis number, coefficients, manual
RI basis selection, RI_AUX selection or AUX_FIT substitution is introduced.
AUX_FIT remains the separate ADMM role at 223. SORT_BASIS EXP is emitted for RI.

The HF/RI section explicitly enables RI and uses RI_FLAVOR RHO. The default
**RI_METRIC HFX** follows the existing HF interaction operator and parameters:
PBE0/NONE uses full COULOMB; PBE0/XYZ inherits the face-spacing-bounded TRUNCATED
radius; HSE06 uses SHORTRANGE with omega=0.11 bohr^-1 and a CP2K-determined
metric cutoff from EPS_SCHWARZ. CP2K separately extends the short-range HFX
operator range using RI/EPS_FILTER_2C during RI setup; no numeric runtime range
is claimed here. Consistent metric inheritance is not a claim of optimal sparsity.

An optional **RI_METRIC TRUNCATED** uses an independent, explicitly required
`ri_cutoff_radius` in angstrom, without changing HF fraction, exchange operator,
omega or exchange radius. NONE and XYZ are supported within the same bounded
profile/task/solver scope. For XYZ the RI radius must be strictly below half the
minimum perpendicular face spacing of the emitted, rounded cell, including skew
cells. Invalid radii fail, never clip or change the cell. No automatic 1.5 angstrom
choice or independent RI omega editor is introduced. Radius/metric accuracy and
performance require separate numerical convergence checks.

```bash
cp2kkit generate-input solid.extxyz -o solid-pbe0-ri-truncated.inp \
  --functional PBE0 --ri-hfx --ri-metric TRUNCATED --ri-cutoff-radius 1.7 \
  --data-dir /path/to/cp2k/data --write-json
```

All RI modes resolve and emit INTERACTION_POTENTIAL/T_C_G_DATA: the inspected
2026.2 RI initialization checks this file even for non-truncated operators. A
supplied data directory requires readable t_c_g.dat; its raw bytes/hash are
recorded and protected. With explicit ORB files but no data directory, the
runtime filename remains t_c_g.dat with an unchecked-data warning. File presence
is not validation of the table's numerical contents. Since 0.3.5, the emitted
reference is always the short t_c_g.dat name; absolute paths remain provenance.
The shared hybrid filename/force-output fixes above supersede the original
0.3.5 default-text preservation, without changing physical defaults.

Numerical controls at 121 share CLI/config/replay validation:

- `ri_metric` / `--ri-metric`: HFX (default) or TRUNCATED.
- `ri_cutoff_radius` / `--ri-cutoff-radius`: finite positive angstrom value,
  required explicitly for TRUNCATED, rejected with HFX; independent of
  `hf_cutoff_radius`, and subject to the periodic bound above.
- `ri_basis_size` / `--ri-basis-size`: MEDIUM default; size is not convergence.
- `ri_eps_filter` / `--ri-eps-filter`: finite dimensionless value in (0,1),
  default 1e-9, emitted as EPS_FILTER. Converge accuracy; values above 1e-8
  are not recommended by the target-version guide.
- `ri_memory_cut` / `--ri-memory-cut`: positive integer, default 3,
  emitted as MEMORY_CUT. This batches tensor contractions, **not a memory cap**.
- Other RI numerical controls retain CP2K defaults; in particular
  2C_MATRIX_FUNCTIONS=CHOLESKY may fail for ill-conditioned auxiliary bases.
  Automatic fallback or eigenvalue repair is not implemented.

Nondefault RI controls while RI is off fail instead of disappearing. They remain
editable through 121 for explicit reset after disabling. Other unsupported
functional/model requests fail without changing charge, spin, PBC, task or solver.
RI + ADMM is explicitly rejected in either selection order. Direct four-center
`hf_memory` has no RI meaning: nondefault values fail with RI; its default 512 is
retained in raw settings but **HF/MEMORY is not emitted**, and effective
max_memory_mib_per_mpi_process/eps_storage_scaling are null. EPS_SCHWARZ remains
a shared HF screening setting, not a replacement for RI EPS_FILTER.

Hybrid manifests include a generator-policy acceleration matrix and enabled RI
metadata under method_profile.hfx.ri, with basis role/parent/size, metric,
effective metric operator/omega/radius, thresholds, batching and inspected
source identity. CDD reuses the existing complete HFX-identity check for whole/A/B;
split magnetic KINDs retain the same element-specific ORB parent. Generated
auxiliary completeness, actual CUBE reference/grid consistency and physical
accuracy are unverified. Defaults remain RI-off; 0.3.5 changes only the documented
hybrid data filenames and ENERGY_FORCE print text. Schema stays 0.1.0 with
additive fields.

RI metadata and review identify thresholds by complete keyword path, with
`selection` = explicit_input, source_derived or native_default and `emitted`
flags. QS/EPS_DEFAULT remains 1e-11 for ENERGY and 1e-12 for forces/optimization.
Omitted **FORCE_EVAL/DFT/QS/EPS_PGF_ORB** is source-derived as its square root:
approximately 3.1623e-6 or 1e-6 respectively. This is distinct from omitted
**FORCE_EVAL/DFT/XC/HF/RI/EPS_PGF_ORB**, whose native default is 1e-5. Both are
recorded as expected source values, **not runtime observations**. EPS_FILTER,
EPS_FILTER_2C, EPS_SCHWARZ and EPS_SCF are also qualified by full path. Numerical
input defaults remain unchanged; EPS_SCF stays 1e-6 and restart remains inactive.

RI-HFX is not universally faster: large sparse periodic systems can favor
four-center exchange. Compare representative energies/forces with direct HFX
and converge RI size/filtering, orbital bases, SCF and cell/radius independently.
Generation/source checks and synthetic tests establish neither native syntax
acceptance, linked-build support, convergence, speedup nor scientific validity.
The generator and software tests do not run CP2K or submit jobs. User-returned
native observations and their limitations are recorded in the 0.3.5 section above.

References: target-2026.2 [Gamma RI-HFX guide](https://manual.cp2k.org/cp2k-2026_2-branch/methods/dft/hartree-fock/ri_gamma.html),
[HF/RI keywords](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/XC/HF/RI.html)
and [DFT AUTO_BASIS](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT.html).
The guide cites Bussy2023 for RI-HFX; the inspected auto-basis source cites
Stoychev2016. Follow CP2K's method references for research use. Exact local
source identities, Multiwfn references and differences are recorded in
[provenance](../third_party/multiwfn/PROVENANCE.md).

## ADMM and auxiliary bases (0.3.4)

ADMM is an additional exchange approximation/assembly scheme, not another XC
functional and not RI-HFX. The existing direct-four-center backend operates
with a smaller auxiliary basis. Default **off** preserves previous input physics.

| Capability | Bounded ADMM scope |
|---|---|
| XC / target | PBE0 or HSE06 DFT, target 2026.2 only |
| Model / tasks | Existing classic MOLOPT/UCL GPW, Gamma, NONE/XYZ; ENERGY, ENERGY_FORCE, GEO_OPT |
| Spin / solver | RKS or collinear UKS, including split magnetic KINDs; OT or diag, no smearing |
| Projection / correction | BASIS_PROJECTION; EXCH_SCALING_MODEL NONE; EXCH_CORRECTION_FUNC DEFAULT |
| Purification | auto: OT MO_DIAG / diag NONE; explicit MO_DIAG or NONE; MO_DIAG with diag fails |
| Auxiliary basis | Independent AUX_FIT registry 200-203; admm-dz, admm-dzp (default), admm-tzp, admm-tz2p |
| Required data | Actual selected ORB and AUX_FIT Gaussian libraries; default auxiliary source BASIS_ADMM_UZH |
| Reused features | Existing dispersion gates, electron/spin cubes, whole/A/B CDD with ADMM and per-element auxiliary identity checks |
| Excluded | B3LYP/BHandHLYP/M06-2X/PBEh ADMM, GAPW/AE, UZH-PBE0/custom ORB, RI-HFX/RI_AUX, +U, smearing, non-Gamma, CELL_OPT/stress, MD/TDDFT |

```bash
cp2kkit generate-input water.xyz -o water-pbe0-admm.inp --periodic NONE \
  --functional PBE0 --admm --aux-basis admm-dzp \
  --data-dir /path/to/cp2k/data --write-json
cp2kkit generate-input water.xyz -o water-hse06-admm-diag.inp --periodic NONE \
  --functional HSE06 --admm --scf diag --admm-purification NONE \
  --basis-file /path/to/BASIS_MOLOPT \
  --aux-basis-file /path/to/BASIS_ADMM_UZH --write-json
```

**122** edits enablement and purification. **223** opens the independent
auxiliary-basis list; its **f** edits the explicit auxiliary-file JSON list,
and `[]` restores automatic source lookup. Enter keeps; 0/back returns.
No existing orbital chooser IDs or functional/xTB positions are reassigned.
CLI/config/replay use string auxiliary IDs, not interactive numbers.
`--aux-basis-file` is repeatable and explicit files win without default fallback.
`--data-dir` or CP2K_DATA_DIR supplies the default auxiliary file, with the same
precedence as the existing resolver. No free-form custom/per-element AUX_FIT
names or automatic BASIS_ADMM/BASIS_ADMM_MOLOPT substitution in this iteration.

The shared Gaussian parser supports AUX_FIT as a distinct role; RI_AUX remains
unavailable. Each present element requires the registered `family-qN` alias,
matching its selected potential's explicit-electron count. Missing elements,
unknown/wrong auxiliary q, malformed selected payloads, non-finite data and
differing duplicate aliases fail. Both ORB and AUX_FIT aliases are rechecked
against the complete emitted basis-file union to prevent cross-file shadowing.
Known local-data limitation for the inspected BASIS_ADMM_UZH hash: Ca
`admm-dz-q10` and `admm-dzp-q10` are rejected because a p-shell descriptor
specifies one contraction but its rows contain two coefficients. The parser
does not silently discard the extra column. No source data is changed and
native CP2K handling is unverified. Other selected entries are checked
independently; no automatic size substitution is made.

Only used files are emitted, deduplicated and hash-recorded. The ADMM follow-up
retains version 0.3.4 by user request. Portable UZH orbital aliases require matching orbital records; auxiliary-only
sources retain their resolved paths, including when selected through `--data-dir`
or `CP2K_DATA_DIR`. This fixes the 0.3.4 misreplacement of `BASIS_ADMM_UZH`
with `BASIS_MOLOPT_UZH`; the explicit `--basis-file` workaround is no longer
needed. Regenerate affected inputs to new paths; old inputs are not repaired
automatically. Auxiliary source paths/hardlinks/symlinks receive the existing
writer protections. Unsafe whole-line
filenames fail; literal internal spaces remain supported. No numerical payload
or installed auxiliary coverage is bundled.

Purification choices follow the inspected Multiwfn ground-state branch:
MO_DIAG requires OT; NONE supports diagonalization. Only these two force-capable
purification modes and BASIS_PROJECTION are exposed. No silent solver repair,
named ADMMS shortcut, blocking, charge-constrained fitting or scaling variant is
introduced. Explicit incompatible retained controls fail; disabling ADMM requires
resetting nondefault auxiliary/purification/file overrides rather than hiding them.

`EXCH_CORRECTION_FUNC DEFAULT` intentionally lets CP2K follow the actual HFX
operator, fraction, omega and radius: full Coulomb uses PBE exchange,
SHORTRANGE uses matching XWPBE, and TRUNCATED uses the matching
PBE_HOLE_T_C_LR/XWPBE construction. It is not a universal unscaled PBEX override.
The existing HF and XC definitions, screening, memory and truncation controls
are unchanged. Source inspection does not establish linked-build compatibility.

Per-KIND `aux_fit` records independent registry ID/number, role, exact alias/q,
actual source/entry hashes and `physical_pairing_validated=false`.
`method_profile.admm` records effective fitting/purification/correction and
source identity; `hfx.admm=true`, `ri_hfx=false`. Defaults/config migration and
CDD consistency are described in [the schema](schema.md).
Using UZH auxiliary data does not open the UZH-PBE0 orbital/potential protocol.
Orbital/auxiliary physical pairing and basis completeness remain user validation
responsibilities: compare representative energies/forces with direct HFX and
converge auxiliary size before production.

References: Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp (projection, solver-dependent
purification and AUX_FIT family organization); supplied local CP2K reference
tree REVISION git:c92cc08 (input_cp2k_dft.F, cp_control_utils.F,
hfx_admm_utils.F, admm_methods.F, BASIS_ADMM_UZH). Directory naming/target
references do not certify unmodified official-tag identity; exact inspected
hashes and boundaries are in admm.py/auxiliary_basis.py and
[provenance](../third_party/multiwfn/PROVENANCE.md).
See the target-2026.2
[ADMM guide](https://manual.cp2k.org/cp2k-2026_2-branch/methods/dft/hartree-fock/admm.html)
and [input reference](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/AUXILIARY_DENSITY_MATRIX_METHOD.html).
No CP2K calculation, native syntax acceptance, convergence, speedup or scientific
accuracy is established by this implementation.

## GFN-xTB methods (0.3.1)

xTB is selected by `InputSettings.method` / `--method`, separate from the
retained DFT `functional`. Old configs default to DFT. Chooser 1/110 preserves
existing DFT positions and appends exactly Multiwfn's numbers:
**30 GFN1-xTB**, **31 GFN0-xTB**, **32 GFN2-xTB (tblite)**.
These are method values, not global functions or basis numbers.

### CP2K version matrix

Version selection is explicit (`--cp2k-version` / menu 504), not detection.
Tagged-source checks cover the following releases; no installed binary is certified.

| Target CP2K | GFN1 native | GFN0 native | GFN2 via linked tblite |
|---|---|---|---|
| 2024.2, 2024.3 | Yes; legacy input/data layout | Not available upstream | Not available upstream |
| 2025.1 | Yes | Yes; requires D4 build support | No tblite interface upstream |
| 2025.2, 2026.1 | Yes | Yes; requires D4 build support | Explicit diagonalization only; OT generation blocked |
| 2026.2 | Yes | Yes; requires D4 build support | Yes; explicit TBLITE backend |

Unavailable models fail before publication with a minimum-version explanation;
no fallback to another GFN model or rename of parameter files is performed.
GFN1 on 2024.x omits the unsupported GFN_TYPE keyword and references
`xTB_parameters`. From 2025.1, native models emit GFN_TYPE 1/0 and reference
`xTB1_parameters` / `xTB0_parameters`.
GFN2 on 2025.2/2026.1 activates `&TBLITE T / METHOD GFN2`, without
GFN_TYPE TBLITE, SCC_MIXER or ACCURACY. Version 2026.2 uses GFN_TYPE TBLITE
and its TBLITE section. Build availability remains user-asserted, not probed.

140 selects DFT/GFN-xTB; 141 is `--tblite-available` for GFN2.
142 is `--xtb-accuracy`, available only for GFN2 on target 2026.2
(finite positive dimensionless factor, default 1.0). A nondefault accuracy
request on an older target fails rather than being silently discarded.

### Solvers and convergence

- **GFN1:** OT by default, or explicit diagonalization. OT emits
  FULL_SINGLE_INVERSE (not DFT FULL_ALL), DIIS and STRICT unless overridden,
  25/20 inner/outer steps and EPS_SCF 1e-6. These OT defaults follow the inspected
  Multiwfn GFN1/Gamma branch, except the retained local ordinary-ENERGY EPS_SCF
  policy (1e-6 rather than 5e-6). Diagonalization defaults to 128 steps/Broyden.
- **GFN0:** non-SCC diagonalization. No EPS_SCF/iteration/mixing/OT controls;
  explicit SCC overrides fail. The retained raw SCF selector is inactive.
- **GFN2:** OT generation is enabled only for target **2026.2**, on the supported
  isolated Gamma/no-smearing subset. OT uses the same FULL_SINGLE_INVERSE/DIIS/STRICT
  and 25/20 EPS_SCF controls as native GFN1, without a separate SCC mixer.
  For legacy targets **2025.2/2026.1**, select `--scf diag` explicitly (menu 320).
  Omitted/default OT, explicit OT and retained OT configs all fail before writing;
  no solver, target version or physical setting is automatically changed.
  The 2026.1 local build crashed in the tblite OT density-update path even at one
  MPI rank and with IRAC. The 2025.2 restriction is conservative, not a claim of
  a tested crash. Enabling 2026.2 generation does not certify the installed binary;
  changing a target string cannot repair or upgrade an older executable.
- **GFN2 legacy diagonalization (2025.2/2026.1):** CP2K DIRECT_P_MIXING,
  ALPHA 0.2, 128 steps and EPS_SCF 1e-6. No new tblite controls are invented.
- **GFN2 diagonalization (2026.2):** SCC_MIXER AUTO selects native tblite SCC;
  ACCURACY controls SCC convergence, distinct from emitted CP2K EPS_SCF.
  With **OT**, ACCURACY controls tblite numerical setup only: EPS_SCF controls
  the orbital optimization. Metadata/review record this solver-dependent role.

All explicit supported solver choices are retained. Multiwfn's chooser only
forces OT for GFN1 at Gamma, not for every GFN selection; GFN2 can retain a prior
solver state. No external xtb/tblite/reference CLI is invoked; atomic-charge
checks are not disabled automatically.

### Geometry, state and data boundaries

The generator subset is H-Rn, isolated PERIODIC NONE, Gamma, closed-shell
multiplicity 1, ENERGY/ENERGY_FORCE/GEO_OPT; these are not CP2K-wide limitations.
Charge is explicit; auto multiplicity uses model reference electron parity,
not GTH q (e.g. Na=1, Mg=2, Fe=8). Odd-electron/open-shell states fail, not repaired.
Native counts were checked across all six tagged sources; tblite 0.6.0 GFN2
reference occupations are reference evidence, not a detected backend version.

Intrinsic D3(BJ)/GFN1 and D4/GFN0/GFN2 are retained. No MOLOPT/GTH/KIND, XC,
MGRID, GPW Poisson or additional VDW section is emitted. dispersion=none means
no extra DFT-D correction, not removal of model dispersion. Nondefault DFT
functional/basis/grid/file/Libxc/PBE-approval requests, +U/magnetic seeds,
density cubes/CDD, smearing/extra orbitals, non-Gamma, periodic and CELL_OPT
fail explicitly. Hidden values remain retained until explicitly reset.

Geometry/box generation, optimization thresholds, XYZ/PDB trajectories, fixed
atoms and staged writing reuse the existing paths. Fixed-atom keyword references
are target-specific for xTB on all six releases; the DFT constraint gate is
unchanged. EXTXYZ requires target 2026.1 or newer for xTB; it is rejected on
older targets instead of being emitted as an unsupported format.

GFN1 also references dftd3.dat. With --data-dir or CP2K_DATA_DIR, require the
pinned bytes for the selected target, record source paths/SHA-256, and protect
them from replacement. In particular, the inspected 2024.2-2026.1 D3 file hash
differs from 2026.2. Missing/modified/wrong-version data fail before writing;
custom refits remain outside this subset. Without a data root filenames are
unchecked runtime requirements. PARAMETER filenames are char_t fields: quote
paths with spaces, unlike DFT whole-line filenames. GFN2 uses tblite built-in
parameters and records backend_version=null/backend_unchecked.

Examples (generation only):

```bash
cp2kkit generate-input water.xyz -o water-gfn1-2024.inp --periodic NONE \
  --method GFN1-xTB --cp2k-version 2024.2
cp2kkit generate-input water.xyz -o water-gfn2-2025.inp --periodic NONE \
  --method GFN2-xTB --cp2k-version 2025.2 --scf diag --tblite-available
cp2kkit generate-input water.xyz -o water-gfn2-diag.inp --periodic NONE \
  --method GFN2-xTB --cp2k-version 2026.2 --scf diag --tblite-available \
  --xtb-accuracy 0.1 --write-json
```

Earlier user-authorized water diagnostics separately established normal termination
and electronic/geometry convergence for GFN2 diagonalization on local CP2K
2026.1/git:5e54ba2 and OT on local 2026.2/git:c92cc08. The latter emits a
Gamma/no-smearing warning and ignores SCC_MIXER under OT. Build/compiler/backend
identities differ and unmodified official-release equivalence is unverified;
these checks are not general version, element or force-accuracy certification.
Source-byte/keyword checks alone do not establish a linked build, native syntax
acceptance, convergence, forces or scientific validity. Exact tagged-source
references are in xtb_versions.py and [provenance](../third_party/multiwfn/PROVENANCE.md).

## Non-hybrid XC profiles (0.3.0)

Version 0.3.0 implements **15 non-hybrid profiles** from Multiwfn 2026.10.1's
CP2K generator: no HF exact exchange, ADMM/RI-HFX, double hybrid or xTB.
All ten additions require target **CP2K 2026.2**. The original five chooser
positions and default PBE / DZVP-MOLOPT-SR-GTH input physics remain unchanged.

| Canonical setting (case-insensitive) | XC emitted inside XC_FUNCTIONAL | Libxc assertion | Additional dispersion allowed |
|---|---|---|---|
| PBE | Native PBE | No | none, d3, d3bj |
| BLYP | Native BLYP | No | none, d3, d3bj |
| PBESOL | PBE / PARAMETRIZATION PBESOL | No | none, d3, d3bj |
| REVPBE | PBE / PARAMETRIZATION REVPBE | No | none, d3, d3bj |
| RPBE | GGA_X_RPBE + GGA_C_PBE | Yes | none, d3, d3bj |
| PADE (alias LDA) | Native PADE | No | none |
| BP86 (alias BP) | Native BP: BECKE88 + P86C | No | none, d3, d3bj |
| TPSS | MGGA_X_TPSS + MGGA_C_TPSS | Yes | none, d3, d3bj |
| REVTPSS | MGGA_X_REVTPSS + MGGA_C_REVTPSS | Yes | none, d3, d3bj |
| SCAN | MGGA_X_SCAN + MGGA_C_SCAN | Yes | none, d3, d3bj |
| R2SCAN | MGGA_X_R2SCAN + MGGA_C_R2SCAN | Yes | none, d3bj |
| MN15L (alias MN15-L) | MGGA_X_MN15_L + MGGA_C_MN15_L | Yes | none, d3 |
| HLE17 | MGGA_XC_HLE17 | Yes | none |
| B97M-RV | MGGA_XC_B97M_V + required rVV10 below | Yes | none (intrinsic nonlocal retained) |
| BEEFVDW (alias BEEF-vdW) | Native BEEFVDW + required LMKLL below | **Yes** | none (intrinsic nonlocal retained) |

BEEFVDW is not Libxc-free: the inspected CP2K shortcut expands to native BEEF
exchange, PBE correlation scaled by 0.3998335231 and **Libxc LDA_C_PW** scaled by
0.6001664769. CP2K owns those coefficients; the generator emits its shortcut,
not a second independently rounded expansion. Likewise HLE17 uses the combined
Libxc definition (internally 1.25 TPSS exchange + 0.5 TPSS correlation), not an
HF fraction. Build assertions are required even though no explicit LDA_C_PW
subsection appears in the BEEFVDW input.

### Capability and numerical limits

- PADE/BP86 follow existing semilocal GPW rules, including non-Gamma diagonalization,
  CELL_OPT and explicit +U. Existing GAPW Gamma/ALL rules are retained for
  compatible AE families; UZH-PBE and UZH AE families remain PBE-only.
- All meta-GGAs (including B97M-rV) and BEEF-vdW initially allow **GPW Gamma
  ENERGY/ENERGY_FORCE/GEO_OPT without +U**, for RKS or collinear UKS. Existing
  boundary/SCF rules also apply. GAPW/non-Gamma/CELL_OPT/+U fail explicitly. These are
  cp2kkit scope limits, not claims that CP2K universally lacks those capabilities.
- No new basis/q policy: prefer real matched potentials from supplied data.
  PADE uses GTH-PADE; BP86 maps to actual GTH-BP, not invented GTH-BP86. At the
  fixed 71-element q policy, the pinned catalog has 71 PADE and 41 BP matches.
  Missing matches require explicit menu **114** / `--allow-pbe-potential`.
  Record the real GTH-PBE approximation; never rename it or change q.
- Menu **113** / `--libxc-available` asserts target build support for RPBE,
  meta-GGAs and BEEF-vdW. No version/build is detected or installed. Selecting
  the functional does not grant potential approval or the build assertion.
- Meta-GGAs depend on kinetic-energy density. Retained CUTOFF/REL_CUTOFF
  **400/55 Ry**, EPS_SCF 1e-6 and native XC low-density thresholds are starting
  values, not demonstrated convergence. Check grids/SCF and low-density behavior
  independently; no automatic numerical/physical resets are made.
- Additional D3/D3(BJ) uses the canonical functional reference, never PBE as a
  parameter substitute. The matrix follows the inspected zero/BJ parameter
  branches in CP2K 2026.2; unsupported pairs fail before writing. This does not
  establish optimal dispersion for a property. D4/arbitrary mixtures are deferred.
- Density/CDD reuse the same generator and require identical nonlocal/kernel
  metadata across whole/A/B components. Actual CUBE grids/reference states
  remain separate checks before subtraction.

### Required nonlocal correlation and kernel evidence

B97M-rV always includes `VDW_POTENTIAL / POTENTIAL_TYPE NON_LOCAL / NON_LOCAL`
with `TYPE RVV10`, `PARAMETERS 6 0.01` (dimensionless b/C) and
`KERNEL_FILE_NAME rVV10_kernel_table.dat`. These are method-specific parameters,
not the generic CP2K 6.3/0.0093 defaults. BEEF-vdW uses `TYPE LMKLL` and
`KERNEL_FILE_NAME vdW_kernel_table.dat`; no rVV10 parameters apply.
The nonlocal FFT CUTOFF is omitted (metadata null, CP2K native default);
its grid convergence is not established. No additional pair correction is allowed.

Thus `--dispersion none` means **no additional pair correction**, not removal of
a named method's required nonlocal term. TUI review/preview and JSON make this
distinction explicit. DFT-D parameters and nonlocal kernels are separate data roles.

With `--data-dir` (or CP2K_DATA_DIR), the required kernel must be readable UTF-8;
its absolute literal whole-line path, raw SHA-256 and size are recorded under
`data_sources.xc_kernel` and `nonlocal_correlation.kernel_source`.
Missing/unreadable files fail before publication. Checks are **source bytes only**,
not validation of kernel numbers, method compatibility or numerical convergence.
Without a data directory, the basename is emitted and resolution at runtime is
explicitly unverified. Basis/potential-only explicit files do not imply a kernel
location. Kernels/data and hardlink aliases stay protected from output replacement.

```bash
# Syntax/assembly examples only; geometry, spin, approximations and convergence need review.
cp2kkit generate-input water.xyz -o water-r2scan.inp --periodic NONE \
  --functional r2SCAN --libxc-available --allow-pbe-potential --write-json
cp2kkit generate-input solid.extxyz -o solid-b97m-rv.inp \
  --functional B97M-rV --libxc-available --allow-pbe-potential \
  --data-dir /path/to/cp2k/data --dispersion none --write-json
cp2kkit generate-input solid.extxyz -o solid-beef.inp \
  --functional BEEF-vdW --libxc-available --allow-pbe-potential \
  --data-dir /path/to/cp2k/data --write-json
```

Static evidence: the fixed Multiwfn source, tagged CP2K input/shortcut/D3
definitions, and local Libxc 7.0.0 sources; see
[feature provenance](../third_party/multiwfn/PROVENANCE.md). The versioned
[NON_LOCAL manual](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/XC/VDW_POTENTIAL/NON_LOCAL.html)
confirms nesting, parameter order, units and kernel names. Synthetic tests and
read-only library checks are not native syntax acceptance, energies/forces/stress
validation, or proof of convergence. No CP2K/Multiwfn process is run by generation.

## Functional and basis profiles (0.2.6)

The original profile round is retained below; the 0.3.0 matrix above supersedes
its five-profile scope and Libxc/menu applicability descriptions.

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
As of 0.3.0, menu 114 is available outside PBE/BLYP and menu 113 follows all
Libxc-requiring profiles, including BEEF-vdW; hidden values remain retained for later edits. Selecting a functional never automatically grants approval.

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
and explicit custom pseudopotential ORB files. Version 0.3.0 adds the bounded
meta-GGA/nonlocal subset above; 0.3.1 adds the separate bounded xTB branch.
Versions 0.3.2/0.3.3 add the six bounded direct-HFX hybrids; 0.3.4 separately
adds PBE0/HSE06 ADMM and checked AUX_FIT families. Version 0.3.5 adds the
bounded PBE0/HSE06 Gamma RI-HFX subset above. UZH-PBE0 templates,
arbitrary q changes, broader auxiliary and reserved families remain unimplemented; see [basis selection](basis-selection.md).

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
