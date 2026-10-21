# Input-generator menu numbering and future allocation draft

## Status and scope

**Software 0.3.1 retains the 0.2.9 menu layout v1 and adds GFN-xTB methods; distant feature
allocations remain a draft, not a frozen future registry or a release claim.**

Schema stays **0.1.0**. The authoritative implemented function registry is
`src/cp2kkit/menu_registry.py`. Categories 100-600 contain applicable existing
controls and new 602; categories 700-1000 and other Planned entries below are
not implemented or shown. This document does not authorize execution/submission.
The design baseline was 0.2.8; its function-number migration is now explicit.

This records the discussed design: a compact, Multiwfn-style common-settings
area plus VASPKIT-style category browsing and full-number direct access. It is
not a port of either program's complete menu or a claim of identical numbering.

- [Current input-generation guide](input-generation.md)
- [Architecture](architecture.md)
- [Development roadmap](roadmap.md)
- [Basis registry and its separate numbering contract](basis-selection.md)
- [Schema](schema.md)
- [Third-party notices](../THIRD_PARTY_NOTICES.md)
- [Multiwfn reference provenance](../third_party/multiwfn/PROVENANCE.md)

### Capability labels

- **Existing**: implemented in the current registered subset, with its documented
  limitations; most underlying capabilities already existed in 0.2.8.
- **Planned**: future capability, editor, or configurable control. A hard-coded
  generated value does not mean that a user-editable control already exists.
- **Existing / expand**: an existing subset with explicitly planned extensions.
- **Provisional**: a design choice to review before allocating a permanent number.

No planned scientific feature is automatically available for every CP2K version,
method, spin state, boundary condition, or build. Keyword/source checks and
scientific compatibility tests are prerequisites to implementation. Generation,
native acceptance, convergence, and physical validity remain distinct.

## 1. Interaction contract

### Main menu

Show only:

1. Applicable common shortcuts, including their current values.
2. Category entrances such as 100, 200, and 300, without expanded child rows.
3. Structure/frame controls, review/preview actions, and the generation action.

**Do not print every 100+ setting under category headings on the main menu.**
That flattened layout was considered and rejected as too redundant.

### Browse or go directly

- `100`: display the implemented, applicable members of category 100.
- `101`: directly edit total charge, without first opening category 100.
- `600`: browse implemented property/input-preparation features.
- `602`: directly open the implemented charge-density difference input editor.
- Display full numbers in category menus: 101, 102, 103, not another layer of
  category-local aliases 1, 2, 3.
- Finishing a parameter edit returns to the originating menu.
- Generator-main `0`: validate and generate directly through the shared writer.
- Generator-main `w`: review, then generate only after explicit y/yes confirmation.
  Successful generation returns immediately without an extra Enter prompt.
- Category-menu `0`: return to the input-generator main menu; never write files.
- A complex feature editor may have local options, explicitly labeled as local.
  Its `0` returns without generating. Final publication stays at the main menu.
- Preserve scrolling line-oriented interaction; no full-screen clearing/redraw.

### Direct access and applicability

Category browsing is not a mandatory path. Full setting numbers are recognized
from the input-generator main menu and category menus. A setting omitted only
because another category is displayed can still be reached directly.

An actually inapplicable setting must not become active through direct access.
Explain the reason and retain the existing draft; do not automatically switch
SCF method, task, electron model, or physical settings. Unimplemented numbers must
not dispatch to guessed or placeholder behavior. Do not display empty categories
as selectable menus.

### Separate numeric namespaces

| Input context | Meaning of a number |
|---|---|
| Generator main/category menu | Function/category ID, e.g. 101 or 602 |
| Basis chooser opened by 2/220 | Immutable basis registry number, e.g. 50 or 900 |
| Atom selection prompt | 1-based loaded/expanded atom index or range |
| Parameter prompt | The parameter value, e.g. charge 0 or CUTOFF 400 |
| Complex feature editor | Its explicitly displayed local choices |
| Application main menu | Application navigation, outside this numbering scheme |

Do not globally intercept numbers inside parameter prompts, atom selections,
basis choosers, or feature editors. In particular, basis 900 must never jump to
the environment category, and atom 101 must never open charge editing.

### One owner per setting

A low-number shortcut and a full-number entry operate on the same internal setting
and shared validator. There must not be separate main-menu/category values.
CLI/config/replay use semantic names, not sequences of menu numbers.

## 2. Main-menu common shortcuts

Keep this area compact. New functionality normally enters a category first; a new
low-number shortcut needs a separate usability justification. Unlisted low IDs
remain unallocated, not implicitly assigned.

| Shortcut | Function | Full entry / routing | Status |
|---:|---|---|---|
| -10 | Return/cancel input generation | Navigation | Existing |
| -9 | Show extended-setting category index | Categories only, not every child | Planned; provisional |
| -7 | Periodicity | 211 | Existing |
| -6 | Trajectory output cadence | 511 | Planned |
| -5 | Trajectory format | 510 | Existing |
| -4 | Atomic population charges | 630 | Planned |
| -3 | Density/CUBE output | 601 initially; broader chooser later | Existing / expand |
| -2 | Molden output | 530 | Planned |
| -1 | Calculation task | Existing run-type setting; expand supported tasks incrementally | Existing / expand |
| 0 | Validate and generate directly | Shared authoritative generation/writer | Existing |
| 1 | Functional/calculation method | 110; broader method routing later | Existing / expand |
| 2 | Orbital basis selection | 220 | Existing |
| 3 | Dispersion | 111 | Existing / expand |
| 4 | SCF method | 320 | Existing / expand |
| 5 | Common SCF controls | OT: 323; diagonalization: 330 | Planned; provisional context-sensitive shortcut |
| 6 | Smearing | 340 | Existing |
| 7 | Solvation model | 901 | Planned |
| 8 | k-points | 310 | Existing |
| 9 | Fixed atoms | 420 | Existing |
| 10 | Optimization algorithm | 401; keep meaning fixed | Existing |
| 12 | CELL_OPT external pressure | 430; keep meaning fixed | Existing |
| s / f | Structure / XYZ frame header controls | 201 / 202 | Existing |
| r / p | Review / full preview and replay | Existing read-only actions | Existing |
| w | Review and generate with y/yes confirmation | Generator main menu only | Existing |

Do not reproduce all of Multiwfn's task-dependent shortcut reuse. For example,
retain 10 as the optimizer shortcut rather than making it a thermostat or another
property in a different task. MD thermostat access can use 710. Shortcut 5, if
implemented, must show its current SCF-specific meaning explicitly.

## 3. Category allocation

| Entrance | Range | Category |
|---:|---|---|
| 100 | 101-199 | Electronic state and method |
| 200 | 201-299 | Structure, boundary and basis |
| 300 | 301-399 | Numerical accuracy and SCF |
| 400 | 401-499 | Optimization and constraints |
| 500 | 501-599 | Output, restart and provenance |
| 600 | 601-699 | Properties and analysis inputs |
| 700 | 701-799 | Molecular dynamics and sampling |
| 800 | 801-899 | Reaction paths and free energy |
| 900 | 901-999 | Environment, fields and embedding |
| 1000 | 1001-1099 | Calculation protocols and batch generation |

Category numbers are entrances, not scientific parameter values. Gaps between
listed entries are intentionally unallocated. Do not fill them merely to make the
list contiguous.

## 4. Category 100: electronic state and method

Owns the electronic state and physical model, not SCF numerical tolerances.

| ID | Function | Status / boundary |
|---:|---|---|
| 101 | Total charge | Existing |
| 102 | Spin multiplicity | Existing; auto resolves whole-system electron parity (even 1, odd 2), explicit values override |
| 103 | Magnetic initialization: auto, UKS, element/atom moment seeds | Existing; moments are initial guesses, not constraints |
| 110 | XC functional / electronic-structure method | Existing: 15 non-hybrid profiles plus 30 GFN1-xTB / 31 GFN0-xTB / 32 GFN2-xTB; hybrids deferred |
| 111 | Dispersion correction | Existing subset; new models need validation |
| 112 | DFT+U | Existing explicit Ueff/L, MULLIKEN subset |
| 113 | Target Libxc support assertion | Existing; user assertion, not build detection |
| 114 | Explicit permission for unmatched-functional GTH-PBE approximation | Existing; never automatic |
| 120 | Hybrid-exchange parameters | Planned |
| 121 | RI-HFX settings | Planned |
| 122 | ADMM settings | Planned; auxiliary bases belong to 223 |
| 130 | Constrained DFT target charges/spins | Planned |
| 140 | DFT / GFN-xTB model | Implemented in 0.3.1: DFT or upstream chooser 30/31/32; other semiempiricals/DFTB deferred |
| 141 | Target tblite support assertion | Implemented for GFN2 only; not build detection |
| 142 | tblite ACCURACY | GFN2 on target 2026.2 only; dimensionless; numerical setup with OT, also native SCC convergence with diag |
| 150 | Classical force-field model selection | Planned; topology/files belong to 241/242 |

The [0.3.x functional/method proposal](functional-roadmap-0.3.md) references
Multiwfn's functional definitions/assembly while preserving local function IDs.
It separates XC profiles from the xTB model/backend controls at 140-142.
The combined 110 / shortcut 1 chooser also accepts xTB choices 30/31/32;
selecting a DFT functional there explicitly returns to DFT. Existing DFT chooser
positions are retained; only the new xTB numbers mirror Multiwfn.
The 0.3.0 non-hybrid expansion changes choices at existing ID 110, not function
IDs or basis numbers. Build assertion 113 follows Libxc requirements (including
BEEF-vdW); 114 is available outside PBE/BLYP. Upstream chooser numbers are not
new local function IDs; xTB does not inherit GPW basis/dispersion settings.
Hidden incompatible requests remain retained and fail validation until explicitly reset.
GFN1 supports checked targets 2024.2-2026.2; GFN0 requires >=2025.1 and
GFN2 requires >=2025.2 plus a tblite assertion. GFN1 defaults to OT; GFN2 OT
is enabled only for target 2026.2. Legacy 2025.2/2026.1 GFN2 drafts retaining OT
fail shared validation before writing; explicitly choose diag at 320.
320/324/322 expose the solver/OT algorithm/outer limit without forced changes.
142 is hidden for legacy targets; unsupported retained requests fail validation.

The charge/multiplicity of a fragment workflow is feature-scoped, not a second
copy of the overall-system values at 101/102.

## 5. Category 200: structure, boundary and basis

Owns system composition, spatial representation, data sources, and named regions.

| ID | Function | Status / boundary |
|---:|---|---|
| 201 | Load/change structure | Existing; retain s shortcut |
| 202 | Select XYZ frame | Existing; retain f shortcut |
| 210 | Cell definition/override | Existing orthorhombic-length override; general editor planned |
| 211 | Periodicity | Existing |
| 212 | Vacuum padding for automatic isolated boxes | Existing |
| 213 | Translation/centering/placement policy | Planned explicit control; current automatic behavior is limited |
| 214 | Electrostatic boundary / Poisson scheme | Planned explicit control; current scheme is derived |
| 220 | Global orbital basis | Existing; separate immutable basis-number namespace |
| 221 | Element basis overrides | Existing |
| 223 | Auxiliary basis selection | Planned |
| 224 | Ghost atoms / basis centers | Planned; do not enable implicitly |
| 225 | GAPW setup profile | Existing auto/native compatibility names and current limitations |
| 230 | CP2K data directory | Existing |
| 231 | Explicit basis-file sources | Existing |
| 232 | Explicit potential-file sources | Existing |
| 233 | Custom orbital basis file and real alias | Existing custom-orbital/900 capability |
| 234 | Custom potential file and real alias | Existing restricted capability |
| 240 | Named atom groups / spatial regions | Planned |
| 241 | Molecular topology/connectivity | Planned |
| 242 | Classical force-field parameter files | Planned |

Cell definition belongs here; cell optimization degrees of freedom belong to 432;
k-point sampling belongs to 310. General regions are defined at 240, while a
QM/MM feature selects and interprets its region at 931.

## 6. Category 300: numerical accuracy and SCF

| ID | Function | Status / boundary |
|---:|---|---|
| 301 | CUTOFF | Existing |
| 302 | REL_CUTOFF | Existing |
| 303 | EPS_SCF | Existing; 0.2.8 defaults to 1e-6 for all supported tasks |
| 304 | EPS_DEFAULT | Planned editable control; currently task-derived |
| 305 | NGRIDS override / restore automatic policy | Planned editable control; current emission is basis-derived |
| 306 | GAPW split tolerances and atom-centered grids | Planned editable controls; currently omitted |
| 310 | k-point mesh | Existing |
| 311 | k-point offsets/symmetry and advanced sampling | Planned |
| 320 | SCF solver: OT/diagonalization and future methods | Existing subset |
| 321 | Inner/diagonalization SCF step limit | Existing |
| 322 | Outer SCF step limit | Existing |
| 323 | Outer SCF enable/control | Planned editable control |
| 324 | OT ALGORITHM | Existing |
| 325 | OT MINIMIZER | Planned editable control; current value fixed |
| 326 | OT PRECONDITIONER | Planned editable control; current value fixed |
| 330 | Density-mixing method | Planned editable choice; current diag template is restricted |
| 331 | Mixing coefficients/history parameters | Planned |
| 340 | Smearing and electronic temperature | Existing; also affects physical occupations |
| 341 | ADDED_MOS | Existing |
| 342 | Advanced occupation settings | Planned |
| 350 | Linear-scaling and other advanced SCF solvers | Planned |

Do not promise accuracy from thresholds alone. Basis, grids, sampling, solver
convergence, and target-property convergence require separate evidence.

## 7. Category 400: optimization and constraints

| ID | Function | Status / boundary |
|---:|---|---|
| 401 | Optimizer | Existing BFGS/LBFGS/CG subset |
| 402 | Maximum optimization steps | Existing |
| 403 | TRUST_RADIUS | Existing BFGS/LBFGS control |
| 410 | Maximum/RMS force convergence thresholds | Planned editable controls |
| 411 | Maximum/RMS displacement thresholds | Planned editable controls |
| 420 | Fixed-atom selection | Existing; explicit 1-based indices/ranges |
| 421 | Fixed coordinate components | Planned; current XYZ only |
| 422 | Distance/angle/dihedral hard constraints | Planned |
| 423 | Soft restraints / restraining potentials | Planned |
| 430 | CELL_OPT external pressure | Existing |
| 431 | Pressure convergence tolerance | Planned editable control |
| 432 | Cell degrees of freedom: axes/angles/etc. | Planned |
| 433 | Symmetry preservation | Planned |
| 440 | Optimizer Hessian initialization/reuse | Planned; not wavefunction restart |

Fixed atoms use fractional coordinates in the inspected CP2K definition; they
are not absolute-Cartesian pins during cell deformation. Generic optimization
controls live here; NEB/Dimer-specific settings live in category 800.

## 8. Category 500: output, restart and provenance

| ID | Function | Status / boundary |
|---:|---|---|
| 501 | Write provenance JSON | Existing; opt-in and exclusive |
| 502 | Input output path | Existing CLI and category editor |
| 503 | PROJECT name | Existing CLI and category editor |
| 504 | Target CP2K version | Existing CLI capability; not runtime identity |
| 510 | Trajectory format | Existing PDB/XYZ/EXTXYZ subset |
| 511 | Trajectory cadence | Planned |
| 512 | Force/velocity/stress printing | Planned configurable controls |
| 520 | Wavefunction restart writing | Planned switch; current output leaves writing enabled |
| 521 | Wavefunction restart backup count | Planned editable control; currently fixed to 0 |
| 522 | MOTION restart writing | Planned switch |
| 523 | MOTION restart backup count | Planned editable control; currently fixed to 0 |
| 524 | SCF initial guess / wavefunction restart reading | Planned; current suggestion is metadata only |
| 525 | Full optimization/MD continuation settings | Planned; explicit inheritance/override policy required |
| 530 | Molden output | Planned |
| 540 | PRINT_LEVEL / log detail | Planned editable control |
| 550 | Source/settings/validation summary | Existing read-only entrance |

Do not combine writing, backup retention, and restart reading into one ambiguous
switch. Never infer permission to overwrite wavefunctions or results. Preserve
existing narrow .inp replacement permission and exclusive JSON/export policies.

## 9. Category 600: properties and analysis inputs

Owns requests for calculated properties and specialized analysis input workflows,
not post-processing of existing results.

| ID | Function | Status / boundary |
|---:|---|---|
| 601 | CUBE output selector | Existing GPW subset: 0 None / 1 Electron density; UKS also prints spin density |
| 602 | Whole-system plus two-fragment density-difference inputs | Existing in 0.2.9; ENERGY/GPW/charge-conserving two-fragment subset |
| 603 | Spin-density output | Existing; current UKS output channels are coupled |
| 604 | Spin-density difference inputs | Planned |
| 605 | CUBE sampling STRIDE | Existing |
| 606 | ELF and other scalar fields | Planned |
| 607 | Selected-orbital CUBE output | Planned |
| 610 | Electrostatic/related potential fields | Planned; sign/meaning must be explicit |
| 611 | Electric-field output | Planned |
| 612 | Work-function calculation preparation | Planned |
| 620 | DOS | Planned |
| 621 | PDOS | Planned |
| 622 | Band-path calculations | Planned |
| 630 | Atomic population-charge analysis settings | Planned |
| 631 | Localized orbitals / Wannier-related settings | Planned |
| 640 | Vibrational analysis | Planned |
| 641 | Finite-displacement / phonon input preparation | Planned |
| 642 | IR/Raman-related preparation | Planned; method/workflow checks required |
| 650 | TDDFT / excited-state settings | Planned |
| 651 | Real-time electronic propagation / response | Planned |
| 652 | NMR settings | Planned |
| 653 | Polarizability/dielectric response | Planned |
| 654 | X-ray absorption-related settings | Planned |
| 660 | BSSE/counterpoise input preparation | Planned |
| 670 | Data preparation for external charge-analysis tools | Planned; not an external-tool execution switch |

Which property to calculate belongs here; general output formatting/retention
belongs to 500. A workflow may enforce shared output requirements through the
same underlying settings, never independent inconsistent copies.

### 9.1 Implemented 602 editor

Local options, not new global IDs:

```text
602. Charge-density difference inputs

1. Enable/disable
2. Define fragment A using whole-system atom indices
3. Review fragment B complement
4. Set whole/A/B charges and multiplicities (six integers)
5. Review atom mapping and common-grid settings
0. Back
```

Initial workflow boundaries:

- ENERGY calculations for the whole system and two complementary nonempty
  fragments; no separate fragment optimization.
- Select fragment A using positive 1-based indices/ranges in the selected frame /
  symmetry-expanded structure. Fragment B is its complement. Reject malformed,
  overlapping, out-of-bounds, or incomplete partition definitions as applicable.
- Preserve whole-system atom order. Fragment-local indices restart at 1 while
  retaining relative order; write an explicit whole-to-fragment atom mapping.
- Option 1 toggles immediately. Enabling CDD enables shared electron-density output
  and blocks disabling it through -3/601 until CDD is off; disabling CDD retains
  density output. Automatic output follows the source stem with -CDD.inp while
  enabled, .inp otherwise; explicit paths are unchanged.
- Option 2 prompts directly for indices; use 3/5 for an explicit mapping review.
- Option 4 accepts all_Q all_M A_Q A_M B_Q B_M as six integers and updates them
  together only after checking count, positive multiplicities and charge conservation.
  Enter/back preserve the old values. Component electron-count/parity validation
  still applies during review/generation. Fragment states remain explicit: do not
  infer neutral singlets or derive fragment spin from the whole-system spin.
- The implemented subset requires Q_total = Q_A + Q_B. Alternative partitions
  are deferred; never silently repair charge. All components need positive
  electron counts, so zero-electron fragments are not supported.
- Use one common cell, origin, PBC, fixed geometry, numerical/output settings, and
  corresponding per-element method/basis/potential choices. Never independently
  recenter fragments or rebuild their isolated boxes.
- No automatic ghost-basis addition. Document the density/basis convention.
- Keep current GPW density-output restrictions until additional models are
  independently validated; an AE menu choice does not certify GAPW cube meaning.
- Verify actual produced CUBE grids before subtraction. Matching requested input
  parameters is not proof of matching output grids.
- Existing cube-diff subtraction uses electron-number density, not an automatically
  signed electric-charge density; keep sign/units explicit.
- Offer read-only previews of all outputs/mappings and preflight collisions before
  publication. Generator-main 0 validates/writes directly; w reviews and confirms.
  Category/local 0 never writes. Keep rollback and overwrite policy explicit; do not
  assume a three-input workflow inherits unrestricted replacement permission.
- Reuse shared generation/config/replay and future batch-publication mechanisms.
  Do not fork a second chemistry generator inside the editor.

## 10. Category 700: molecular dynamics and sampling

These are planned nuclear/atomic dynamics controls. Electronic real-time
propagation belongs to 651 and has its own physical time/propagation parameters.

| ID | Function |
|---:|---|
| 701 | Ensemble / MD type |
| 702 | Time step |
| 703 | Number of steps |
| 704 | Target temperature |
| 705 | Target pressure |
| 706 | Initial velocities / velocity reset policy |
| 707 | Random seed |
| 708 | Overall drift / center-of-mass motion controls |
| 710 | Thermostat type |
| 711 | Thermostat time scales / parameters |
| 712 | Thermostat groups/regions |
| 720 | Barostat type |
| 721 | Barostat time scales / parameters |
| 730 | PIMD method / bead count |
| 731 | PIMD-specific integration/sampling |

Trajectory format/cadence remains 510/511. Multi-stage equilibration/production
input organization belongs to 1032, reusing these stage settings.

## 11. Category 800: reaction paths and free energy

All entries are planned.

| ID | Function |
|---:|---|
| 801 | Path task / endpoint structures |
| 802 | Initial-path generation/import |
| 803 | Image count / image list |
| 804 | BAND/NEB optimization controls |
| 805 | Climbing-image controls |
| 806 | Spring/path-convergence parameters |
| 807 | Dimer and other transition-state search specifics |
| 810 | Collective variables |
| 811 | Umbrella sampling |
| 812 | Metadynamics |
| 813 | Constrained scans |
| 814 | Free-energy integration and related protocols |

Validate atom identity/order, cells/PBC, endpoint compatibility, units, and
multi-structure provenance before preparing paths. Category 700 owns shared MD
controls, category 400 owns generic optimization controls, and this category owns
path/bias-specific settings. Post-processing NEB outputs is outside this menu.

## 12. Category 900: environment, fields and embedding

All entries are planned. Do not import another program's solvent/embedding
capabilities by analogy; check actual CP2K implementation and supported targets.

| ID | Function |
|---:|---|
| 901 | Implicit-solvation model |
| 902 | Dielectric constant / solvent parameters |
| 903 | Cavity / non-electrostatic contributions |
| 910 | External electric field |
| 911 | Time-dependent external field |
| 912 | External potential |
| 920 | Surface-dipole and related corrections |
| 921 | Additional charged/low-dimensional environment models |
| 930 | QM/MM coupling scheme |
| 931 | QM-region selection / boundary treatment |
| 932 | QM/MM electrostatic coupling |
| 940 | External point charges / electrostatic embedding |
| 950 | Other embedding models |

Basic PBC/cell/Poisson boundary choices stay in 200. Named regions can be reused
from 240; QM/MM interpretation/coupling stays here rather than duplicating a region
with an unrelated index convention.

## 13. Category 1000: calculation protocols and batch generation

All entries are planned. This category organizes related calculations; it does not
independently redefine functional, charge, spin, grids, or output settings.

| ID | Function |
|---:|---|
| 1001 | Calculation-protocol template |
| 1010 | CUTOFF convergence series |
| 1011 | REL_CUTOFF convergence series |
| 1012 | k-point convergence series |
| 1013 | Basis comparison |
| 1020 | General parameter scan |
| 1021 | U and other physical-model parameter scans |
| 1022 | Lattice/strain scans |
| 1030 | Optimization followed by single-point input preparation |
| 1031 | Optimization followed by vibration input preparation |
| 1032 | Multi-stage MD input organization |
| 1040 | Multi-structure batch generation |
| 1050 | Batch directories / naming rules |
| 1051 | Batch compatibility checks / generation summary |

Physical-model variation is not numerical convergence. Record each stage's
parameters, inheritance/overrides, sources and intended outputs. 602 can reuse
batch machinery without moving its scientific entrance away from category 600.
Submission, monitoring, external execution, and results post-processing remain
separate application concerns, never automatic consequences of preparing inputs.

## 14. Migration from the 0.2.8 extension numbers

This table records the 0.2.9 one-time UI migration, not backward-compatible
routing. Old numeric TUI scripts are not preserved by CLI/config compatibility.

| Old 0.2.8 ID | Setting | Implemented layout-v1 ID |
|---:|---|---:|
| 101 | Charge | 101 |
| 102 | Multiplicity | 102 |
| 105 | CUTOFF | 301 |
| 106 | REL_CUTOFF | 302 |
| 107 | Vacuum padding | 212 |
| 110 | OT ALGORITHM | 324 |
| 112 | ADDED_MOS | 341 |
| 120 | EPS_SCF | 303 |
| 121 | Inner/diagonalization SCF limit | 321 |
| 122 | Outer SCF limit | 322 |
| 123 | Optimization step limit | 402 |
| 124 | DFT+U | 112 |
| 125 | Magnetic initialization | 103 |
| 126 | Spin density | 603 |
| 127 | CUBE STRIDE | 605 |
| 128 | Element basis overrides | 221 |
| 129 | GTH-PBE approximation permission | 114 |
| 130 | Libxc assertion | 113 |
| 131 | GAPW profile | 225 |
| 132 | Write JSON | 501 |
| 133 | TRUST_RADIUS | 403 |

Conflicting old/new IDs cannot both be silently accepted: old 112 means ADDED_MOS,
whereas new 112 means DFT+U. Publish the migration and show clear labels/values
before generation. Do not guess which historical UI a bare number refers to.

Preserve semantic CLI/config keys, basis registry IDs/numbers and source atom
order. Review schema compatibility separately if workflows add fields; do not
change schema or package version simply because this draft exists.

## 15. Implementation and allocation rules

1. Implemented categories, migration and 602 follow the approved first scope;
   obtain a separate specification before implementing Planned entries.
2. Treat distant feature IDs as provisional until their workflows are understood;
   do not freeze all future numbers just to fill a table.
3. Once allocated as a stable function ID, do not recycle it for another meaning.
   Retire with an explicit unavailable/migration status if necessary.
4. Keep one implemented function/setting registry with category, aliases, semantic
   key, label and editor metadata. Reuse shared applicability rules; leave planned
   statuses in this document, not placeholder runtime entries. Do not maintain
   independent main, category and direct-access dispatch tables that can drift.
5. Preserve the shared InputSettings/generator/review/config/replay/writer path;
   workflow-specific additions need explicit scoped models, not parallel parsers.
6. Keep hidden values without emitting inapplicable controls. Direct access must
   use the same applicability checks as category browsing.
7. Validate all new keywords, nesting, units, method combinations and target
   versions. Planning labels are not implementation evidence.
8. Add tests for duplicate IDs/aliases, direct/category equivalence, return context,
   parameter/basis/atom namespace isolation, inapplicable/unknown numbers, source
   changes, replay/config compatibility, and safe multi-file publication.
9. Keep user results and ignored workspaces out of commits. No automatic expensive
   calculations, dependency additions, publication, commit or push.
10. Freeze the implemented subset and document its menu-layout revision when the
    feature round is ready; software, schema, menu layout and basis registry
    versions are separate concepts.

## 16. Initial development scope and deferred work

Implemented first round (0.2.9, menu layout v1):

- Category browsing plus full-number direct access.
- Migrate existing settings using the table above, keeping common shortcuts.
- Implement 602 for the explicitly supported two-fragment density workflow.
- Preserve CLI/config/replay, provenance, result protection and English maintained
  text; add focused tests and update actual user documentation.

Defer:

- Unimplemented 700-1000 functionality and advanced electronic/property models.
- Automatic molecule recognition, arbitrary multi-fragment partitioning, ghost
  conventions, and new GAPW density semantics until separately specified.
- Empty placeholder menus and unverified claims of complete CP2K coverage.

The implemented subset has layout v1; future IDs stay provisional. Optional
shortcuts -9/-6/-4/-2 and 5/7 listed above are not registered yet. Implementation,
validation, commit/push and publication remain separate steps. This document
and version number do not certify CP2K runtime behavior.
