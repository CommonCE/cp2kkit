# Multiwfn module provenance

This records facts, not permission inferred from labels such as "reference-based"
or "rewritten in another language". Prefer version/file/subroutine/SHA-256;
line numbers are auxiliary. Do not invent upstream commits, inspection dates, or grants.

## CP2K input generation

### Location and fixed source

- Local module: `src/cp2kkit/inputgen.py`
- Interfaces: InputSettings, generate_input, write_input
- CLI: `src/cp2kkit/cli.py`, generate-input
- Upstream: Multiwfn 2026.10.1
- Package: Multiwfn_2026.10.1_src_Linux
- User-provided local path: `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`
  (development locator, not runtime dependency)
- File: cp2kmate.f90
- Main subroutine: outCP2Kinp, lines 68-3448
- Related inspection: outCP2Kinp_wrapper, determine_vacuumsize
- SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`
- Provenance/hash review (UTC): 2026-10-13
- Applicable terms: [TERMS.md](TERMS.md)

### Actual references

- Tasks and GLOBAL/FORCE_EVAL/DFT/SUBSYS/MOTION organization.
- MOLOPT-GTH names and selected Nval valence-count entries.
- PBE/BLYP GTH potentials and D3/D3(BJ) configuration.
- Some grid/SCF/optimization defaults; not every default is identical.
- Density extension inspected E_DENSITY_CUBE/STRIDE 1 branches, lines 2599-2641,
  retaining both citations. Spin applicability, final-step frequencies, and file
  behavior were separately checked against CP2K 2024.1-2026.2 documentation/source:
  [cube guide](../../docs/cube.md). cube.py streaming/difference logic was not ported
  from Multiwfn's cube implementation.

### Implementation and differences

- Python GPW subset, not a line-by-line port or strict clean-room implementation.
  Original Fortran is not distributed.
- Only ENERGY/ENERGY_FORCE/GEO_OPT/CELL_OPT, PBE/BLYP, restricted MOLOPT presets.
- Element/basis/potential names separately checked against CP2K headers; optional
  local data verification/hashing.
- Conservative PBC/electron/combination checks; exclusive creation/JSON provenance.
- OT inner/outer limits follow upstream's enabled-outer branch, 25/20, enabled by
  default locally. Smearing empty-orbital auto uses max(30,NINT(ncenter/2)), not fixed 20.
  Optimization steps, low-dimensional Poisson, and cell construction still differ.
- Restart settings are not inherited; rebuild KIND by element.
- Detailed differences belong in development conversation, not a separate comparison
  document. Actual scope: [generation guide](../../docs/input-generation.md).

### Citations and authorization

- Required papers: [notices](../../THIRD_PARTY_NOTICES.md).
- Preserved in module docstrings, generated inputs, and JSON.
- No separate header copyright/license statement was found in the inspected
  cp2kmate.f90; absence is not evidence of no copyright.
- No separate integration permission; relicensing/paid-distribution boundaries unconfirmed.
- Python implementation does not automatically remove upstream conditions.

### Validation boundary

- Synthetic unit/CLI smoke checks, no CP2K execution.
- Comparison is static inspection of identified source, not equivalent output/
  calculation testing between Multiwfn and cp2kkit.

## Input-generation editor

### Location and fixed source

- Local: `src/cp2kkit/input_tui.py`, run_interactive/Menu/GROUPS.
- CLI: generate-input --tui/--interactive; original arguments retained.
- Upstream: Multiwfn 2026.10.1, Multiwfn_2026.10.1_src_Linux/cp2kmate.f90.
- outCP2Kinp: main numbered menu approximately lines 194-375; return/other settings 389-445.
- Development locator: `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`, not runtime dependency.
- SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Hash recheck (UTC): 2026-10-14; terms: [TERMS.md](TERMS.md).

### References and differences

- Repeated current-settings display, numbered editing, return, and final generation.
- Reimplemented using standard-library line interaction, not copied/distributed
  Fortran UI; no clean-room claim.
- Eight local groups with different numbering; only implemented GPW parameters.
- Retain local defaults, CLI seeds, source restrictions, scientific checks. Do not
  port all upstream options/session persistence/magnetic inference/automatic repairs/direct writes.
- Add previews, quoted replay commands, and default-no confirmation; no shell/CP2K execution.

### Citations, permission, validation

- Both papers remain in input_tui.py/shared input/JSON/notices.
- Original custom terms apply; no extra grant or confirmed relicensing boundary.
- Synthetic unit/CLI/PTY cases; no Multiwfn/CP2K execution or menu/result equivalence claim.

## Default entry and SCF/empty-orbital automatic values

### Location and source

- Local: cli.py, main_tui.py, input_tui.py, inputgen.py.
- Same Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp;
  actually rechecked hash: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Lines 2437-2440: diag 128, enabled-outer OT inner 25; lines 2487-2492: outer 20.
- Lines 1124-1134: smearing on assigns nADDED_MOS=nint(ncenter/2D0), minimum 30;
  turning it off assigns 0.
- Terms/citations/authorization unchanged: [TERMS.md](TERMS.md).

### Use and differences

- Use these formulas; Python (natoms+1)//2 implements Fortran positive half-integer rounding.
- Reference load-then-numbered-menu organization; application dispatch is locally
  implemented for existing functions.
- Not a complete menu/reader port. GJF/CIF/POSCAR are local strict standard-library
  readers, without referencing/distributing Multiwfn reader source.
- UKS dual-spin organization from lines 2525-2529 also used; ADDED_MOS integer-array/
  per-spin meaning separately checked in CP2K 2026.2 SCF documentation linked in the guide.
- Auto applies only to diag+smearing without explicit override. OT rejects smearing/
  nonzero empty orbitals instead of switching to diag. Auto follows current structures,
  not upstream session assignments.
- 400/55 Ry is the user's request, not claimed upstream provenance or system convergence.
- Application/dynamic hiding/auto checks are synthetic; no Multiwfn/CP2K run or full
  behavior-equivalence/scientific-sufficiency claim. Shared generator retains both citations.

## Local scrolling workflow redesign (0.2.4)

- Local: main_tui.py, input_tui.py, input_editor.py, presentation.py.
- This round reorganizes existing local actions, field definitions, and shared
  generator/writer calls into grouped application actions and one complete numbered
  generation menu with stable field numbers. Existing local visibility rules filter
  inapplicable fields without resetting values. The temporary step-based layout was
  replaced at the user's request, retaining version 0.2.4.
- Numbering refinement: re-inspected the same Multiwfn 2026.10.1 cp2kmate.f90,
  outCP2Kinp main menu (lines 200-365) and Other settings (lines 390-435).
  Rechecked SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
  Reuse main IDs -10 return, -7 PBC, -3 cube, -1 task, 0 generate, 1 method,
  2 basis, 3 dispersion, 4 SCF, 6 smearing, 8 k-points, 10 optimizer and 12 pressure
  for their implemented counterparts. Local prompts/capability limits still differ.
  Charge, spin, grids, padding and empty orbitals originate in upstream submenus;
  flattened local controls use explicitly separate 100+ IDs instead of claiming
  upstream main-menu numbers. Unsupported entries are omitted, not reassigned.
- Source/frame now appear in the header; output/project/target-version settings
  rows are removed. Generation still requires explicit confirmation; no physical
  defaults, original citations, or terms were changed. No Fortran source is copied
  or distributed; this is not a full UI or menu-choice equivalence claim.
- Optional Rich is terminal presentation only; batch serialization and the
  standard-library chemistry core do not depend on it.
- Navigation/menu numbers change from earlier cp2kkit releases; correspondence is
  limited to the inspected main-menu IDs above, not all upstream menus/choices.
  Synthetic/PTY checks do not establish upstream UI equivalence or scientific validity.
- Separate authorization remains unrecorded; no new permission or licensing claim.

## Explicit Hubbard U and collinear magnetic initialization (0.2.4)

### Sources and local implementation

- Local: inputgen.py, spin_settings.py, input_tui.py, input_editor.py, cli.py.
- Re-inspected the same user-provided Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp:
  Other settings 8/9, setup around lines 535-612, DFT_PLUS_U/MAGNETIZATION output
  at 1577-1601, UKS at 1739, and PLUS_U_METHOD at 1763.
- Rechecked SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Reference organization: element/atom selection splits atomic kinds, each kind
  carries its magnetic initial guess, DFT+U is KIND-local and uses U_MINUS_J/eV,
  and MULLIKEN projectors are selected in DFT. Original Fortran is not distributed.
- Independently checked exact keyword nesting/units against CP2K 2026.2:
  [DFT_PLUS_U](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/SUBSYS/KIND/DFT_PLUS_U.html),
  [KIND/MAGNETIZATION](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/SUBSYS/KIND.html),
  [DFT/UKS and PLUS_U_METHOD](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT.html).

### Differences and validation limits

- Local menu extensions 124/125 replace cell/data rows; those old controls remain
  CLI/API settings. These are not upstream main-menu IDs for Hubbard/magnetic settings.
- No default U=2 eV or inferred L is copied. Explicit nonnegative Ueff/L is required
  per element; one channel per element and MULLIKEN only. It applies to all split
  kinds of that element. No U/J separation, ramping, LOWDIN switch or occupation constraints.
- Element seeds plus individual 1-based atom overrides are locally parsed and split
  deterministically; atom order/coordinates are retained. Initial spin difference
  is not a local-moment constraint. UKS can be explicitly requested even for a singlet.
- Unlike upstream's magnetic-menu exit, total multiplicity is NOT recomputed from
  the sum of local initial moments. Charge/multiplicity conflicts are errors or
  warnings for explicit correction, never implicit physical-model repairs.
- New requests require target 2026.2. Synthetic input/round-trip/UI/CLI/provenance
  tests are not CP2K execution, shell/projector suitability, magnetic-state or U validation.
- Existing two Multiwfn citations and custom [terms](TERMS.md) remain applicable.
  No extra grant, full-port, clean-room, license-compatibility or release claim.

## GGA and basis profile extension (0.2.6)

- Local: method_profiles.py, data_catalog.py, inputgen.py and the shared CLI/editor.
- Re-inspected the same Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp, SHA-256
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`:
  basis names around 137-147, functional selection 939-999, q suffixes/potential
  policy around 1535-1575, Libxc RPBE 2015-2020, native parametrized PBE 2086-2092,
  and dispersion reference normalization around 2335-2349.
- Actual references: PBEsol/revPBE use PBE PARAMETRIZATION; RPBE separates exchange
  GGA_X_RPBE and correlation GGA_C_PBE; explicit basis q suffixes; RPBE D3 reference
  removes the upstream _LIBXC implementation suffix. Local canonical name is RPBE.
- Independent official CP2K v2026.2 checks: native XC parametrization, Libxc
  registration/name lookup, both D3 damping reference branches, repeated basis-file
  keyword, and exact basis/potential headers. data_catalog.py records all eight
  version-fixed URLs/raw-byte SHA-256 hashes; no upstream Fortran or coefficients
  are distributed. Header aliases/element/q/file metadata are derived, not inferred.
- TZV2PX matches an inspected upstream family; UCL triple-zeta SR and new element
  coverage were derived from official data, not claimed to be Multiwfn dropdown ports.
  Preserve the existing 71-element valence policy; do not substitute q2 for Mg-q10.
- Differences: explicit per-element mixed bases; no missing-family fallback. Prefer
  matched potentials (including B GTH-PBESOL-q3), and require approval for unmatched
  GTH-PBE approximations rather than reproducing upstream's unconditional fallback.
  RPBE requires a user target-build Libxc assertion. Gate new profiles to 2026.2;
  assertions/header checks are not native execution or scientific suitability.
- Supplied modc.py was read-only design reference for future UZH protocol migration,
  not executed/copied/redistributed. Its established hash and UZH source checks are
  recorded in [the roadmap](../../docs/roadmap.md#uzh-protocol-follow-up-modcpy-reference).
  Preserve data-library identity, not just shared aliases/q. In-place overwrites,
  forced numerical resets and regex migration are not implemented.
- The original two citations and custom [terms](TERMS.md) remain applicable.
  No new grant, full-port, clean-room or license-compatibility claim. Synthetic
  generation/round trips do not validate energies, forces/stress, magnetic states,
  convergence, projector-dependent U, or Libxc/runtime library availability.

## Permanent ORB registry follow-up (software 0.2.6, registry v1)

- Local: basis_registry.py, basis_resolution.py, cp2k_data.py, basis_ui.py and
  existing method_profiles/inputgen/CLI/editor adapters. Explicit numbers and
  stable IDs follow the user's requested contract, not an additional Multiwfn
  menu/table port. Existing earlier references/citations/custom terms are retained;
  no new Multiwfn source inspection or authorization is claimed for this follow-up.
- Primary evidence: actual tagged CP2K v2026.2 BASIS_MOLOPT (including SZV non-SR),
  BASIS_MOLOPT_UCL, BASIS_MOLOPT_UZH_2026.2 and POTENTIAL_UZH_2026.2. Versioned URLs
  and raw hashes are recorded in data_catalog.py and [the basis guide](../../docs/basis-selection.md).
  The UZH hashes match the established earlier read-only reference checks.
- New implementation indexes real aliases/headers, checks selected numerical
  payload structure and q, rejects ambiguous content/cross-KIND lookup shadowing,
  and records requested/real paths without inferring versions from filenames.
  The input_cp2k_dft.F reference confirms repeated basis files versus one potential
  file. No coefficients, potential parameters, Fortran routines or user modc.py
  code are copied/distributed. No in-place conversion or numerical resets.
- Read-only actual-data checks: 213 UZH-PBE pairs across the existing 71-element
  fixed-q policy, plus original SZV entries. PBE0 header presence is not method
  support: literal malformed element header at UZH basis line 5614 is not repaired,
  and PBE NA placeholders are not numerical potentials. Synthetic custom fixtures
  are invented parser data, not production scientific parameters.
- Version remains 0.2.6 by explicit request. Registry v1 separates new IDs from the
  earlier 0.2.6 positional menu; older names stay accepted and numeric migration
  is explicit. Validation is unit/interface/real-data parsing only, not native
  CP2K execution, convergence, physical suitability or upstream menu equivalence.
  No separate grant, clean-room, full-port or license-compatibility certification.

## All-electron GAPW and explicit OT algorithm (0.2.7)

- Local: gapw.py, all_electron_catalog.py, basis_registry/resolution, cp2k_data,
  inputgen and shared CLI/editor. Re-inspected Multiwfn 2026.10.1 cp2kmate.f90,
  outCP2Kinp, SHA-256
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Actual references: AE family names 151-158, GAPW selection 1078-1082, no-q AE
  orbital/nuclear ALL output 1536-1575, library mapping 1695-1700, GAPW method
  1860-1861, FULL_ALL for GAPW 2468-2471 and pob IRAC/other STRICT 2478-2483.
  User-requested basis numbers 50-59 and OT menu 110 are local allocations.
- Independent local CP2K evidence: user-supplied tree
  `/home/xwp/soft/cp2k-2026.2`, REVISION git:c92cc08. Exact data, keyword and
  GAPW example hashes are in all_electron_catalog.py. The local revision is not
  asserted equivalent to the named upstream release or an installed binary.
  input_cp2k_scf.F 583-592 verifies OT ALGORITHM STRICT/IRAC and native STRICT.
- Differences: explicit electron model and Z counting, no heavy/ECP or mixed
  model inference; whitelisted AE coverage; strict ALL payload/occupation checks;
  auto profile adds 110/80 atomic grids from the local water example and explicit
  native split tolerances. This is not the example's full numerical setup and
  does not inherit any upstream claim of convergence. PP defaults stay unchanged;
  explicit OT choices override profile suggestions, hidden diag values persist.
- Only header metadata/hashes and independently implemented validation/derivation
  are bundled, not upstream Fortran or production basis/potential parameters.
  Read-only actual data checks: 332 AE basis/nuclear pairs; unit/UI/CLI tests do
  not establish native acceptance, convergence or scientific fitness.
- Existing two papers/citations and custom [terms](TERMS.md) remain applicable;
  no separate grant, clean-room, full-port or license-compatibility claim.

## D3 whole-line filename serialization fix (0.2.7)

- Local: cp2k_data.cp2k_long_path and inputgen.py; no new Multiwfn port/reference.
  Preserve existing citations/custom terms and unconfirmed licensing boundaries.
- Actual failure evidence: user supplied a CP2K ABORT from common/cp_files.F:376
  and a generated `PARAMETER_FILE_NAME "dftd3.dat"` line with no literal internal
  leading whitespace. Running binary version/full output were not supplied.
- Inspected the same local CP2K tree, REVISION git:c92cc08:
  input_cp2k_xc.F defines PARAMETER_FILE_NAME with default_lc_val;
  input/input_parsing.F 526-584 and input/cp_parser_methods.F 535-559 use
  fixed-size chunks, including a quote-only first chunk; input/input_val_types.F
  398-413 joins chunks without left-stripping. common/cp_files.F 373-377 rejects
  a leading blank. This explains the observed failure path by static inspection,
  not execution of the user's binary.
- Exact inspected parser hashes: input/input_parsing.F
  `7a61a8ad06610de89a0b71dc907343655c29160ee8c30ee6d39e804e69bd0299`;
  input/cp_parser_methods.F
  `5bf3ae764d72d89a4a14d56db148883030c42bd84d92e2fc47bdf2ec2a5a98c3`;
  input/input_val_types.F
  `06587067b3ed6623d2f0fbcf81cde1fec4350129a975c26759bc6f3c4ff51e36`.
- Fix: literal whole-line path with shared injection validation and explicit
  rejection of ambiguous whitespace/comment edges; no global quote removal,
  physical setting changes, source/output overwrite or native-validation claim.

## Input-writing policy and library filenames (0.2.7 follow-up)

- Explicit user requests: unquoted basis/potential filenames, JSON off by default,
  and permission to replace generated .inp. These override the historical
  input-writer defaults recorded above, not protections on expensive results.
- Local keyword evidence: the same supplied CP2K tree, REVISION git:c92cc08,
  src/input_cp2k_dft.F 134-147 defines BASIS_SET_FILE_NAME and POTENTIAL_FILE_NAME
  as whole-line strings. Inspected raw SHA-256:
  `93887178d0208020a96826b794459bac9937a66cec8ff6a69b7d4e1d393d5648`.
  The shared literal serializer now covers all three library filename keywords;
  no native execution/all-version parser acceptance is inferred.
- Local write_input stages before replacing only regular .inp; structure/data
  sources (including hardlink aliases), symlinks and non-input results remain
  protected. Optional JSON retains exclusive creation and pre-publication failure
  leaves old input intact. Menu 132/--write-json is opt-in; stale JSON is retained
  and warned, never silently deleted. Analysis/export/plot/cube I/O is unchanged.
- No new Multiwfn algorithm or production parameters are incorporated. Existing
  citations/custom terms/unknown licensing boundaries remain unchanged.

## Universal NGRIDS and omitted GAPW controls (0.2.7 latest follow-up)

- Explicit user request supersedes earlier local profile-v1/v2 descriptions:
  NGRIDS=5 for every PP/AE and SR/non-SR basis; no EPSFIT/EPSRHO0/EPSSVD or
  LEBEDEV_GRID/RADIAL_GRID output in either profile. Numerical profile v3 retains
  GAPW/ALL and basis-aware/manual OT selection but leaves those controls to CP2K.
- This removes the local 110/80 example-derived override, rather than claiming
  it was a Multiwfn default. No new upstream source or numerical coefficients
  are incorporated. Omission resembles the inspected ordinary Multiwfn AE output
  style, not proof of convergence or runtime equivalence. Existing citations,
  terms, source hashes and authorization limits remain unchanged.

## Restart hints, trust radius and motion print (0.2.7 follow-up)

- Local implementation: inputgen.py generate_input/InputSettings; input_tui.py
  shared fields/review/replay; input_editor.py -5/133; cli.py argument dispatch.
- Reference: supplied Multiwfn_2026.10.1_src_Linux/cp2kmate.f90, outCP2Kinp;
  unchanged raw SHA-256
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
  Inspected lines 2414 (NGRIDS), 2453-2456 (SCF guess), 1727-1735
  (restart filename extension/comments), 3107-3120 and 3205-3212
  (optimization radii), 3360-3365 and 3392-3393 (MOTION print).
- Actual use: reference-based Python rendering of commented non-HFX restart hints,
  0.2 angstrom BFGS/LBFGS radius, trajectory and restart-backup templates.
  No original Fortran is distributed or required at runtime.
- Differences: all supported methods use inactive hints (hybrids remain unsupported);
  name derives from resolved PROJECT. Non-Gamma uses .kp, not a falsely named .wfn.
  XYZ is the default for both optimization tasks without task-switching resets;
  EXTXYZ is a local extension checked only for target 2026.2. Radius editing is
  local ID 133; CG hides/retains but does not emit it. The inspected CELL_OPT
  LBFGS branch does not explicitly set radius; this implementation extends the
  same explicit 0.2 value using the shared CP2K optimizer keyword definition.
  MOTION restart backup count is 0; SCF wavefunction backup defaults are unchanged.
- Grid comparison: upstream emits NGRIDS 5 only for ibas 3/4/5 (non-SR MOLOPT);
  other branches omit it. Local universal NGRIDS 5 is the explicit user policy,
  not exact upstream default equivalence. No other grid controls are added.
- CP2K static evidence: supplied local tree REVISION git:c92cc08, not assumed
  equivalent to an official release/binary from its directory name:
  - src/start/input_cp2k_motion.F 1323-1327 and 1569-1573 define BFGS/LBFGS
    TRUST_RADIUS in angstrom (defaults 0.25 and -1, respectively);
    SHA-256 `9371421ff8ace52ba452288647328d34b73cdc30fe421b052474c62734b5963b`.
  - src/input_cp2k_motion_print.F 250-260 / 319-323 define restart backups
    and trajectory XYZ/PDB/EXTXYZ;
    SHA-256 `33b63bf95fe3062f1865d3c6cb9ef54b174a8effe7dd196b897fcbe3ccb2b138`.
  - src/input_cp2k_scf.F 207-213 / 307-318 define ATOMIC guess default,
    restart filename RESTART and separate SCF backup controls;
    SHA-256 `23f7fdd4abfdf64904f0c95ed6dd672f6ca645c0abb7f91b60347ab6693bacf1`.
  - src/qs_mo_io.F 155 / 494-499 use .wfn/.kp; SHA-256
    `c257c64e756a61e1a4d00d9c80779b78a1f445d7bfc367c1746b47e5646449cc`.
  - src/kpoint_io.F 110 writes .kp; SHA-256
    `aea666edd4ea27f4fc8e14bc4567a1b20da1503e01c6d212e29184caf5c03a32`.
- Existing required 2012/2024 papers remain in generated inputs/manifests and notices.
  Multiwfn custom terms still apply; no separate permission or licensing
  compatibility is inferred from Python rewriting or source inspection.
- Validation: synthetic CLI/menu/config/replay/nesting/unit/boundary regressions.
  No CP2K/Multiwfn calculation or acceptance/convergence certification.

## Fixed atoms (0.2.8)

- Local modules: constraints.py parse_fixed_atoms/resolve_fixed_atoms;
  inputgen.py InputSettings/generate_input; input_editor.py menu 9 and atom table;
  input_tui.py shared field/review/replay; cli.py --fixed-atoms.
- Same supplied Multiwfn_2026.10.1_src_Linux/cp2kmate.f90, outCP2Kinp;
  SHA-256 `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
  Actual references: menu 9 at 295-302, index/range prompt at 1150-1173,
  MOTION/CONSTRAINT/FIXED_ATOMS with fractional XYZ and LIST at 3347-3354.
- Reference-based Python workflow/rendering, not a Fortran/str2arr port.
  Local parsing rejects malformed, duplicate/overlapping and active out-of-range
  selections before range expansion. Input is explicit 1-based indices/ranges;
  optH/element shortcuts and partial components are outside this first subset.
  Defaults remain unconstrained. Repeated LIST lines contain at most 20 indices.
- Differences: limited to GEO_OPT/CELL_OPT (not upstream MD/TS); source/frame
  changes retain indices with warnings, never silently clear/remap them.
  ENERGY/ENERGY_FORCE retain but do not emit hidden selections. Constraints
  from source/restart/POSCAR files are not inherited.
- CP2K evidence: supplied tree REVISION git:c92cc08, not inferred official/binary
  equivalence. src/input_cp2k_constraints.F create_fixed_atom_section, 334-377,
  defines fractional positions, COMPONENTS_TO_FIX XYZ and repeatable integer LIST;
  SHA-256 `2761dd6df4a1ab7200d50de32481aea2942dabbb92ab5562c722713b73bb360f`.
  Active selections are currently gated to target 2026.2. In CELL_OPT frozen
  fractional coordinates can move with the cell; this is not Cartesian pinning.
- Existing 2012/2024 papers and custom terms remain in force; generated
  inputs/manifests retain citations. No separate permission, whole-project
  license compatibility or clean-room exemption is inferred.
- Validation: synthetic index/range/bounds/nesting tests, CLI/menu/config/replay,
  selected frame/expanded CIF/KIND-order checks and non-destructive write checks.
  No CP2K/Multiwfn execution or scientific/convergence certification.

## Grid/OT/SCF backup/comment policy (retained 0.2.8 follow-up)

- Local gapw.py resolve_ngrids/resolve_gapw, inputgen.py generate_input, and shared
  CLI/menu/review/config/replay. Existing fixed-atom work is retained.
- Same supplied cp2kmate.f90/outCP2Kinp, SHA-256
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`:
  lines 145-147 identify ibas 3/4/5 as classic non-SR TZVP/TZV2P/TZV2PX;
  2414 emits NGRIDS 5 only for those choices; 2478-2483 select explicit OT
  IRAC for pob/CDFT, STRICT otherwise. This replaces the historical local
  universal-five-grid policy. Effective per-element overrides use any matching
  family; custom alias names do not establish a registry-family identity.
- Explicit user extension: all AE families now default to emitted IRAC, not just
  pob, in both legacy auto/native profiles. PP emits STRICT; manual choices win.
  Profile v4 omits NGRIDS for AE and keeps native QS/KIND numerical controls.
  This does not claim exact upstream algorithm/default equivalence.
- SCF restart backup evidence: supplied local CP2K REVISION git:c92cc08,
  src/input_cp2k_scf.F 307-318 defines SCF/PRINT/RESTART and BACKUP_COPIES;
  SHA-256 `23f7fdd4abfdf64904f0c95ed6dd672f6ca645c0abb7f91b60347ab6693bacf1`.
  New output explicitly sets zero backups without RESTART OFF; .wfn/.kp
  extensions follow the previously recorded writer evidence. No cadence or
  restart filename override is added. Generation never touches wavefunctions.
- Header-only comment policy is the user's formatting request. Inactive restart
  hints are removed, not activated. Suggestions remain metadata/review only,
  with emitted=false and runtime_verified=false. Safety/units stay in review,
  manifest and docs, rather than inline generated comments.
- Existing source/terms/citations and unknown authorization boundaries remain
  unchanged. No original Fortran, numerical payload or new licensing grant.
- Validation: synthetic family/override/OT/nesting/comment/config/replay checks.
  No CP2K/Multiwfn execution, installed-version equivalence or convergence proof.

## Uniform EPS_SCF (retained 0.2.8 follow-up)

- Explicit user request changes ordinary ENERGY default from the previously
  referenced Multiwfn 5e-6 to 1e-6, matching other supported task defaults.
  Same supplied cp2kmate.f90/hash above; lines 1778-1794 distinguish ordinary
  ground-state ENERGY (5e-6) from derivative tasks (1e-6) and tighter tasks.
- inputgen.py now uses 1e-6 only when eps_scf is unset; explicit CLI/API/config
  values are preserved. OT inner/outer share it; diag emits it once. EPS_DEFAULT
  and other physical/numerical requests are unchanged. Old inputs are not rewritten.
- This is a local policy override, not exact Multiwfn equivalence or an energy
  error bound in hartree. Existing terms/citations/authorization limits remain.
  Synthetic task/SCF/default/override regressions only; no native calculation.

## Template for future features

Copy this structure for each referenced feature and supply evidenced facts.
Register other authors' code separately and preserve notices.

```markdown
## <Feature>

### Location and fixed source
- Local module/function:
- Upstream version/package:
- Upstream file/subroutine:
- Source SHA-256 or an actual upstream commit:
- Registration/recheck date:
- Applicable terms:

### Actual references
- <Algorithm, workflow, tables, defaults, or code portions actually used>

### Implementation and differences
- <Reference-based implementation, rewrite, or direct port; no automatic exemption>
- <Behavior differences and verification sources>

### Citations and authorization
- <Citation/copyright preservation locations>
- <Additional method papers>
- <Separate grants, actual evidence/scope, or explicitly unknown>

### Validation boundary
- <Tests/unverified items; requested outcomes are not verified results>
```
