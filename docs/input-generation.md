# CP2K input generation

This guide describes cp2kkit **0.2.6**. Older defaults and migration notes are in
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

## Single numbered input-generation menu

```bash
cp2kkit generate-input --tui
cp2kkit generate-input --interactive     # Equivalent option.
cp2kkit generate-input water.xyz -o water-opt.inp --periodic NONE \
  --run-type GEO_OPT --dispersion d3bj --electron-density --tui --plain
cp2kkit generate-input                  # Opens menu only when both streams are TTY.
```

All applicable settings appear together in one scrolling numbered menu, using
Multiwfn-style direct selection. There are no sequential steps, hidden advanced
pages, or group-selection submenus. Corresponding main-menu IDs follow the inspected
Multiwfn 2026.10.1 source; unsupported entries are omitted, not reassigned.
This changes presentation only; the same `InputSettings`, generator and protected
writer remain in use. Version **0.2.6** retains the menu introduced in 0.2.4;
new profiles are explicit opt-ins, not changes to the default scientific settings.

| ID | Setting/action | Numbering origin |
|---|---|---|
| -10 | Return/cancel generation | Multiwfn main menu |
| -7 | Periodicity | Multiwfn main menu |
| -3 | Electron-density cube | Multiwfn cube entry; supported density subset only |
| -1 | Task | Multiwfn main menu |
| 0 | Review and generate, with explicit y/yes confirmation | Multiwfn generate ID; extra safety confirmation |
| 1 / 2 / 3 / 4 | Functional / basis / dispersion / OT-diag | Multiwfn main menu |
| 6 / 8 | Smearing temperature / k-points | Multiwfn main menu; local parameter prompts |
| 10 / 12 | Optimizer / CELL_OPT pressure | Multiwfn main menu |
| 101 / 102 | Charge / multiplicity | Local extensions (upstream Other settings 1/2) |
| 105 / 106 | CUTOFF / REL_CUTOFF | Local extensions (upstream Other settings 5 combines both) |
| 107 / 112 | Isolated padding / ADDED_MOS | Local extensions (upstream Other settings 7/12) |
| 120 / 121 / 122 | EPS_SCF / inner-diag limit / outer limit | Local extensions |
| 123 / 124 / 125 | Optimization steps / DFT+U / magnetic initialization | Local extensions |
| 126 / 127 | Spin density / cube stride | Local extensions |
| 128 / 129 / 130 | Element basis overrides / approve GTH-PBE approximation / target Libxc assertion | Local extensions |

Only corresponding implemented main-menu IDs are reused; this is not full upstream
menu/choice/default equivalence. In particular, OT outer-limit editing is not the
upstream outer-SCF enable/disable toggle. No unimplemented placeholders are shown.

- Structure path and frame appear above the list, without setting numbers or seed
  annotations. `s` loads/replaces the structure; `f` selects the XYZ frame.
  An invalid source/frame preserves the previous selection.
- Output path, project and target-version rows are removed. Without `-o`, the
  output is `<source-stem>.inp` in the current directory; a source change updates
  an automatic target. Explicit CLI `-o`, `--project`, and `--cp2k-version` seeds
  remain honored. PROJECT still defaults to the source stem; target CP2K stays 2026.2.
  These values and absolute output paths remain in review/manifest for traceability.
- Select any displayed number directly; a prompt shows its choices. Numbers remain
  fixed across task/SCF/PBC changes. Hidden fields cannot be selected.
  Pressure appears only for CELL_OPT; optimizer/step limits only for optimization.
  Isolated padding requires effective NONE, not Unknown. OT hides smearing/ADDED_MOS;
  diag hides outer SCF limits. All values are retained when fields disappear.
- Parameter Enter keeps; `back` abandons that edit. **Literal zero remains a value**,
  including charge, ADDED_MOS and Boolean off. Optional `auto` restores defaults.
  Enumerations accept names/numbers; triples are space-separated.
- **Input-generation navigation changed:** `0` now reviews/generates, matching
  Multiwfn. Use `-10`/`back`/`cancel` to return without generation.
  The application main menu still uses `0` to exit; ordinary submenus retain their
  own `0`-back behavior. `q` exits the session; Ctrl+C cancels; EOF exits cleanly.
- `r` reviews effective settings/warnings and full paths; `p` adds full input and
  the replay command. Neither writes. Enter returns to the same settings list.
- `0` or its alias `w` reviews and asks for explicit `y`/`yes` before writing.
  Enter defaults to no. Collision/I/O errors offer a new-path retry prompt
  (Enter/back returns to settings), without adding a persistent output-path option.
  No overwrite button exists. The protected writer revalidates and rolls back.
- Bare interactive generation opens the same menu; use `s` to load a source.
  A missing source gives a recoverable validation message.

- Type/range errors retry locally. Changed fields are rechecked by the existing
  generator. Incompatible drafts retain their values with explicit warnings.
  No charge/spin/SCF/PBC/k-point combination is automatically repaired.
  Hidden overrides are retained and still validated. For example, switch to diag,
  remove explicit smearing/nonzero ADDED_MOS, then switch back to OT. No implicit
  reset is performed when fields disappear.
- Enter paths literally without shell quotes. Use `./q`, `./cancel`, `./back`,
  or `./0` for filenames that collide with navigation words.

Optional Rich (`.[ui]`) has a standard-library fallback; `--plain` and the presence
of `NO_COLOR` disable styling. Text folds on narrow terminals without clearing,
alternate screen, or continuous redraw. Both stdin and stdout must be TTY.
Redirected/piped sessions fail promptly with batch alternatives rather than waiting.
Complete batch calls, schema 0.1.0, scientific defaults, and protected writing are
unchanged; identical structure/settings produce identical text/manifest.

## Scope and defaults

| Setting | Support/default |
|---|---|
| Structure | `.xyz`/`.extxyz`/text `.restart`/`.gjf`/`.com`/`.cif`/POSCAR/CONTCAR/`.vasp`/`.poscar`; XYZ last frame |
| Task | ENERGY (default), ENERGY_FORCE, GEO_OPT, CELL_OPT |
| Method | Quickstep/GPW; PBE (default), BLYP; target 2026.2 adds PBEsol/revPBE/Libxc RPBE |
| Basis | DZVP-MOLOPT-SR-GTH (default); SZV-SR, DZVP/TZVP/TZV2P non-SR; target 2026.2 adds TZVP-SR/TZV2P-SR/TZV2PX and explicit element overrides |
| Potential | Catalog-checked GTH entries with fixed `-qN`; prefer actual matched functional, explicitly approved PBE approximation otherwise |
| Dispersion | none (default), D3, D3(BJ); dftd3.dat and REFERENCE_FUNCTIONAL |
| Charge/spin | 0/1; explicit valence-electron parity check; UKS for multiplicity > 1 or explicit magnetic request |
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
charge 0 / multiplicity 1, GPW and no dispersion. No calculation is executed.

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
matches, generation errors until `--allow-pbe-potential` / menu **129** is explicitly
enabled. Every affected KIND records the actual potential and approximation status,
and review warns that this is not a matched-functional potential. No unverified
GTH-RPBE/GTH-REVPBE names are fabricated, and no q values are changed.

RPBE additionally requires `--libxc-available` / menu **130**. This is a user assertion
about the target CP2K build, not probing, installation, a detected Libxc version, or
runtime certification. Native PBEsol/revPBE do not require Libxc in these profiles.
The menu hides 129 outside the new GGA choices and 130 outside RPBE; values remain
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

Use `--basis-overrides 'Element=basis; Element=basis'` or menu **128** for explicit
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
a different q cannot satisfy a selection. User data files verify existing profiles,
not automatically add arbitrary functional/basis/potential choices.
NGRIDS is 5 if any effective KIND basis is non-SR, otherwise 4. CUTOFF/REL_CUTOFF
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

r2SCAN/meta-GGAs, hybrids/HF/ADMM, UZH protocol pairs, arbitrary q changes and
additional basis families remain roadmap items, not enabled options.

## DFT+U and magnetic initialization (124 / 125)

These are real generator features, not renamed placeholders. They are opt-in and
currently keyword-checked only against CP2K **2026.2**; explicit requests with other
target profiles are rejected rather than presented as verified. These controls
were introduced in 0.2.4 and remain compatible with the 0.2.6 method/basis profiles. Schema 0.1.0 retains the
additive settings/extension metadata.

- **124 — DFT+U:** enter `Element:L:Ueff_eV`, separated by semicolons.
  `L=0/1/2/3` means s/p/d/f; Ueff is finite, nonnegative, in eV, and equals U-J.
  `off`/`auto` clears the correction. One entry per present element is supported.
  No element-specific U values or orbital channels are guessed.
  The generator writes `DFT/PLUS_U_METHOD MULLIKEN` and active
  `SUBSYS/KIND/DFT_PLUS_U` sections with `L` and `U_MINUS_J [eV]`.
  User-selected U/L must be justified for the functional, basis and projector
  definition; no native runtime/shell-suitability validation has been performed.
- **125 — magnetic initialization:** `uks` explicitly enables UKS without local seeds;
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
