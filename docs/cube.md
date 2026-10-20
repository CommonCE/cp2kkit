# Density cube output, validation, and differences

This stage implements input generation, scalar-cube validation, and subtraction on
aligned grids, without running CP2K. No Bader, interpolation, registration, grid
reordering, plane averaging, DOS/bands, or job submission is provided.

## 1. Define comparable physical references first

Density difference is `delta_rho = rho_AB - sum(rho_fragment)`: the first file is
the combined system, and all remaining fields are subtracted. Electron-density
and spin-density differences are distinct quantities and must not be mixed.

- AB/fragments need matching cells, origins, sampling grids, and comparable settings.
- For bonding-induced redistribution, keep fragments in their AB geometries.
  Subtracting independently relaxed fragment densities also includes geometry-change
  contributions. After AB relaxation, prefer final fixed-geometry AB/fragment single points.
- Keep functional, pseudopotential, basis strategy, grid precision, k-points, and
  applicable occupations/smearing consistent. Equal STRIDE does not imply equal grids;
  inspect actual cubes.
- Fragment charge/spin must define physically reasonable references. Electron conservation
  requires consistent charge combinations; spin densities also require consistent
  spin conventions/quantization directions and reasonable fragment states.
- GPW localized basis functions change with atom composition. Fragment-only bases vs
  AB bases retained using ghost atoms affect comparability/basis error. Specify the
  strategy: this version neither adds ghosts automatically nor requires them for every analysis.
- The tool verifies format/numbers/grids, **not generally calculation settings or
  reference states from cube files alone**.

Positive electron-density difference indicates accumulation relative to the chosen
fragments; negative indicates depletion. Neither is directly an atomic charge change.
Whole-space and positive/negative integrals are not fragment net charge transfer.
Total density is electron-number density, not negatively signed electron charge density;
spin density is `rho_alpha - rho_beta`.

## 2. Density output with generate-input

Software 0.2.9 adds **602 / --density-difference** for preparing the whole/A/B
ENERGY GPW inputs together. Select A by whole-system indices, B is the complement,
explicitly set both fragment charges/spins, and preserve whole geometry/cell/grid
controls. It writes three inputs and an atom map, with optional combined provenance
JSON, only to entirely new targets. No calculation or subtraction is triggered.
See [the input-bundle workflow](input-generation.md#two-fragment-density-difference-inputs-029)
for flags, filenames, common NGRIDS lock and magnetic-seed mapping. Use --write-json
to retain complete source/data identity and all component settings for review.
This does not replace checking actual output CUBE grids and reference states.


```bash
export PYTHONPATH="$PWD/src"
python -m cp2kkit generate-input AB.extxyz -o AB.inp --project AB \
  --cp2k-version 2026.2 --run-type ENERGY --electron-density --cube-stride 1 1 1

# This example assumes charge +1/doublet are physically appropriate; no automatic repair.
python -m cp2kkit generate-input radical.extxyz -o radical.inp --project radical \
  --charge 1 --multiplicity 2 --spin-density --cube-stride 1 1 1

# Common GPW density-print syntax for an older version.
python -m cp2kkit generate-input AB.extxyz -o AB-2024.inp --project AB2024 \
  --cp2k-version 2024.1 --electron-density
```

`--cp2k-version` defaults to 2026.2 and accepts 2024.1/2/3, 2025.1/2, 2026.1/2.
These are checked **density-print syntax profiles** and recorded targets, not actual
runtime certification of the entire generator/parser. Older/newer profiles are not
included. Reading cube format itself does not require a version number.

`--electron-density` or `--spin-density` enables:

```text
&FORCE_EVAL
  &DFT
    ...
    &PRINT
      &E_DENSITY_CUBE ON
        STRIDE 1 1 1
        APPEND F
        ADD_LAST NUMERIC
        &EACH
          QS_SCF 0
          JUST_ENERGY 1
          GEO_OPT 0
          CELL_OPT 0
        &END EACH
      &END E_DENSITY_CUBE
    &END PRINT
  &END DFT
&END FORCE_EVAL
```

- No request means no density PRINT section; other input defaults are unaffected.
- Under UKS, E_DENSITY_CUBE prints both electron/spin density. This feature has no
  separate SPIN_DENSITY_CUBE switch. Spin requests require current UKS eligibility
  (multiplicity > 1, or explicit magnetic initialization/UKS for target 2026.2);
  invalid requests error without silently changing total charge/multiplicity.
- Under UKS, either request produces both cubes. JSON `settings` records requested
  values; `density_output` records effective behavior.
- ENERGY/ENERGY_FORCE use JUST_ENERGY 1. GEO_OPT/CELL_OPT routine frequency is 0;
  ADD_LAST NUMERIC requests the final recognized step, with routine SCF printing also 0.
  The manual notes that some iteration levels cannot recognize the last step in time,
  so abnormal termination may not produce a final cube. The last step does not prove
  convergence; inspect output. Prefer fixed-geometry ENERGY for subtraction.
- FILENAME is not overridden: retain project names, ELECTRON_DENSITY/SPIN_DENSITY
  middle names, iteration numbers/extensions. Check logs for actual names. Avoid
  `=filename` collisions; APPEND F prevents appended frames. cp2kkit's own protection
  cannot prevent a later CP2K run from overwriting old results in a reused directory.
- STRIDE needs three positive integers; effective default is 1 1 1 when enabled.
  Specifying stride alone errors. Larger stride reduces sampling and may compromise
  integrals/post-processing; 1 1 1 is not a convergence certificate either.
- GPW/GTH produces **pseudopotential valence electron density**, without all core
  electrons; it is not all-electron density. Old/new GAPW hard/soft options differ
  (TOTAL_DENSITY vs DENSITY_INCLUDE). GAPW/these branches are not enabled, nor is
  TOT_DENSITY_CUBE substituted for electron-number density.
- JSON records effective stride/frequencies/units/spin convention, target version,
  version-fixed definition URL/hash, manual source, and non-runtime-validated status.
  The standalone 2024.3 manual address was unavailable; manual_source is null and
  checked v2024.3 source is used (identical file content to v2024.2).

## 3. cube-check

```bash
python -m cp2kkit cube-check AB.cube
python -m cp2kkit cube-check AB.cube -o AB-check.json

# Generic cube metadata/filenames do not establish scalar meaning.
python -m cp2kkit cube-check generic.cube --scalar-type electron-density \
  --scalar-unit 'e/bohr^3' -o generic-check.json

# Explicit signed-count angstrom convention, not Gaussian cubegen input-unit rules.
python -m cp2kkit cube-check signed.cube --dialect signed \
  --scalar-type electron-density --scalar-unit 'e/angstrom^3'
```

Reports include comments, atom count/1-based index/atomic number/raw field/positions,
origin, dimensions, step vectors, sampling/quadrature spans, scalar count/min/max/sum,
voxel volume, total/positive/negative integrals, original-byte SHA-256, and interpretation evidence.
`atom_field` is preserved, including zero: **do not infer pseudopotential valence counts
or file corruption from it**. Invalid files exit 4 with stderr diagnostics and no
successful-check JSON. Missing paths/usage exit 2; existing JSON targets exit 5.

### Supported formats and unit policy

- UTF-8 formatted single-scalar CUBE; NATOMS >= 0; NVAL absent or 1; one value per point.
- Empty atom tables, negative scalars, E/e/D/d exponents, nonorthogonal/left-handed grids.
- All three grid counts must have the same nonzero sign; reject singular/near-collinear grids.
- Standard traversal: X outer, Y middle, Z fastest. Reject explicit other orderings;
  no automatic reordering.
- Reject negative NATOMS/orbital cubes, multiple datasets/vectors, appended frames,
  truncation/extra data, NaN/Inf, malformed atom/grid fields, numeric overflow,
  lines exceeding 1 MiB, binary/other formats.
- Bounded line iteration and compensated summation; no full text/token/grid arrays.
  Mainly retain headers and one line per input. Reject detectable changes during reading.

| Interpretation | Spatial unit | Scalar meaning/unit |
|---|---|---|
| auto, exact first line `-Quickstep-` | Positive counts: bohr; negative rejected | Checked ELECTRON/SPIN DENSITY titles and TOTAL prefixes only; e/bohr^3 |
| cp2k (explicit producer assertion) | Positive counts: bohr | Same title rules; otherwise unknown |
| gaussian | Positive counts: bohr | No scalar inference; manual assertion needed |
| signed (explicit choice) | Positive: bohr; negative: angstrom | Count sign does not establish density units |
| auto, generic positive counts | Standard bohr convention | Unknown unless asserted |
| auto, generic negative counts | null/undetermined | Raw integral; explicit spatial interpretation required for subtraction |
| cp2kkit difference output | Explicit tool-written metadata | Recorded electron/spin difference type and units |

`--length-unit` is a **unit assertion**, not coordinate conversion; conflicts with
recognized producer/convention error. Scalar assertions likewise cannot override
recognized opposing density types/units. Requests are recorded in
`interpretation.requested`; the program does not prove the user's assertion.
A CP2K identity/title does not prove GPW or inclusion of every core electron.
Unknown integrals use `raw_numerical_integral`, not electron counts.

### Integration convention

```text
I = sum(f(i,j,k)) * abs(det(v1,v2,v3))
```

Use the determinant of **grid step vectors**, not the product of their lengths,
an atomic bounding box, or step vectors mistaken for a cell.
`sample_span_vectors=(N-1)*v`; `quadrature_span_vectors=N*v` describe sampling/
quadrature regions, not proof of the simulation cell. Each point has full voxel
weight: no duplicated periodic endpoints, trapezoidal weights, or normalization.

For known electron density/differences with known spatial/scalar units, reconcile
bohr/angstrom volumes and report electrons. Spin integrals are alpha-minus-beta
excess electron counts, not automatically magnetic moments. Otherwise report raw
scalar sum times raw voxel volume. Negative integrals retain their sign.

Cube text rounds vectors/scalars; coarse stride may miss features. If original
dimensions are not divisible by stride, rounded-up output counts can change the
nominal quadrature span. Discrete integral error is not by itself SCF failure or a
physical change in electron count.

## 4. cube-diff

```bash
python -m cp2kkit cube-diff AB.cube A.cube B.cube -o delta-density.cube
python -m cp2kkit cube-diff AB.cube A.cube B.cube C.cube -o delta-many.cube
python -m cp2kkit cube-diff AB-spin.cube A-spin.cube B-spin.cube \
  --scalar-type spin-density -o delta-spin.cube

# Explicit assertions for generic cubes.
python -m cp2kkit cube-diff generic-AB.cube generic-A.cube generic-B.cube \
  --scalar-type electron-density --scalar-unit 'e/bohr^3' -o delta-generic.cube
```

At least two inputs, matching dimensions, matching known electron/spin-density types,
and comparable units are required. Reject unknown units/type or electron/spin mixing
(exit 2), not different atom tables. Already-difference files cannot be reused as
original fragment densities.

Normalize grids to bohr, then compare components:
`abs(a-b) <= grid_atol + grid_rtol*max(abs(a),abs(b))`.
Defaults: `--grid-atol 1e-6` bohr, `--grid-rtol 0`. Record each fragment's maximum
origin/vector component deviations, overall maximum, and a conservative farthest-sample
position-deviation bound. Tiny step differences can accumulate across large grids;
review them. No movement, interpolation, registration, or reordering; only explicit
unit-based numeric conversion is allowed.

Generic cubes with different units can use a shared signed convention or per-input assertions:

```bash
python -m cp2kkit cube-diff AB-bohr.cube A-angstrom.cube B-bohr.cube \
  --scalar-type electron-density --input-length-units bohr angstrom bohr \
  --input-scalar-units 'e/bohr^3' 'e/angstrom^3' 'e/bohr^3' -o delta-units.cube
```

Per-file option counts must match input count. Assertions cannot conflict with a
recognized producer or force actually different grids into apparent alignment.

Output retains AB origin/grid/spatial/scalar units and original atom-record lines;
comments identify the difference and units. `<output>.json` records expression,
ordered inputs/hashes, grid comparisons/tolerances, conversion factors, input/output
integrals, positive/negative contributions, and warnings. Hashes cover written bytes.
If the absolute difference integral exceeds `--integral-atol` (default 1e-3 electrons),
warn about charge/spin references, different settings, box tails, stride/sampling.
Do not normalize automatically or infer calculation failure from this alone.

Preflight all targets, including dangling symlinks. Stage same-directory temporary
files and publish through exclusive hard links. Collisions exit 5; failures clean up
this operation's temporary files and output inodes still owned by it, not existing
user files. Hard-link support is required; power-loss two-file atomicity is not promised.

## 5. AB/A/B workflow (no automatic construction or execution)

Assume prepared `AB.extxyz`, `A-in-AB.extxyz`, `B-in-AB.extxyz` with identical cell/PBC
and fragments in AB geometry. The example applies only when all three physical
references are neutral singlets. Otherwise set charge/multiplicity explicitly;
metals additionally need suitable diag/k-points/smearing/empty orbitals.

```bash
export PYTHONPATH="$PWD/src"
python -m cp2kkit generate-input AB.extxyz -o AB-density.inp --project AB \
  --run-type ENERGY --functional PBE --charge 0 --multiplicity 1 \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1
python -m cp2kkit generate-input A-in-AB.extxyz -o A-density.inp --project A \
  --run-type ENERGY --functional PBE --charge 0 --multiplicity 1 \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1
python -m cp2kkit generate-input B-in-AB.extxyz -o B-density.inp --project B \
  --run-type ENERGY --functional PBE --charge 0 --multiplicity 1 \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1

# Review and run all three calculations yourself in new independent directories.
# No execution/submission command is included here. Use exact final filenames from logs,
# not ambiguous globs selecting multiple iteration outputs.
AB_CUBE=/path/to/AB/ELECTRON_DENSITY.cube
A_CUBE=/path/to/A/ELECTRON_DENSITY.cube
B_CUBE=/path/to/B/ELECTRON_DENSITY.cube
python -m cp2kkit cube-check "$AB_CUBE" -o AB-cube-check.json
python -m cp2kkit cube-check "$A_CUBE" -o A-cube-check.json
python -m cp2kkit cube-check "$B_CUBE" -o B-cube-check.json
python -m cp2kkit cube-diff "$AB_CUBE" "$A_CUBE" "$B_CUBE" -o delta-density.cube
python -m cp2kkit cube-check delta-density.cube -o delta-cube-check.json
```

Actual filenames normally include project/iteration identifiers; replace the generic
example paths with the actual files.

## 6. Sources and validation levels

- Manuals: [2026.2 E_DENSITY_CUBE](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/PRINT/E_DENSITY_CUBE.html),
  [EACH](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/PRINT/E_DENSITY_CUBE/EACH.html),
  [2024.1 comparison](https://manual.cp2k.org/cp2k-2024_1-branch/CP2K_INPUT/FORCE_EVAL/DFT/PRINT/E_DENSITY_CUBE.html).
- Version-fixed [CP2K v2026.2 source](https://github.com/cp2k/cp2k/tree/v2026.2/src):
  input_cp2k_print_dft.F, input/cp_output_handling.F, qs_scf_post_gpw.F,
  pw/realspace_grid_cube.F; also inspected v2024.1/v2026.1 output/iteration behavior
  and intermediate versions' input definitions. Interface/format checks only;
  CP2K source is not copied/distributed.
- Format: [Gaussian cubegen](https://gaussian.com/cubegen/) (do not conflate output
  units with input-unit rules), [Paul Bourke signed-count convention](https://paulbourke.net/dataformats/cube/).
- Multiwfn 2026.10.1 cp2kmate.f90 E_DENSITY_CUBE/STRIDE branches:
  [provenance/citations](../third_party/multiwfn/PROVENANCE.md). Print frequencies
  were checked separately against CP2K manuals/source.

Official syntax/format checks, synthetic regression, and actual execution are distinct.
At implementation time, no CP2K executable was found/installed/run, and no usable
real cubes existed in tests or the authorized test-workspace. Thus no real-cube
regression or runtime certification was available. Synthetic expected values come
from constant-field determinant quadrature and manual subtraction, not scientific calculations.
