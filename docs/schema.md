# Exchange schema v0.1.0

All JSON top levels include `schema_version: "0.1.0"`.
NaN/Infinity are prohibited. Unknown JSON values use null, CSV uses empty fields;
actual zero values remain zero.

## Parse JSON

- `software`, `software_version`, `project`: output-derived; absent version/project is null.
- `source`: absolute path, sha256, size_bytes.
- `exit_status`: null; this version has no scheduler/process metadata.
- `segments`: file order; IDs start at 0.
- `parser_warnings`: unsupported formats, segments, or missing evidence.
- `settings`: top-level placeholder; current settings live in each segment,
  without implicit merging across segments.
- CLI parse embeds `quality`, using the report structure.

Segments contain started/completed, scf_converged, geometry_converged, run_type,
evidence, diagnostics, settings, energies, scf_iterations, final_energy, wall_time,
and unparsed_energy_records (evidence for unsupported/damaged energy lines).
final_energy is the last successfully parsed energy. If energy lines remain
unparsed, it is not a reliable final result; energy_usable=false for that segment.

Quantity:

```json
{
  "value": -12.3,
  "unit": "hartree",
  "source": {
    "path": "/absolute/path/run.out",
    "line": 10,
    "text": "original source line"
  }
}
```

Energy fields: segment, index, nullable step, quantity, and its associated scf_converged.
Total FORCE_EVAL records accept `[a.u.]` and `[hartree]` unit labels
(case-insensitive); both serialize as `hartree` without numerical conversion.
Original evidence retains the printed label. Unsupported units and malformed
records remain unparsed; energy extraction alone does not imply convergence.
This compatibility fix does not change schema 0.1.0.
SCF counts use iteration; wall_time uses s; coordinates/cells use angstrom.
Settings retain original strings, source, and nullable unit; unknown semantics are
not automatically converted to numbers.

## CSV

Long-form record types are energy and scf_iterations; missing data do not become invented rows.

Fields:
`schema_version, software, software_version, project, source_path, source_sha256,
segment, run_type, segment_status, energy_usable, scf_converged, settings_json,
record, index, step, value, unit, source_line, source_text`.

energy_usable is conservative segment quality, not certification of physical validity.
SCF-count rows have empty energy_usable/scf_converged. settings_json is ordered
JSON preserving parsed settings/evidence. Plots use index when step is absent;
index is not cumulative MD time.

## Quality JSON

Top-level status: passed or not_passed.
Segment status: passed, failed, or incomplete_or_unknown.
Electronic and geometry convergence are independent. ENERGY may have
geometry_converged=null with geometry_required=false.

Reports include reasons, energy_usable, evidence arrays, original provenance, and
limitations. Command success and calculation quality are separate.

## Structure JSON

symbols, positions, cell (3x3 row vectors or null), pbc (three Booleans or null),
coordinate_unit, cell_unit, atom_count, source, frame.
XYZ frame indices start at 0; restart frame is null.
XYZ source includes selected-frame line_start/line_end.
Export sidecars add export_format/warnings.
Unknown periodicity is not non-periodic; a cell-less XYZ has pbc=null.
Formats explicitly establishing non-periodicity, such as GJF without TV, can record false flags.

## Plot manifest

source, kind, x_label, y_label, segments_connected=false, data/path/sha256,
image/path/sha256, run, quality.
CSV contains both record types; kind chooses the plotted subset.
Plot segments independently without cross-segment connections.

## Generated input JSON: menu/workflow additions (software 0.2.9)

Schema stays 0.1.0; these are additive settings/manifest fields. Analysis/CSV
semantics, immutable basis registry v1 and semantic CLI/config names do not change.
Numeric 0.2.8 TUI extension scripts require explicit migration.

- settings.multiplicity accepts null for automatic whole-system parity selection;
  generated input and manifest settings resolve it to an integer (even electrons 1,
  odd electrons 2, after charge). Explicit values are preserved; fragment
  multiplicities remain required integers, not automatic spin predictions.
- emitted_data_files records the literal input references for basis (list),
  potential (string) and dispersion (string or null). Default UZH references use
  BASIS_MOLOPT_UZH / POTENTIAL_UZH; data_sources and KIND source evidence retain
  the independently resolved paths/hashes. Explicit file overrides are preserved.
- generator.menu_layout_version=1: function-navigation layout, not a basis registry,
  schema or CP2K runtime version. The same metadata is present in batch generation.
- Settings: density_difference Boolean (default false), fragment_a_indices compact
  1-based whole-system selection (default off), fragment_a_charge,
  fragment_b_charge, fragment_a_multiplicity, fragment_b_multiplicity (default null).
  Disabled workflows retain requests without applying them. Enabled workflows
  require explicit integer fragment states and nonempty complementary partition.
- generate_input continues returning (whole_input_text, manifest). For a workflow,
  density_difference contains enabled, expression, density_meaning, both expanded
  index lists, atom_index_base=1, atom_mapping, common_grid_policy,
  magnetic_seed_policy, ghost_basis=false, charge_conserving=true,
  runtime_validated=false and cube_grid_match_verified=false.
- components.whole/fragment_a/fragment_b are complete ordinary generator manifests,
  including settings, source/data identities, generated geometry, KINDs, input_text,
  input_sha256, electron counts, units, density output and validation boundaries.
  Their density_difference setting is false to prevent recursive workflows.
  Fragment source metadata adds derived_fragment and whole_atom_indices.
- Workflow settings retain raw global electron_density toggles; components explicitly
  enable density output. Resolved numerical defaults and per-element requests are
  inherited from the whole calculation; fragment atom-seed indices are explicitly
  mapped. Under UKS, electron/spin output channels remain coupled.
- method_profile.ngrids_selection distinguishes effective orbital basis policy from
  a whole-system workflow lock. If whole NGRIDS=5, both fragment inputs emit 5,
  including subsets whose own basis policy would omit it; otherwise all omit it.
  This does not verify actual CUBE grid equality or change ordinary defaults.
- atom_mapping records whole_index, element, fragment A/B, fragment_index and
  generated position_angstrom. CSV columns are whole_index, element, fragment,
  fragment_index, x_angstrom, y_angstrom, z_angstrom; coordinates have eight decimals.
- write_input retains (whole_path, nullable_combined_json_path, warnings). Use
  density_workflow.bundle_paths(settings, output) to enumerate all targets.
  Output must end in .inp: derive -fragment-A.inp, -fragment-B.inp and -atom-map.csv
  from its stem. The combined JSON is optional, at <whole-output>.json, and adds
  density_difference.output_paths (absolute paths for this publication).
- All requested bundle targets are exclusive, preflighted and staged. Ordinary
  error/interrupt rollback removes only our published inodes; no crash-atomic
  transaction claim. Existing JSON with JSON disabled is retained and warned.
  Ordinary single-input replacement permission does not extend to bundles.

The workflow is ENERGY GPW valence density only, charge conserving, without
ghosts/separate relaxation/centering, spin-density difference inference or native
execution. Actual reference-state fitness and produced CUBE grids remain unverified.
See [input generation](input-generation.md#two-fragment-density-difference-inputs-029).

## Generated input JSON: density extension

Schema 0.1.0 adds channels/optional fields without changing existing result semantics.
TUI and regular CLI share a manifest. Generator-main 0 validates/writes directly;
w reviews and requires confirmation; category/602 0 returns without writing.
Complete batch calls write noninteractively.
Final settings record actual selections, not UI/session histories; schema is unchanged.
Auto project/multiplicity/max_scf/added_mos resolve to actual values, not null:
multiplicity uses explicit-electron parity after charge (even 1, odd 2);
project uses the source basename without suffix; OT inner default 25, diag 128;
diag+smearing empty orbitals default to `max(30, NINT(atom_count/2))`, otherwise 0.
max_outer_scf is the OT outer limit (20 default), unused by diag.
CIF symmetry expansion, GJF charge/multiplicity, and POSCAR selective dynamics
are source_structure.source metadata, not inherited CP2K settings/constraints.
Since software 0.2.1, CELL/COORD text has eight decimals; generated_structure matches
written angstrom values, while source_structure retains original precision.
Fields/units/schema 0.1.0 are unchanged.

- target_version/settings.cp2k_version: requested syntax target, default 2026.2.
  runtime_version=null/runtime_validated=false: not an executed software version.
- settings.electron_density/spin_density/cube_stride: raw requests; unrequested stride is null.
- density_output: effective enabled/electron_density/spin_density; both densities
  are true under UKS. Includes stride (three positive integers), each
  (QS_SCF/JUST_ENERGY/GEO_OPT/CELL_OPT), add_last, append, filename_override.
  Disabled stride/each/add_last are null; no PRINT is added.
- density_meaning: GPW pseudopotential valence electron density;
  spin_convention: alpha minus beta.
- spatial_unit=bohr, scalar_unit=e/bohr^3, stride_unit=grid index increment.
- reference_version, source (version-fixed official source URL), definition_sha256,
  manual_source identify checked syntax definitions. Unavailable 2024.3 manual
  address yields null; checked tagged source is used.
- syntax_reference_checked/runtime_validated describe density-print validation,
  not certification of the entire generator.

## Generated input JSON: hybrid hardening (software 0.3.5)

Schema remains **0.1.0**; no settings or CLI/config fields are added.

- `force_output` records `explicit_print`, nullable `section`, `destination` and
  `unit`, plus `runtime_validated=false`. Explicit printing applies only to hybrid
  ENERGY_FORCE: FORCE_EVAL/PRINT/FORCES, __STD_OUT__, hartree/bohr. False means no
  explicit print override, not that forces are zero or never computed.
- Automatic hybrid basis/potential references resolvable under the selected data
  root use short filenames; explicit files retain their paths. Existing UZH aliases
  remain intact. `data_sources` and KIND/method source identities retain absolute
  checked paths/hashes. `emitted_data_files` describes literal runtime references,
  not files proven to exist on another machine. T_C_G_DATA uses t_c_g.dat while
  `truncated_gamma_source` retains the checked absolute source when available.
- `method_profile.hfx.short_range_cutoff_estimate` is null for non-screened
  hybrids. For HSE06 it contains `value_angstrom`, `selection=source_derived`,
  `derivation`, `runtime_observed=false`, nullable
  `half_minimum_cell_face_spacing_angstrom` and `exceeds_half_cell`, and `scope`.
  NONE has no cell bound (null); XYZ uses half the minimum rounded-cell face
  spacing. The equation is erfc(omega*r)/r = EPS_SCHWARZ with r in bohr. RI can
  independently extend the range; a false warning flag is not runtime or physical
  validation. No explicit exchange cutoff, omega or screening change is implied.
- Generator manifests still set runtime_validated=false. Historical returned-run
  observations are documented separately, never substituted for per-input checks.

## Generated input JSON: RI-HFX and acceleration policy (software 0.3.5)

Schema remains **0.1.0**. Old configs default to ri_hfx=false,
ri_basis_size=MEDIUM, ri_eps_filter=1e-9, ri_memory_cut=3, ri_metric=HFX and
ri_cutoff_radius=null. TRUNCATED requires an explicit finite positive radius
[angstrom]; HFX rejects an independent radius. Periodic TRUNCATED RI radii are
strictly bounded by half the emitted cell's minimum perpendicular face spacing.
Nondefault RI controls when disabled, malformed values, unsupported combinations
and nondefault direct-only hf_memory with RI fail before publication.
Settings serialize semantic fields, never new basis/function menu numbers.

- Hybrid-only method_profile.hybrid_acceleration_capabilities records target
  version, common scope, supported profile lists for direct_hfx/admm/ri_hfx,
  ri_metrics=[HFX,TRUNCATED], ri_truncated_radius_policy,
  ri_hfx_admm=false, uzh_pbe0_protocol=false, ri_basis_policy and
  runtime_validated=false. It describes generator policy, not a build probe.
- Enabled RI changes hfx.algorithm to ri_gamma and hfx.ri_hfx to true;
  hfx.admm remains false. Fraction, operator, omega/radius, screening and
  truncated-table identity retain their existing definitions. All RI modes now
  resolve/protect/hash and emit T_C_G_DATA because RI initialization checks it,
  even for non-truncated operators. The existing hfx_truncated_gamma keys under
  data_sources/emitted_data_files refer to this shared initialization table.
- hfx.max_memory_mib_per_mpi_process and hfx.eps_storage_scaling are null:
  direct HF/MEMORY is not emitted. settings.hf_memory=512 is an inactive raw
  default, not an effective RI allocation.
- Enabled-only hfx.ri records basis_role=RI_HFX, basis_generation=AUTO_BASIS,
  basis_size, basis_parent_role=ORB, parent-source-only basis_validation,
  sort_basis=EXP, metric (HFX default or TRUNCATED), effective_metric_operator,
  effective_metric_omega_bohr_inverse and effective_metric_cutoff_radius_angstrom.
  A null short-range cutoff means CP2K determines it, not zero or infinite range.
  metric_parameter_policy records inheritance or explicit independent RI truncation.
  metric_cutoff_exclusive_limit_angstrom is the periodic independent-radius bound,
  otherwise null. The metric omega is null when not applicable (TRUNCATED).
  truncated_gamma_requirement explains the shared initialization-table requirement.
- ri.thresholds maps full keyword paths to {value, unit, selection, emitted,
  derivation, keyword_reference_version, runtime_observed=false}. selection is
  explicit_input, source_derived or native_default. QS/EPS_PGF_ORB is derived
  from sqrt(QS/EPS_DEFAULT), while HF/RI/EPS_PGF_ORB is independently 1e-5 by
  native default. These expected values have inspected-source provenance through
  ri.source_hashes/source_identity, not measured runtime evidence. EPS_DEFAULT,
  EPS_FILTER, EPS_FILTER_2C, EPS_SCHWARZ and EPS_SCF are also recorded.
- ri also records eps_filter (dimensionless), memory_cut (batching factor),
  ri_flavor=RHO, two_center_matrix_functions=CHOLESKY (native default),
  keyword_reference_version, inspected local source identity/hash map and false
  build_verified/runtime_validated. Source identity is not an official-tag certificate.
- Actual ORB source files/entries/hashes remain in kinds and data_sources.
  No generated auxiliary coefficients, numerical validation, manual RI basis,
  AUX_FIT substitution or new auxiliary registry number is implied.
- Existing CDD complete hfx equality checks include the RI model across whole/A/B;
  split KINDs reuse their resolved ORB data. This is not actual CUBE/reference-state
  compatibility, convergence, timing or scientific validation.

## Generated input JSON: ADMM / AUX_FIT (software 0.3.4)

Schema stays **0.1.0**. Legacy configs default to admm=false,
admm_purification=null, aux_basis=admm-dzp and aux_basis_files=[].
These fields are additive; numeric auxiliary settings have no implicit orbital
migration. aux_basis_files must be a list of literal paths. Nondefault ADMM
controls while disabled, and all active ADMM requests outside PBE0/HSE06 DFT
target 2026.2, fail instead of disappearing.

- settings retains requested purification (null means auto) and independent
  auxiliary stable ID/file overrides. Effective OT purification is MO_DIAG;
  diagonalization uses NONE. Explicit MO_DIAG with diag fails.
- Enabled-only method_profile.admm records enabled, method=BASIS_PROJECTION,
  purification, purification_selection=explicit/solver-derived,
  exchange_scaling_model=NONE, exchange_correction_functional=DEFAULT,
  operator-consistent correction_policy, auxiliary_registry_version=1,
  keyword_reference_version, local source identity/hash scope and reference
  locators/hashes. build_verified/runtime_validated remain false.
- method_profile.hfx.admm becomes true when enabled; algorithm remains
  direct_four_center and ri_hfx remains false. Its fraction, operator,
  omega/radius/data and resource semantics are unchanged.
- Every generated KIND (including split magnetic labels) gains aux_fit:
  id, number, role=AUX_FIT, registry_version, basis (real alias), basis_file,
  basis_q, basis_source (path/bytes/hash/entry line/entry hash),
  data_validation=data_checked and physical_pairing_validated=false.
  Disabled ADMM adds no aux_fit or method_profile.admm object.
- method_profile.basis_files and emitted_data_files.basis include the
  deduplicated used ORB/AUX union. data_sources records every emitted auxiliary
  file, reusing the basis source-key scheme and protected writers.
- Density bundles compare per-element aux_fit identity and global admm model
  across whole/A/B. Actual CUBE compatibility and scientific validity remain
  unverified. Selected bytes/q and source hashes do not certify a CP2K build,
  native acceptance, physical pairing or convergence.

## Generated input JSON: direct HFX (software 0.3.2, extended in 0.3.3)

Software 0.3.2 retains this schema: standard hybrid family potentials record
`kinds.*.potential_functional=BLYP` for B3LYP or `PBE` for the other five hybrids, with
`potential_approximation=true` (not an exact-hybrid potential). The existing
`method_profile.potential_approximations` list includes affected elements even
though family selection no longer requires explicit approximation approval.
Actual exact-hybrid entries remain preferred and set the flag false.


Schema remains **0.1.0**; these are additive generator settings/profile metadata,
not changes to analysis records. Legacy configurations default new fields.

- settings.functional additionally accepts PBE0/HSE06/B3LYP (16/17/18) and,
  since 0.3.3, BHANDHLYP/M06-2X/PBEH (19/20/21). settings.pbeh_fraction
  defaults to null; PBEH requires an explicit finite dimensionless value in
  (0, 1]. Other DFT/xTB methods reject non-null values.
  settings.hf_eps_schwarz defaults to 1e-6, hf_memory to 512 [MiB per MPI process],
  hf_cutoff_radius to null (automatic, angstrom). Nondefault controls on pure
  DFT/xTB fail instead of silently being ignored. Method definitions (fraction,
  HSE06 omega, VWN3) are not arbitrary user-editable XC fragments.
- Hybrid method_profile.family is hybrid-GGA (M06-2X: hybrid-meta-GGA,
  kinetic_energy_density=true); exact_exchange_fraction is 0.25
  for PBE0/HSE06, 0.20 for B3LYP, 0.50 for BHANDHLYP, 0.54 for M06-2X,
  or the requested PBEH fraction. native_shortcut=null. BHANDHLYP/M06-2X use
  xc_backend=Libxc, libxc_required=true and ordered xc_components; other hybrids
  use CP2K-native, libxc_required=false and empty xc_components.
  **xc_parameters** records ordered native component names and keyword/value
  strings, including VWN FUNCTIONAL_TYPE=VWN3 and effective PBEH SCALE_X/SCALE_C
  (empty for the two Libxc hybrids). dispersion_reference is M062X for
  M06-2X D3, rather than its canonical profile ID. generator_scope records the
  bounded GPW/classic/Gamma/NONE-or-XYZ task policy.
- Hybrid-only method_profile.hfx records algorithm=direct_four_center, fraction,
  interaction_potential=COULOMB/TRUNCATED/SHORTRANGE; omega and omega_unit
  (0.11, bohr^-1 for HSE06; null otherwise), cutoff_radius_angstrom (periodic
  global hybrids only), cutoff_policy and minimum_cell_face_spacing_angstrom.
  Automatic radius is min(6 angstrom, minimum emitted-cell face spacing/2.01);
  settings retains null while hfx records the effective radius.
- hfx also records eps_schwarz, screen_on_initial_p=false,
  max_memory_mib_per_mpi_process, eps_storage_scaling=0.1, admm=false (true only with the explicit 0.3.4 ADMM option),
  ri_hfx=false, build_verified=false and runtime_validated=false.
- truncated_gamma_file/source and data_validation distinguish not_required,
  not_checked and source_bytes_only. If a data directory is supplied, the
  truncated table has a protected absolute path/raw-byte SHA-256/size in
  data_sources.hfx_truncated_gamma; otherwise it is an unchecked basename.
  emitted_data_files.hfx_truncated_gamma records the same effective filename.
  No table is needed for direct COULOMB/SHORTRANGE without RI. Since 0.3.5
  the emitted table reference is always t_c_g.dat; absolute checked source paths
  remain provenance only.
- hfx.keyword_reference_version=2026.2 and sources contain inspected tagged-source
  URLs/hashes. Static references, build requirements and bytes are not executable
  support, numerical-table validity, derivative accuracy or scientific validation.
  Existing data_sources/quality/protection semantics are unchanged.

## Generated input JSON: non-hybrid XC additions (software 0.3.0)

Schema remains 0.1.0; analysis/CSV and existing config/replay names are unchanged.

- settings.functional uses one of 15 canonical non-hybrid IDs (PBESOL, REVPBE,
  R2SCAN, B97M-RV, BEEFVDW, etc.). Documented aliases normalize on generation;
  previous names remain accepted. Software 0.3.3 enables six
  hybrid IDs as documented above; xTB is a separate method branch since 0.3.1.
- method_profile adds family, xc_components (ordered emitted Libxc subsections;
  empty for native/parametrized shortcuts), native_shortcut, pbe_parametrization,
  exact_exchange_fraction=0.0, kinetic_energy_density and generator_scope.
  xc_backend can be CP2K-native, Libxc or CP2K-native + Libxc (BEEFVDW).
  libxc_required applies to the native BEEFVDW shortcut too. build_verified and
  runtime_validated remain false; true user assertions do not prove availability.
- nonlocal_correlation records enabled, type (RVV10/LMKLL), kernel_file,
  parameters (B97M-rV [6.0, 0.01], otherwise null), parameter_names/unit,
  cutoff_Ry=null (omitted/native default), cutoff_policy, kernel_source,
  kernel_validation (not_checked or source_bytes_only), runtime_validated=false.
  Disabled profiles have null type/kernel/parameters. It is independent of
  settings.dispersion: none disables additional pair corrections, not required
  nonlocal correlation in B97M-rV/BEEF-vdW.
- data_sources.xc_kernel is present only for a checked supplied-data-directory
  kernel, with absolute path, raw SHA-256 and size_bytes. kernel_source repeats
  this evidence; source_bytes_only does not certify a numerical kernel.
  emitted_data_files.xc_kernel records the emitted absolute path or unchecked
  basename (null for semilocal methods). Existing basis/potential/dispersion
  fields retain their meanings. Kernel files/aliases become protected data sources.
- Canonical BP86 maps to actual GTH-BP names; kinds.potential_functional remains
  BP86 for a match, PBE for an approved approximation. No invented GTH-BP86 tag,
  implicit PBE fallback, automatic q or charge/spin change.
- CDD component manifests retain the same XC and nonlocal/kernel identity;
  inconsistent kernel hashes fail before publication. Native acceptance,
  numerical grids and scientific reference fitness remain unverified.

## Generated input JSON: method profiles (software 0.2.6)

Schema stays 0.1.0; additions do not imply changes to default physical settings.

- settings.basis_overrides: ordered canonical [element, basis ID] pairs in registry v1
  (legacy family names remain accepted on input), [] by default.
  Element names must be present and unique; the fixed valence q is not overridden.
- settings.allow_pbe_potential / libxc_available: false by default. These are explicit
  user approval/assertion flags, not detected runtime facts or an automatic fallback.
  Hidden UI values are retained; raw assertions may be true even for a native profile.
- kinds[label] retains basis/potential/valence_electrons and adds basis_file,
  potential_functional and potential_approximation (Boolean). Labels may be split
  magnetic kinds; every kind of an overridden element receives the same basis.
  File identity matters: identical basis/potential aliases in different libraries
  do not establish identical coefficients/protocols.
- method_profile records canonical functional, XC backend, libxc_required,
  libxc_user_asserted, build_verified=false, dispersion_reference (null when disabled),
  ordered basis_files, potential_file and potential_approximations (element list).
  catalog_reference_version=2026.2 and catalog_sources {url, sha256} identify fixed
  inspected header/keyword bytes, not installed files or a tested build.
  runtime_validated=false remains distinct from keyword/header checks.
- data_sources retains basis/potential/dispersion keys for the first selected basis
  library and legacy roles. Each additional basis library adds basis:<filename>,
  with its own absolute path/raw-byte sha256/size_bytes. method_profile.basis_files
  lists the actual emitted paths (absolute with data_dir, basenames otherwise).
  kinds.basis_file identifies the emitted file (registry v1: resolved absolute path
  for actual files, catalog basename for templates). Supplied hashes are separate
  from catalog reference hashes; explicit files/environment directories can be
  checked even without data_dir.
- New functionals/families, UCL coverage extensions and nonempty element overrides
  require target 2026.2. Older target profiles still support the original requests.
  Failed approval/availability checks occur before protected output creation.
- source/generated structure geometry and symbols are unchanged by these method
  requests. No inferred spin, q, missing basis substitution or source-file rewriting.
  Default generated physics is retained; software-version and additive metadata differ.

## Generated input JSON: basis registry v1 (software remains 0.2.6)

This follow-up retains schema 0.1.0 and all analysis/CSV contracts. Generator
settings now serialize semantic basis IDs instead of family labels; both forms
remain accepted on input. See [numbering and migration](basis-selection.md).
Software 0.2.6 alone does not distinguish legacy positional menus from registry v1.

- settings.basis: canonical stable string ID (default molopt-sr-dzvp).
  settings.basis_overrides values use the same ID domain. No persisted menu positions.
- settings.basis_files/potential_files: explicit source-path arrays, [] by default;
  custom_basis_file/custom_basis_name/custom_potential_file/custom_potential_name:
  nullable literal strings. Inactive custom settings are retained, not applied to
  other families. These fields are data selectors, not new computational methods.
- basis_selection: {id, number, registry_version: 1}. The number is informational,
  not a substitute for settings.basis. Loading a registry-v1 sidecar with numeric
  settings is rejected rather than migrated as legacy software 0.2.6.
- kinds[label] additionally records basis_id/basis_number, basis_role=ORB,
  basis_kind_type=pseudopotential, basis_protocol, nullable basis_q, potential_q
  and potential_q_source (occupations or catalog), potential_file, basis_source,
  potential_source and data_validation. All split KINDs inherit the element's
  selected basis/potential/q without changing spin/U or atom order.
- Actual basis_source/potential_source objects contain resolved path, requested_path
  and requested_paths (including symlink spellings), raw sha256/size_bytes,
  entry_line (1-based) and entry_sha256 (header-q/payload-token fingerprint).
  Sources are null for catalog-only templates. data_version is identified only
  through an exact pinned whole-file hash; otherwise null. reference_url is
  present only for a recognized reference. Unrecognized unused headers are
  preserved as unrecognized_headers [{line,text}], not repaired or certified.
- protocol_pairing is reference_pair (recognized UZH reference bytes), catalog_pair
  (both files unresolved), unverified_pair (UZH bytes not both recognized),
  classic_family (intended classic profile), or custom_user_asserted. These are
  not execution/convergence judgments; q agreement does not prove physical fitness.
- basis_validation: status=data_checked or unverified_template, explicit selected-
  entry scope, runtime_validated=false and runnable_verified=false. data_checked
  requires both actual selected files and known matching q; it is not a check of
  every block in those files, physical suitability or native CP2K acceptance.
- Additional source keys still use basis:<basename>; basename collisions use
  basis:<resolved-path> to preserve both identities. Only actually used basis
  references are emitted, deduplicated by real path. Different potential files
  cannot silently be merged into the one POTENTIAL_FILE_NAME keyword.

Metadata and full summaries stay in JSON/review rather than extra input comments.
The bundled catalog remains header metadata only, not installed data or parameters.
No runtime validation is inferred from a filename, version, hash or successful export.

## Generated input output policy (0.2.7 follow-up)

JSON is opt-in, not a default file: settings.write_json=false by default;
--write-json or menu 501 enables it. generate_input still returns (text, manifest)
in memory. write_input returns (input_path, sidecar_path_or_null, warnings).
Existing regular .inp may be replaced; optional JSON remains exclusive and its
failure/collision must leave an existing input unchanged. Existing JSON is never
removed or updated when the option is off (stale-sidecar warning is returned).
Other workflows and schema/analysis/CSV contracts are unchanged. Filenames for
basis, potential and D3 libraries are serialized unquoted as whole-line values;
input_sha256 and input_text reflect that deliberate formatting change, with
scientific settings unchanged. Source/data/symlink protections still apply.

## Generated input JSON: all-electron and OT additions (0.2.7)

Analysis/CSV and schema 0.1.0 are unchanged. Settings add `ot_algorithm` (null for
auto, otherwise IRAC/STRICT) and `gapw_profile` (auto/native, effective for AE).
Old configs without these fields use defaults. Registry v1 is extended additively
with 50-59; no previously allocated number/ID changes meaning.

- `explicit_electron_count`: charge-adjusted electrons in the selected model.
- `electron_count_model`: pseudopotential_valence or all_electron.
- `valence_electron_count`: unchanged integer for PP; null for AE, not a misleading
  full-electron count under a valence label.
- AE KINDs: nuclear_charge=Z, nuclear_charge_source=nuclear_occupations or
  atomic_number_catalog, explicit_electrons=Z; basis_q, potential_q,
  potential_q_source, potential_functional and valence_electrons are null.
  protocol_pairing=all_electron_nuclear_charge; potential_approximation=false.
- `method_profile.qs_method`: GPW/GAPW; `ngrids`: emitted count or null when omitted;
  `ot_algorithm`: effective IRAC/STRICT for OT, null for diag. Hidden raw settings
  are retained but must not be confused with effective settings.
- `method_profile.gapw`: null for PP, or versioned profile/qs/kind/ot_algorithm/
  ngrids/automatic_settings/preserved/convergence_verified=false. Derived entries
  record setting/value/reason; explicit OT overrides carry source=user. Numerical
  profile v4 has empty qs/kind maps: cp2k_default_controls lists omitted EPSFIT,
  EPSRHO0, EPSSVD, LEBEDEV_GRID, RADIAL_GRID and NGRIDS for AE without guessing
  runtime values. method_profile.ngrids is 5 only for an effective classic non-SR
  TZVP/TZV2P/TZV2PX-MOLOPT-GTH basis; null otherwise. Both legacy AE profiles
  default to explicit IRAC; PP defaults to explicit STRICT. Manual overrides win.
- AE catalog_reference_version is null: catalog_sources identifies exact local
  paths/hashes/REVISION and does not infer upstream equivalence. Actual source
  records may identify recognized local bytes with reference_path/source_revision;
  official reference_url remains reserved for recognized tagged bytes.
- AE data_checked requires both actual selected entries, valid no-q orbital
  payloads and ALL nuclear occupations equal to Z. It is not proof of orbital
  fitness, native execution or convergence. All runtime/runnable flags stay false.

## Generated input JSON: optional electronic extensions

Schema remains 0.1.0; the following fields are additive. Older inputs without new
requests retain the same generated input text. Existing input-settings metadata now
also records `dft_plus_u` (empty array by default) and `magnetism` (null by default).

- `settings.dft_plus_u`: array of [element, L, Ueff_eV] entries. One present element
  per entry, L=0/1/2/3, finite nonnegative Ueff=U-J in eV.
- `settings.magnetism`: null means automatic UKS from multiplicity; [] explicitly
  requests UKS without local seeds; [selector, moment] entries request UKS plus
  initial moments. Selectors are element symbols or @1-based atom indices.
  Element defaults are overridden by atom selectors. Zero and negative moments
  are actual values. Moments are initial alpha-minus-beta electron numbers.
- When +U or explicit magnetism is requested, `electronic_extensions` records
  effective UKS, atom_kinds (ordered labels matching generated COORD), atom_index_base=1,
  initial-spin convention, U units, projector method, keyword-reference version/URLs,
  and runtime_validated=false. Current reference/target restriction is CP2K 2026.2.
- `kinds` is keyed by generated KIND label (not necessarily an element symbol).
  For extensions it adds actual element, nullable initial_magnetization and optional
  dft_plus_u {L, U_minus_J, unit, method}. Split same-element kinds retain their basis/
  potential and all receive the element's requested Hubbard correction.
- Source/generated structure symbols remain chemical elements; generated COORD
  KIND labels are recorded separately in electronic_extensions.atom_kinds.
  Positions/cell/order remain governed by the existing eight-decimal geometry contract.
  Parsed restart KIND labels/moments are not implicitly inherited.
- Total charge/multiplicity are never derived from initial local moments. An explicit
  UKS singlet is distinct from default RKS; density_output.spin_density and the
  generated two-spin ADDED_MOS follow effective UKS rather than multiplicity alone.

## Generated input JSON: fixed atoms (software 0.2.8)

Schema stays 0.1.0; existing analysis/CSV and optional JSON write policies are
unchanged. Missing settings in old configs default to off.

- settings.fixed_atoms: compact text, default 'off'. Explicit positive 1-based
  indices/ranges are sorted deterministically; off/none/0 normalize to off.
  Hidden selections remain requests, not evidence of emitted constraints.
- constraints.enabled: true only when GEO_OPT/CELL_OPT has a nonempty, validated
  selection. DFT active constraints require target 2026.2; the separate xTB
  branch uses audited target-specific references on checked 2024.2-2026.2 releases.
- constraints.fixed_atoms: ordered expanded active indices, [] when disabled.
  Bounds are checked against the loaded structure before expansion. Inactive
  selections are not expanded and are checked when optimization becomes active.
- constraints.index_base=1; index_reference identifies generated_structure atom
  order after source symmetry expansion/frame selection. Atom order, geometry,
  KIND splitting, charge and spin are unchanged.
- components_to_fix='XYZ', coordinate_space='fractional' when active, otherwise
  null. CELL_OPT therefore does not pin absolute Cartesian positions.
- keyword_reference records the inspected supplied local CP2K revision,
  definition file/hash and target; null when disabled. It does not assert
  installed data/binary identity or native acceptance.
- runtime_validated=false. The generator does not inherit source constraints,
  remap atom identities, execute CP2K or certify convergence.

## Generated input JSON: restart and motion output (software 0.2.7)

Schema remains 0.1.0. These additive fields are available in the in-memory
manifest/review and optional JSON; the default writer still creates input only.

- settings.trust_radius: positive finite number, default 0.2; units.trust_radius
  is angstrom. settings.trajectory_format is PDB/XYZ/EXTXYZ, default XYZ.
  Hidden values remain raw requests, not evidence of active output.
- restart_template: filename follows PROJECT with -RESTART.wfn for Gamma or
  -RESTART.kp for non-Gamma. scf_guess=RESTART is a metadata-only suggestion;
  enabled=false, emitted=false, filename_commented=false, guess_commented=false.
  Neither hint is emitted or enabled. CP2K's guess default applies until edited.
  naming_basis describes default restart naming, runtime_verified=false.
  This is not evidence that the file exists or is compatible with the calculation.
- motion_output.enabled: true for GEO_OPT/CELL_OPT, false otherwise.
  trajectory_format and restart_backup_copies=0 describe emitted MOTION/PRINT
  controls; both are null outside optimization.
  trust_radius_angstrom is the effective BFGS/LBFGS radius, null for CG and
  non-optimization tasks, even when settings.trust_radius retains a value.
- wavefunction_output records restart_enabled=true, restart_backup_copies=0,
  section=FORCE_EVAL/DFT/SCF/PRINT/RESTART, runtime_validated=false. This describes
  output controls, not proof of an existing or successfully written wavefunction.
- No trajectory cadence or filename override is imposed. SCF and MOTION each
  explicitly set backup count 0, without disabling restart writing.
  Static keyword/naming checks are not native acceptance or convergence proof.

## Generated input JSON: GFN-xTB branch (software 0.3.1)

Schema remains 0.1.0; analysis contracts are unchanged. Consumers of generator
JSON must branch on settings.method (absent in old configs means DFT) /
method_profile.family before interpreting DFT-specific fields.

- settings adds method (DFT/GFN1-xTB/GFN0-xTB/GFN2-xTB), tblite_available Boolean
  and xtb_accuracy (positive dimensionless, default 1.0). Raw inactive DFT
  defaults are retained; they are not an effective xTB basis/XC/grid.
- method_profile for xTB records family=GFN-xTB, model, upstream_number 30/31/32,
  qs_method=XTB, backend, backend_version=null, tblite_required/user_asserted,
  self_consistent, solver, scc_mixer, convergence_control, intrinsic_dispersion,
  accuracy/unit/accuracy_role, effective_max_scf, parameter_source and data_validation.
  version_compatibility records legacy_gfn1, legacy/new parameter filename,
  modern_tblite, extxyz and target-specific tagged-source URLs/SHA-256 hashes.
  Additive gfn2_ot_enabled is a generator-policy Boolean: true only for target
  2026.2, not a detected runtime capability. Legacy GFN2 OT requests are rejected
  before publication; explicit diag remains required on 2025.2/2026.1. Build/runtime flags
  remain false. count_reference records native/tblite source hashes and the
  reference tblite version; expected_data_sha256 records pinned native files.
  Source reference versions do not establish an installed version.
- explicit_electron_count subtracts charge from model reference occupations;
  electron_count_model=xtb_reference_occupation and electron_reference_counts
  records each element. valence_electron_count=null: these are not GTH valences.
- basis_selection id/number are null (registry_version stays 1),
  basis_validation.status=not_applicable; kinds is empty. poisson_solver=null.
  GPW/GAPW XC, nonlocal, kernel and density objects are not reused for xTB.
- effective_eps_scf=null and effective_max_scf=null for non-SCC GFN0.
  GFN1/2 record emitted CP2K SCF thresholds/limits. GFN2 OT uses CP2K EPS_SCF
  for orbital convergence. Only 2026.2 diagonalization/native SCC uses ACCURACY
  for SCC convergence (not equivalent to EPS_SCF). On 2026.2 OT, accuracy_role
  is numerical setup only; legacy GFN2 targets have accuracy/unit/role=null and
  emit no ACCURACY/SCC_MIXER keyword. Default raw xtb_accuracy stays 1.0.
- data_sources records checked native model/D3 absolute paths/byte hashes;
  emitted_data_files.xtb records actual runtime filenames. data_validation is
  source_bytes_checked or unverified_template for native models, backend_unchecked
  for tblite built-ins. Source-byte checking does not certify a parameter model.
- Source/generated structures, angstrom geometry, coordinate translation,
  constraints, wavefunction_output, motion_output, input_text/input_sha256,
  references and warnings retain their meanings. xTB constraints.keyword_reference
  uses the selected target's tagged definition/hash. All writing still uses the
  shared non-destructive publication policy.
- Initial model/task/spin/PBC restrictions are in the
  [xTB guide](input-generation.md#gfn-xtb-methods-031). No calculation is executed.

## Cube check JSON

- schema_version/source: absolute path, raw-byte sha256, size_bytes.
- comments: two lines; atom_count/atoms: 1-based index, atomic_number, atom_field,
  position. Raw fields, including zero, do not identify potentials/valence counts.
- origin, shape (positive dimensions), signed_counts (original signs), vectors
  (three grid step rows). Header values remain in file units, interpreted by
  length_unit, not implicitly standardized to angstrom.
- sample_span_vectors=(N-1)*v, quadrature_span_vectors=N*v; not a cell derived from
  atom bounding boxes.
- voxel_volume: value=abs(det(vectors)), unit=spatial unit cubed.
- dialect, nullable length_unit, scalar_type, scalar_unit, interpretation.
  unknown is an explicit enum, not zero or proof of density. interpretation records
  requests, pre-assertion inference, and spatial/scalar evidence.
- expected_value_count, traversal (X outer/Y middle/Z inner), statistics, warnings,
  supported_format.
- validation.format_valid=true only after complete reading/checks.
  calculation_settings_verified/real_cp2k_runtime_validated remain false.

Statistics include value_count/minimum/maximum/sum/sum_unit/integral/positive_integral/
negative_integral. Integrals have value/unit/quantity/convention; negative contributions
retain their sign. Known electron density with compatible units uses
quantity=electron_number/unit=electron; spin uses spin_excess_electrons without automatic
magnetic-moment conversion. Unknown scalars/spatial units use raw_numerical_integral,
with units of raw scalar times spatial volume. All use scalar sum times absolute
step determinant, without endpoint weighting, normalization, or data correction.
Damaged/unsupported files exit through existing CLI errors, not format_valid=true JSON.

## Cube difference JSON sidecar

- operation=density_difference; expression subtracts all remaining fields from rho[0];
  expression_sources are ordered paths.
- inputs: ordered full check reports with independent hashes/atoms/grids/units/integrals.
- output: path/sha256/size_bytes, electron-density-difference or spin-density-difference,
  scalar_unit/length_unit/shape/origin/vectors, atoms_from=rho[0],
  atom_fields_preserved=true.
- canonical_grid: normalized bohr comparison grid; output retains AB's numeric grid/units.
- tolerances: grid_atol_bohr, grid_rtol, nonzero_integral_warning_electrons.
- grid_deviations: per-fragment maximum origin/vector components and conservative
  farthest-sample bounds; max_grid_component_deviation_bohr spans all origin/step components.
- density_conversion_factors_to_output_unit: conversion to AB scalar units.
- statistics: output range/sum/integrals and positive/negative contributions.
- generator/warnings/validation: version, physical/numerical limits, and unverified
  calculation-settings/runtime status.

Cube comments encode type/spatial/scalar units/traversal for independent rereading,
not certification of the original calculation. See [the cube guide](cube.md).
