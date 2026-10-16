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

## Generated input JSON: density extension

Schema 0.1.0 adds channels/optional fields without changing existing result semantics.
TUI and regular CLI share a manifest; drafts are written only after confirmation.
Final settings record actual selections, not UI/session histories; schema is unchanged.
Auto project/max_scf/added_mos resolve to actual values, not null:
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

## Generated input JSON: method profiles (software 0.2.6)

Schema stays 0.1.0; additions do not imply changes to default physical settings.

- settings.basis_overrides: ordered canonical [element, family] pairs, [] by default.
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
  kinds.basis_file identifies the catalog library basename. Supplied file hashes
  are separate from catalog reference hashes; no data_dir means no local verification.
- New functionals/families, UCL coverage extensions and nonempty element overrides
  require target 2026.2. Older target profiles still support the original requests.
  Failed approval/availability checks occur before protected output creation.
- source/generated structure geometry and symbols are unchanged by these method
  requests. No inferred spin, q, missing basis substitution or source-file rewriting.
  Default generated physics is retained; software-version and additive metadata differ.

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
