# Changelog

Software and data-schema versions are maintained independently.
This file records actual implementation changes, not publication to a package
repository or certification with actual CP2K calculations.

Versions use **A.B.C**: A is decided manually by the user; features increment B
and reset C; fixes increment C with A/B unchanged. A mixed feature/fix round
increments B once. Explicit user version requests take priority.

## 0.3.3

- Add BHandHLYP (50% HF), M06-2X (54% HF) and explicit-fraction PBEh through
  the shared direct-HFX generator; append chooser 19/20/21. Original DFT/xTB
  positions, basis IDs, physical defaults and protected writers are retained.
- BHandHLYP/M06-2X require --libxc-available. Emit their complete Libxc
  components and explicit HF, without double scaling. M06-2X records tau
  dependence and grid-convergence warnings.
- PBEh requires --pbeh-fraction A (dimensionless 0 < A <= 1; no default).
  Derive complementary PBE exchange/full correlation and HF from one profile.
  Reject malformed/non-finite/out-of-range or inactive retained fractions.
  Menu 120, CLI, config, replay and CDD share the same parameter/identity.
- Target remains CP2K 2026.2, GPW classic MOLOPT/UCL Gamma NONE/XYZ,
  ENERGY/ENERGY_FORCE/GEO_OPT, RKS/UKS and OT/diag without smearing or +U.
  Prefer matched potentials; otherwise all three new profiles use GTH-PBE,
  retaining approximation warnings and fixed q. No ADMM/RI-HFX or UZH-PBE0.
- M06-2X permits D3 (reference M062X), not D3(BJ); BHandHLYP/PBEh extra pair
  dispersion remains blocked pending a separate parameter/identity audit.
- Software 0.3.2 -> 0.3.3 is explicitly designated by the user; schema remains 0.1.0.
  Legacy configs default pbeh_fraction to null. All 21 referenced DFT choices
  now have bounded generation support, not full Multiwfn combination parity.
- Validation: 117 focused tests and 479 full regression tests passed; compileall,
  CLI version check and diff whitespace checks passed.
- User-authorized fresh generator comparison against Multiwfn 2026.10.18:
  64 pairs, all 128 generator processes exited 0. 62 pairs matched under documented
  numerical/default policies; two M06-2X-D3 cases retain an upstream reference-key
  mismatch (Multiwfn M06-2X versus the checked CP2K 2026.2 key M062X).
  All other checked XC/HF/data/geometry/task/spin/solver settings matched in 64/64.
  PBEh high-precision comparison explicitly allows upstream five-decimal rounding,
  not exact fraction identity. All 48 invalid-combination/overwrite checks passed.
  Raw inputs, commands, stdin, logs, hashes and JSON/CSV summaries are retained in
  test-workspace/hybrid-remaining-0.3.3-20261022-125352-T48M5s/.
  No CP2K execution, native acceptance, convergence or scientific-validation claim.

## 0.3.2

### Family-potential correction (version retained by explicit user request)

- Correct standard hybrid family-potential selection: B3LYP uses GTH-BLYP;
  PBE0/HSE06 use GTH-PBE when no actual exact-hybrid entry is supplied.
  Family selection no longer requires --allow-pbe-potential. Prefer verified
  exact-hybrid entries, preserve fixed q and actual file/entry hashes, and reject
  missing family entries rather than crossing families (even with approval).
- Keep existing potential_functional/potential_approximation provenance: family
  potentials remain semilocal approximations, not exact-hybrid potentials.
  Warnings distinguish automatic family policy from user-approved PBE fallback.
  Other functionals retain their approval requirements. No schema change,
  XC/HFX composition change, CP2K execution or scientific-validation claim.
- Hide inactive menu 114 for these three hybrids, retaining hidden values for
  other functional selections. CLI/config compatibility is preserved.
- Validation: 44 focused and 476 full regression tests passed. Regenerated 63
  cp2kkit cases without approval and compared against preserved real Multiwfn
  2026.10.18 inputs: XC/HF, geometry/task/spin/solver and selected basis/potential
  payload checks passed for all cases, allowing documented numerical-policy
  differences. No new Multiwfn run or native CP2K validation in that comparison.
- Version retained at 0.3.2 by explicit user request. Fresh B3LYP retest ran both
  cp2kkit and Multiwfn 2026.10.18 for 21 cases without approximation approval:
  all semantic/data-payload checks passed, with known numerical-policy differences
  retained. Package/CLI/generated-manifest versions are 0.3.2; 21 focused and
  476 full regression tests passed. No CP2K execution or convergence claim.

### Initial direct-HFX implementation

- User-designated version: add PBE0 → HSE06 → B3LYP direct-four-center HFX
  input generation through the shared API/CLI/TUI/config/replay/writer.
  Preserve original 15 DFT positions and xTB 30/31/32; append local 16/17/18.
  Menu 120 edits HF controls; 121/122 remain planned RI-HFX/ADMM.
- Emit complete native XC/HF compositions: PBE0 25%; HSE06 25% short-range HF
  with matching XC/HF omega=0.11 bohr^-1; B3LYP 20% with explicit VWN3
  (Gaussian/Multiwfn convention, not the CP2K shortcut's VWN5).
- Initial scope: target CP2K 2026.2, GPW classic MOLOPT/UCL orbital bases,
  Gamma NONE/XYZ ENERGY/ENERGY_FORCE/GEO_OPT, RKS/UKS, OT/diag without smearing
  or +U. Existing density/CDD generation is reused. GAPW, CELL_OPT, non-Gamma,
  low-dimensional PBC, UZH-PBE0/custom orbital protocols, ADMM and RI-HFX are
  not enabled. BHandHLYP/M06-2X/configurable PBEh remain deferred.
- Isolated globals use COULOMB; periodic globals use TRUNCATED. Auto radius is
  min(6 angstrom, minimum emitted-cell face spacing/2.01), including skew cells.
  Explicit radii must be below half the minimum spacing; no automatic clipping,
  cell/solver/model changes or restart-dependent initial-P screening.
- Add --hf-eps-schwarz (default 1e-6), --hf-memory (512 MiB per MPI process,
  not total job memory), --hf-cutoff-radius [angstrom; periodic globals only].
  SCREEN_ON_INITIAL_P=F and EPS_STORAGE_SCALING=0.1. Nondefault inactive HF
  requests fail on pure DFT/xTB instead of being silently ignored.
- Reuse checked basis/potential resolution and explicit GTH-PBE approximation
  approval. UZH-PBE0 basis numbers remain unavailable with corrected reasons.
  For TRUNCATED, --data-dir requires/protects/hashes t_c_g.dat; without it,
  emit an unchecked runtime basename and warning. No numerical data bundled.
- Schema remains 0.1.0 with additive native XC/HFX metadata, units, effective
  operator/radius, resource policy and tagged-source provenance. Existing pure
  DFT/xTB input physics and protected publication semantics are unchanged.
- Validation is source/manual inspection and synthetic generation/regression
  tests only; no CP2K run, submission, native syntax acceptance, convergence
  or property-validation claim. No commit, push or package publication.

## 0.3.1

- GFN2 OT crash-protection follow-up (version retained): reject OT generation
  for legacy CP2K targets 2025.2/2026.1 before publication; require explicit
  --scf diag/menu 320 instead of silently changing the solver. Shared version
  policy adds gfn2_ot_enabled; target 2026.2 retains OT generation without any
  runtime-certification claim. Native crash evidence is from local 2026.1;
  2025.2 is conservatively restricted without native execution. Prior authorized
  water tests found diagonalization converged on local 2026.1 and OT converged
  on local 2026.2/git:c92cc08, not necessarily an unmodified official release.
  Add API/config/replay/CLI/TUI and no-publication regressions; schema stays 0.1.0.
  No new native calculation, CP2K patch or automatic resubmission in this fix.
- Parser compatibility follow-up, retaining 0.3.1 by explicit user request:
  accept `[hartree]` as well as `[a.u.]` on total FORCE_EVAL energy records.
  Preserve hartree values, source text/lines/hashes, complete numeric-token
  boundaries, malformed/non-finite handling and conservative quality rules.
  Add synthetic unit/boundary/segmentation and CLI regressions. This follow-up
  rechecks existing local native output only; no new calculation is run and no
  GFN2 runtime fix or non-SCC quality-rule change is implied. Schema stays 0.1.0.
- Add a distinct DFT/GFN-xTB method dispatch, not three fake XC functionals:
  30 GFN1-xTB, 31 GFN0-xTB and 32 GFN2-xTB match the inspected Multiwfn
  chooser. Keep existing DFT positions, function IDs and basis registry stable.
  Method chooser 1/110, model selector 140, tblite assertion 141 and accuracy 142
  share CLI/API/config/replay generation. Hybrids remain deferred.
- Expand compatibility within the user-designated 0.3.1 round: GFN1 supports
  2024.2/2024.3/2025.1/2025.2/2026.1/2026.2, GFN0 starts at 2025.1, and GFN2
  starts at 2025.2 with tblite linked. Reject unavailable upstream models without
  fallback. Emit legacy GFN1 filenames/no GFN_TYPE on 2024.x; legacy TBLITE T
  activation on 2025.2/2026.1, new backend/mixer/accuracy controls only on 2026.2.
- Keep H-Rn, isolated Gamma closed-shell ENERGY/ENERGY_FORCE/GEO_OPT. GFN0
  is non-SCC; GFN1 and target-2026.2 GFN2 support default OT/FULL_SINGLE_INVERSE
  or explicit diag. The earlier universal removal of the GFN2 diag-only gate is
  superseded by the legacy-target crash protection above. OT convergence uses EPS_SCF;
  native tblite SCC with diag on 2026.2 uses ACCURACY. Legacy GFN2 diag uses
  CP2K direct-P mixing. Unsupported nondefault ACCURACY requests fail explicitly.
- Pin target-specific parameter/D3 identities and source hashes. Reuse shared
  fixed-atom resolution with audited target references for xTB without relaxing
  the existing DFT gate; xTB EXTXYZ output starts at target 2026.1.
- Retain intrinsic model dispersion, use xTB reference occupations rather than
  GTH valences, omit DFT basis/potential/XC/grid/Poisson controls. Reject unsupported
  periodic/open-shell/CELL_OPT/density/CDD/+U, additional pair corrections, DFT
  overrides and parameter refits without automatically changing requested physics.
- Check pinned native model/D3 bytes via data_dir/CP2K_DATA_DIR, record/protect
  sources; unchecked runtime references and tblite built-ins remain unverified.
  Native PARAMETER filenames are char_t paths (quote when needed), distinct from
  DFT whole-line filenames. No production numerical parameters are bundled.
- Reuse geometry, optimization/constraint rendering and staged single-input writing.
  Keep replacement/JSON/symlink/data protection, default DFT physics and schema 0.1.0.
  Add synthetic model/invalid-combination/menu/CLI/replay/overwrite regressions.
  No CP2K/Multiwfn/tblite execution, build detection or scientific validation.

## 0.3.0

- Add ten non-hybrid XC profiles to the original five: PADE, BP86, TPSS,
  revTPSS, SCAN, r2SCAN, MN15L, HLE17, B97M-rV and BEEF-vdW. Reference
  Multiwfn 2026.10.1's actual XC/nonlocal definitions; preserve the original five
  chooser positions. Share canonical names/aliases across CLI, TUI, config and API.
- Emit complete B97M-rV (Libxc MGGA_XC_B97M_V + rVV10 b/C=6.0/0.01) and
  BEEF-vdW (native BEEFVDW + required LMKLL) definitions. Both retain intrinsic
  correlation when additional dispersion is none; reject extra D3/D3(BJ).
  Read/hash kernel files when data_dir is supplied and protect them from output
  replacement. Unchecked runtime filenames and source-byte-only checks are
  explicitly distinguished from numerical kernel/runtime validation.
- Gate all new profiles to target CP2K 2026.2. Require explicit Libxc-build
  assertions for meta-GGAs and BEEF-vdW (native shortcut needs Libxc PW92), as
  already required for RPBE. Initial meta-GGA/nonlocal subset: GPW Gamma
  ENERGY/ENERGY_FORCE/GEO_OPT without +U; reject GAPW/non-Gamma/CELL_OPT/+U
  rather than silently changing physics. Existing semilocal restrictions remain.
- Add audited header-only PADE/BP potential coverage and real BP86 -> GTH-BP
  mapping at unchanged q. Prefer actual matched potentials; missing matches need
  explicit PBE-approximation approval. UZH-PBE remains PBE-only. No production
  basis/potential/kernel coefficients or Fortran are bundled.
- Whitelist additional pair corrections per profile against the inspected CP2K
  tables: BP86/TPSS/revTPSS/SCAN allow D3 and D3(BJ), r2SCAN D3(BJ), MN15L D3;
  PADE/HLE17 allow neither. Retain the original five correction combinations.
- Add XC family/components, native shortcut/parametrization, zero exact exchange,
  kinetic-density/scope and nonlocal/kernel metadata. Lock nonlocal identity
  across density-bundle components. Schema remains 0.1.0; basis/menu registry v1,
  CLI/config/replay names and default PBE input text/physics are retained.
- Validation: 430 regression tests passed, none skipped. User-authorized actual
  generator testing against Multiwfn 2026.8.31 passed 95 paired H/O cases and
  79 negative CLI checks. Development reference remains Multiwfn 2026.10.1;
  the executed binary is a different version. Complete XC/nonlocal/dispersion
  semantics and selected H/O data payloads matched in the tested matrix.
  No CP2K execution, convergence/property certification, installation/new dependency,
  hybrid/HFX/ADMM, xTB, submission or package publication.

## 0.2.9

- Emit portable BASIS_MOLOPT_UZH / POTENTIAL_UZH names for default UZH-PBE
  inputs (UZH AE bases only change the basis reference). Keep explicit file
  overrides and resolved source/hash provenance; record emitted_data_files
  separately. Runtime generic aliases must resolve to the intended data.

- Suggest <source-stem>-CDD.inp when CDD is enabled with automatic TUI naming,
  including initially seeded CDD and subsequent source changes. Disabling CDD
  restores the ordinary name; explicit user paths and bundle collision protection
  remain unchanged.

- Return from successful input generation immediately without an extra
  Enter-to-return prompt; the parent application menu resumes automatically.

- Default whole-system multiplicity to electron-parity selection: even -> 1,
  odd -> 2, with neutral charge still the default. Use selected PP/AE electron
  counts minus charge; preserve explicit spin requests. Menu 102 supports auto
  and displays its effective value. Resolved input/JSON records an integer;
  CDD fragment states remain explicit. This does not predict ground-state spin.

- For all tasks, generator-main 0 directly validates/writes inputs without review
  or confirmation; optional JSON still follows 501. Category/602
  0 only returns, and w retains review/confirmation. Make 602 option 1 an immediate
  on/off toggle without an extra Boolean prompt.

- Make -3/601 a numbered cube selector (0 None, 1 Electron density), limited
  to implemented types. UKS also prints spin density; None clears both requests.
  Enabling CDD in 602 automatically enables the shared density request and blocks
  disabling it while CDD is active; disabling CDD retains density output.

- Simplify 602 option 4 to a single six-integer charge/multiplicity entry for
  whole/A/B, including the shared total state. Show all three pairs in the menu.
  Validate integer count, positive multiplicities and charge conservation before
  updating any values; Enter/back preserve the old values. CLI/schema unchanged.
- Omit the automatic per-atom listing when selecting fragment A in 602; prompt
  directly for indices. Explicit mapping reviews remain available through 3/5.
  Fixed-atom and magnetic editors retain their coordinate tables.

- Implement menu layout v1: compact common shortcuts, category browsing with full
  IDs, direct access from main/categories, origin-preserving edits and shared
  applicability. 500 is output/provenance; 600 is properties. Future/empty
  categories are not shown. No full-screen UI or new dependency.
- Migrate local 100+ function numbers explicitly. Old 112 ADDED_MOS becomes 341;
  new 112 is DFT+U. Old numeric TUI scripts need migration; semantic
  CLI/config/replay names and immutable basis registry v1 numbers are unchanged.
- Add category editors for existing source/data/cell/output/project/version
  controls, transactional custom file/alias pairs, and read-only summary 550.
- Add 602 / --density-difference for ENERGY GPW whole/A/B density input bundles.
  Require explicit fragment charges/multiplicities, nonempty complementary
  1-based partitions, charge conservation and component electron-count parity.
  Keep relative atom order, record CSV mapping and map magnetic atom seeds.
- Resolve whole-system geometry once; retain a common cell, PBC, origin
  convention and numerical settings. Freeze whole-system derived SCF defaults
  and NGRIDS policy across fragments; compare selected per-element basis,
  potential and data-source identities. Actual output CUBE grids remain unverified.
- Publish three inputs and mapping together, optional combined JSON, exclusively.
  Preflight collisions and roll back only our own files on ordinary publication
  errors/interrupts. No existing bundle target is replaceable; not a crash-atomic
  multi-file transaction. Ordinary single-input replacement policy is unchanged.
- Retain 0.2.8 numerical defaults, constraints, restart/comment policy and schema
  0.1.0. Menu-layout metadata and workflow settings/manifests are additive.
- No ghost basis, separate relaxation/centering, spin-density difference workflow,
  AE density semantics, arbitrary multi-fragment partition, CP2K execution,
  convergence certification, commit or publication is implied.
- Latest validation: 403 tests passed, none skipped, including new menu/workflow
  methods, migrated UI regressions and follow-up parity/cube/naming/navigation cases;
  compileall, CLI version, maintained-text/link and diff checks passed. Includes CLI subprocess and real PTY smoke, data-hash mutation,
  bundle collision/race/rollback, config/replay and shared-grid geometry checks.

## 0.2.8

### Uniform SCF threshold follow-up (version retained)

- Change ENERGY default EPS_SCF from 5e-6 to 1e-6 by explicit user request;
  all supported tasks now default to 1e-6. Apply equally to OT inner/outer and
  diagonalization. Explicit --eps-scf/API/config values still take priority.
- Keep task-dependent EPS_DEFAULT, physical settings and existing generated files
  unchanged. This deliberately differs from Multiwfn ordinary single-point defaults,
  not a claim of convergence or a 1e-6 hartree energy-error guarantee.
- Validation: 346 tests passed, including all-task/SCF/default/override checks.

### Grid, explicit OT, wavefunction backups and comment follow-up (version retained)

- Follow Multiwfn's NGRIDS emission branch: 5 only for effective classic non-SR
  TZVP/TZV2P/TZV2PX-MOLOPT-GTH, omitted otherwise (metadata null). Explicit
  element overrides use actual effective families; custom names are not inferred.
- Always emit OT ALGORITHM: PP STRICT / AE IRAC, including both legacy AE
  auto/native profile names. Manual selections still win; diag emits no OT.
  This all-AE IRAC policy is an explicit user extension, not Multiwfn equivalence.
- Set DFT/SCF/PRINT/RESTART BACKUP_COPIES 0 in all tasks, separately from MOTION
  restart backups. Wavefunction writing stays enabled; existing files are not
  modified by generation. Add effective wavefunction_output metadata.
- Retain only generator/Multiwfn opening comments. Remove explanatory comments
  and inactive restart directives without enabling restart reads. Keep filename
  suggestions in metadata/review (emitted=false). Numerical profile is now v4;
  schema and software versions stay 0.1.0 / 0.2.8.
- Validation: 345 tests passed, including eight additional policy regressions;
  no native calculation. Earlier 0.2.8 fixed-atom work follows below.

- Add optimization main-menu 9 Fixed atoms and CLI --fixed-atoms. Explicit
  1-based indices/ranges (1,3-5,8), off/none/0 clears; default off. Preserve
  existing menu IDs and all unconstrained input defaults.
- Share compact selection parsing and source-bound resolution across CLI, menu,
  config and replay. Reject invalid, duplicate, overlapping or out-of-bounds
  active selections; validate bounds before expanding ranges.
- Emit MOTION/CONSTRAINT/FIXED_ATOMS with COMPONENTS_TO_FIX XYZ and repeated
  bounded LIST lines for GEO_OPT/CELL_OPT. Active constraints currently require
  target 2026.2; ENERGY/ENERGY_FORCE retain but do not emit hidden selections.
- Display the loaded/expanded atom table and warn after source/frame changes:
  indices are retained, never silently remapped. Do not inherit source constraints.
- Explain fractional-coordinate semantics, particularly moving Cartesian positions
  during CELL_OPT, and warn when all atoms are fixed.
- Add settings.fixed_atoms and effective constraints metadata; schema remains
  0.1.0. Older configs default to unconstrained. Keep local source evidence
  distinct from installed/runtime verification; register Multiwfn references.
- Validation: 337 tests passed with no skips, including 22 focused synthetic
  constraint methods; compileall, CLI version, documentation links/text and diff
  checks passed. No CP2K execution.

## 0.2.7

### Restart and optimization-output follow-up (version retained)

- Replace active SCF_GUESS ATOMIC with commented SCF_GUESS RESTART and
  WFN_RESTART_FILE_NAME hints. Names follow PROJECT, .wfn for Gamma/.kp otherwise;
  no restart is read or enabled by generation.
- Emit BFGS/LBFGS TRUST_RADIUS [angstrom] 0.2 for GEO_OPT/CELL_OPT; expose
  --trust-radius / main-menu 133. CG hides/retains but does not emit the value.
- Add optimization trajectory format PDB/XYZ/EXTXYZ via --trajectory-format and
  main-menu -5, default XYZ. EXTXYZ is checked only for target 2026.2.
  Add MOTION/PRINT/TRAJECTORY and MOTION/PRINT/RESTART BACKUP_COPIES 0.
  Explain cell/precision loss and that zero backups does not disable restart writing.
- Record inactive restart_template and effective motion_output in the manifest;
  preserve hidden settings through config, menu and replay. Keep schema 0.1.0.
- Inspect Multiwfn's NGRIDS logic: only ibas 3/4/5 explicitly emit 5.
  Retain the user's separate universal NGRIDS=5 policy and omitted GAPW controls.
- Add 17 focused regression methods; native execution remains unverified.

### Universal five-grid/default-GAPW follow-up (version retained)

- Default NGRIDS to 5 for every basis, including pseudopotential SR. Use one
  shared constant for rendering and metadata; do not infer grid count from names.
- Stop emitting EPSFIT, EPSRHO0, EPSSVD, LEBEDEV_GRID and RADIAL_GRID in both AE
  profiles. Remove the 110/80 override; CP2K defaults now apply. Retain GAPW/ALL,
  core-inclusive electron counts and basis-aware/manual OT algorithm selection.
- Numerical profile_version=3; qs/kind metadata maps are empty and
  cp2k_default_controls records omitted settings, not guessed runtime values.
  CLI/menu descriptions and docs match the reduced profile. No old input rewrite
  or claim that default numerical controls are converged for any property.
- Validation: 298 tests passed with no skips, including all enabled builtin bases
  at NGRIDS=5 and every AE family/profile omitting the five controls. Historical
  regression restores only grid count/library quotes before checking old bytes.

### Earlier 0.2.7 implementation stages (historical)

### All-electron five-grid follow-up (version retained)

- Change AE NGRIDS from 4 to 5 in both auto/native profiles by explicit user
  request. Increment numerical profile_version to 2 for traceability; software
  remains 0.2.7. Rendering/review/JSON agree; PP SR/non-SR policy and requested
  CUTOFF/REL_CUTOFF remain unchanged. No old inputs are rewritten.
- Explain the local auto-profile QS split tolerances and KIND atom-centered grids:
  Multiwfn does not explicitly output these five parameters in ordinary AE setup.
  Their existing values are retained, not removed by inference from a question;
  native omits them. No accuracy/convergence or native-execution claim.

### Input-writing follow-up (version retained by explicit request)

- Emit BASIS_SET_FILE_NAME and POTENTIAL_FILE_NAME without quotes, using the
  shared whole-line filename serializer (literal internal spaces preserved;
  ambiguous comment/injection characters rejected). Physical defaults unchanged;
  default input bytes/hashes intentionally differ by library filename quoting.
- Default to input-only output. Add --write-json / main-menu 132 (off by default)
  for optional provenance JSON. generate_input still returns its manifest in memory;
  write_input's second return value is null when JSON is disabled.
- Permit replacement of existing regular .inp targets only, with staged atomic
  publication and menu confirmation. Refuse source/data aliases, symlinks,
  directories and existing non-.inp results. Optional JSON remains exclusive;
  its collision/serialization/publication failure preserves previous input.
  With JSON off, existing sidecars remain untouched and are warned potentially stale.
- Analysis/export/cube/plot writers and expensive calculation results remain
  protected. No CP2K execution or new dependencies.
- Validation: 295 tests passed with no skips, including 16 focused input-writing
  cases; compileall/version/docs/diff checks passed. Legacy input regression
  confirms only library filename quote removal changes the default text.

### D3 filename fix (version retained by explicit request)

- Fix generated D3/D3(BJ) `PARAMETER_FILE_NAME`: serialize a literal unquoted
  whole-line value rather than a quoted ordinary string. The inspected CP2K
  lchar_t parser can turn the first quote chunk into a blank prefix, triggering
  `The file name < ... dftd3.dat> has leading blanks.` in cp_files.F.
- Keep literal internal spaces and absolute paths. Reject leading/trailing
  whitespace, comment markers and injection characters rather than stripping or
  renaming user paths. The subsequent input-writing follow-up extends this
  whole-line serializer to BASIS_SET_FILE_NAME/POTENTIAL_FILE_NAME too.
- Preserve all methods/physics, analysis/schema/exit contracts and protected
  outputs. This D3 fix did not itself rewrite existing inputs. Add five synthetic path regressions;
  no CP2K execution or all-version parser compatibility certification.
- Validation: 279 tests passed with no skips; compileall, CLI version, local
  documentation links/text and diff checks passed.

### All-electron and OT additions

- Add immutable all-electron ORB choices 50-59: Pople, def2, pob and UZH-PBE-ae.
  Preserve all previously allocated numbers/IDs; split unused reservation 40-59.
- Selecting AE automatically derives GAPW, ALL nuclear potentials, real basis files
  and sum(Z)-charge electron counts. Validate actual ALL occupations/payloads and
  distinguish nuclear charge from pseudopotential q/valence metadata.
- Add versioned `gapw_profile=auto`: five grids (numerical profile v2), explicit native split tolerances,
  angular/radial grids 110/80, FULL_ALL and pob IRAC (otherwise STRICT for OT).
  `native` omits added numerical conveniences, not required GAPW/ALL semantics.
  Preserve user charge/spin, XC/dispersion, cutoff/rel_cutoff, SCF and periodicity;
  review/JSON/warnings disclose derived settings and unverified convergence.
- Add main-menu **110 ALGORITHM**, OT-only IRAC/STRICT with optional auto reset;
  explicit choices override the AE profile. Hide but retain for diagonalization.
  CLI `--ot-algorithm` and replay/config use the same setting and validation.
- Enable audited H-Kr subsets only: 332 basis/nuclear-potential pairs read from
  the supplied local CP2K tree (REVISION git:c92cc08; upstream equivalence not
  inferred from directory name). No coefficients/potential parameters bundled.
- First AE scope: Gamma ENERGY/ENERGY_FORCE/GEO_OPT; no mixed AE/PP, heavy ECP
  branches, AE +U, CELL_OPT/non-Gamma or GAPW density cubes. These are generator
  restrictions, not assertions that CP2K generally lacks these capabilities.
- Default PP input text/physics and protected writes remain unchanged. Generator
  JSON gains electron-model/nuclear-charge/profile fields and two settings;
  schema stays 0.1.0, analysis/CSV unchanged. No CP2K runtime certification.
- Validation: 274 unit/interface tests passed (20 AE/OT methods), no skips;
  compileall/version/docs/diff checks and 10 local reference hashes checked.
  Default PP water input bytes match the preceding committed generator.

## 0.2.6

### Permanent basis registry follow-up (version retained by explicit request)

- Add explicit immutable number/string-ID registry v1, independent of display
  order/filtering and real data aliases. Establish the numbering contract toward
  1.0.0, not a 1.0.0 release. Separate ORB/AUX_FIT/RI_AUX roles; only ORB is selectable.
  Reserve ranges, retain unavailable PBE0 IDs 30-32, and use custom ORB 900.
- Keep classic 1-5 meanings from the requested contract; allocate 6-9 and 20-22
  explicitly. Earlier menu list positions differ and are not silently reinterpreted.
  Accept legacy family-name configs/CLI, persist stable IDs and provide explicit
  legacy-version numeric migration. Registry-v1 metadata disambiguates the two
  editors sharing software 0.2.6; current numeric configs are rejected.
- Add audited SZV non-SR and paired UZH-PBE DZVP/TZVP/TZV2P, each UZH-PBE family
  matching all 71 existing fixed-q presets. Use real PBE/GGA aliases and paired
  potentials, not classic GTH_POTENTIALS renames. PBE0 headers do not enable hybrid
  templates; preserve the anomalous source header and exclude NA placeholders.
- Parse actual supplied basis/potential entries, aliases, q and numerical structure;
  reject header-only/partial/non-finite/conflicting-q entries. Reuse read-only
  hashing, directory discovery and protected writing; accept explicit files and
  CP2K_DATA_DIR. Reject differing alias content and final-library shadowing rather
  than guessing by file order. Emit deduplicated real paths; reject requests that
  need multiple potential files instead of silently merging/replacing protocols.
- Custom 900 accepts literal files/names, shares validation, records unknown basis
  q as unknown/unverified, and does not certify role/physical pairing. Show grouped
  scrolling choices and full pre-write KIND summaries. Record IDs/numbers, final
  names, q, real/requested paths, entry/full hashes and identifiable versions.
  No files yields unverified_template; data_checked never means runtime acceptance.
- Keep default input physics, q, spin/U, cutoff/SCF and analysis JSON/CSV unchanged.
  Schema remains 0.1.0; generator settings now serialize stable basis IDs and gain
  documented registry/source/validation metadata. No new input comment inventory.
- Validation: **254 tests passed, none skipped**, including 38 new registry methods;
  compileall, diff, version and documentation-link/text checks passed. Read-only
  real tagged data checks covered 213 UZH-PBE element/q pairs. Default synthetic-O
  input bytes match commit 229d09d. No CP2K/Multiwfn execution, dependencies added,
  submission, publication, commit or push. See [basis selection](docs/basis-selection.md).

### Initial explicit GGA and basis profiles

- Add native PBEsol/revPBE parametrized PBE and Libxc RPBE (GGA_X_RPBE + GGA_C_PBE).
  RPBE requires an explicit user assertion of target-build Libxc support; the tool
  does not install/probe Libxc or execute CP2K. New profiles require target 2026.2.
- Add TZVP-MOLOPT-SR-GTH, TZV2P-MOLOPT-SR-GTH and TZV2PX-MOLOPT-GTH. Header-only
  catalogs pin tagged v2026.2 URLs/hashes and actual element/q/file availability.
  Expand non-SR DZVP to Cu/Br and TZVP/TZV2P/TZV2PX to Br using UCL entries.
  The SR triple-zeta families cover 54 current preset elements, not H/C/N/O.
  Existing 71-element valence presets stay fixed; Mg-q2 does not replace Mg-q10.
- Add explicit --basis-overrides / menu 128 for element-specific mixed bases.
  Apply overrides to all split magnetic KINDs while preserving atom order, +U,
  charge and multiplicity. No implicit family/q fallback. Emit and independently
  check/hash each required basis library. NGRIDS follows actual KIND bases.
- Prefer checked matched-functional potentials, including B GTH-PBESOL-q3.
  Missing matches require --allow-pbe-potential / menu 129; record each approved
  PBE approximation explicitly. Never fabricate GTH names from new functional labels.
  --libxc-available / menu 130 is an assertion, not verified build compatibility.
- Whitelist none/D3/D3(BJ) per profile after checking the actual PBESOL/REVPBE/RPBE
  reference branches in tagged CP2K sources. Do not substitute PBE damping parameters.
- Retain default PBE/DZVP-SR, 400/55 Ry grids, charge/spin/SCF and protected writers.
  Schema remains 0.1.0 with additive settings, KIND file/potential metadata and
  method_profile source/build/approximation records. Existing single-library
  data_sources keys remain; extra basis sources use basis:<filename>.
- Reinspect Multiwfn outCP2Kinp XC/q-suffix/dispersion branches; record actual
  references/differences and unchanged custom authorization status. Read user
  modc.py only as a UZH migration reference; do not run/copy it or enable an unverified
  rename-based conversion. UZH protocol support was still planned at that stage;
  the registry follow-up above implements only the audited PBE subset.
- Explicit requested version 0.2.6. No Python dependencies added, calculation,
  package release or runtime/scientific certification implied.
- Initial profile-round validation: 216 tests passed, none skipped, including 23 new method/profile test
  methods, current-q family coverage, approvals/build assertions, multi-file headers/
  hashes, wrong-library/q rejection, combined RPBE/+U/AFM/mixed bases, CLI replay,
  menu edit/clear/retained hidden flags and collision protection. Compileall, diff,
  version and local-documentation checks passed.

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
