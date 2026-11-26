# Vibrational result observations (since software 0.4.4, extended in 0.4.7)

This read-only contract covers CP2K 2026.2 Cartesian normal-mode frequency tables
for isolated molecules and periodic `XYZ` partial-Hessian calculations. It is
independent of the [input-generation contract](vibration-contract.md) and the
[GEO_OPT observation contract](geo-opt-contract.md). No method, basis, spin or
solver is inferred or required by the frequency parser. No CP2K, scheduler or
external analysis program is launched.

## Entry points

```python
from cp2kkit.vibration_results import parse_vibration, export_vibration, write_vibration

report = parse_vibration("water.out", segment=1, block=1, zero_threshold_cm_1=0.5)
data = report.to_dict()
export_vibration("water-freq.csv", report, "csv")
# write_vibration(stream, report, "json") writes to a caller-owned text stream.
```

```bash
cp2kkit vibration water.out --segment 1 --block 1 --zero-threshold-cm-1 0.5 --strict
cp2kkit vibration water.out --segment 1 --block 1 --format csv -o water-freq.csv
```

`parse_vibration(path, *, segment=None, block=None, zero_threshold_cm_1=0.0)`
returns a `VibrationReport`. Use one explicit existing UTF-8 text file; no directory
search, settings/replay, structure association or format by filename. Selectors
are positive integers (not Booleans). Segments start at 1 in file order, including
recognized program ranges without vibration tables. A program start or new version
preamble after a previous version or table separates runs; a program end closes its
range. Blocks start at 1 **within each segment**, in heading order. Omitted
selectors match all values in that dimension; only a unique matching heading is
selected, including incomplete candidates. `AmbiguousVibration.choices` contains
`(segment, block, heading_line)` tuples and `.source` describes the inspected bytes.
Selectors refer to the specific file contents, not permanent run IDs.

TUI main **7 Vibrational analysis** requests the file, threshold and, when needed,
the segment/block pair. The summary is bounded; `d` shows detailed JSON, `j` and
`c` explicitly export to a new path. Inspection and cancellation do not write.
The application layout is [5/1 Quality, 6/1 CUBE check, 6/2 density subtraction,
7 Vibration](menu-numbering-draft.md#application-workflow-layout-044); generator
**640** is still an input setting. The main menu requires a terminal and no
structure is needed for analysis.

## Native evidence and supported format

- CP2K tag [`v2026.2`, `src/motion/vibrational_analysis.F`](https://github.com/cp2k/cp2k/blob/v2026.2/src/motion/vibrational_analysis.F#L578-L719)
  writes diagnostic eigenvalue lists and converts the signed square roots of
  Hessian eigenvalues to wavenumbers before calling
  [`vib_out`](https://github.com/cp2k/cp2k/blob/v2026.2/src/motion/vibrational_analysis.F#L874-L915).
  Only `VIB| NORMAL MODES - CARTESIAN DISPLACEMENTS` introduces a candidate.
  Under it, each group has one to three printed sequential mode IDs, a
  `VIB|Frequency (cm^-1)` row, ancillary mass/force/displacement rows and a
  closing blank line. Optional IR/Raman/depolarization rows are ignored as data.
  Signed numbers are native; a negative value is CP2K's sign convention for a
  negative Hessian eigenvalue, not a validated saddle. No `i` suffix, alternate
  unit conversion, `.mol`/binary eigenvectors, mode-selective or phonon format.
- `Cartesian Low frequencies`, `Internal Low frequencies`, `Minimum Structure`,
  Hessians and replica force/SCF prints are **not** frequency records. An
  immediately preceding `Internal Low frequencies ---` list can corroborate the
  mode **count** only: its entries are not the converted frequency values.
  [`rot_ana` in `motion_utils.F`](https://github.com/cp2k/cp2k/blob/v2026.2/src/motion_utils.F#L167-L243)
  counts translations and usable rotation vectors; the writer uses its actual
  reduced dimension. The parser never computes a mode count from atoms,
  linearity, constraints or a filename and never adds/removes any modes.
- Explicit incompatible release/run-type metadata, recognized `POISSON|`/`CELL|
  Periodicity` records that are empty, malformed (including non-native
  punctuation such as `POISSON| Periodicity: XY` or trailing tokens such as
  `XY extra`), outside `NONE`/`XYZ`, or conflicting within the same segment,
  recognized `ROT| Number of rotovibrational vectors` records that are malformed
  (including non-native punctuation or trailing tokens) or outside 5 or 6, or
  any `ROT|` rotovibrational projection combined with `XYZ` periodicity are
  rejected with `ParseError` (CLI exit 4).
  Periodic `XYZ` partial-Hessian outputs (with frozen substrate atoms and
  `FULLY_PERIODIC T`, omitting `ROT|`) are accepted and preserve their printed
  1-based active atom indices in `displacement_atoms`. Only genuinely absent
  periodicity records remain `null`; when absent, the table grammar alone cannot
  prove the underlying boundary conditions or projections. Unknown version/task
  excerpts may be observed (with a warning) but cannot pass strict. The checked
  source tag is `09496e055e132aa3dba53a7751ebdf432b4ebb78`; existing local CP2K
  2026.2 molecular and periodic partial-Hessian outputs were inspected read-only.
  Public tests use independent synthetic records, not private logs or a new run.

## Output, classification and status

`to_dict()` and JSON include `schema_version: "0.1.0"`, `operation:
"vibration_observation"`, `software: "CP2K"`, `parser` name/version and `source`
(resolved `path`, exact-byte `sha256`, `size_bytes`). `software_version` preserves
the printed version string; `run_type` is the observed token. They and their
`version_source`/`run_type_source` can be null. `heading`, `program_end`,
`count_source`, `closure` and entries in `diagnostics` use `{path, line, text}`;
1-based lines retain original text without the line ending. Absent evidence is
null or an empty list as appropriate. `closure` identifies the observed group
terminator or, for a complete table, a recognized following footer when present.
`expected_mode_count_from_diagnostic` is a nullable integer, not an atom-based
count or assurance that all physical modes exist.

Version 0.4.5 adds JSON/Python `displacement_atoms` (ordered positive unique
index/element pairs from the first closed group; duplicate/nonpositive indices or
inconsistent later groups make the table incomplete) and
`reference_electronic_energy`. The additive `reference_state` object records
pre-table `DFT| Charge` and `DFT| Multiplicity` evidence for the selected segment.
Version 0.4.7 adds `periodicity` (`"NONE"`, `"XYZ"` or `null`),
`periodicity_sources` (list of line evidence) and `rotovibrational_vectors`
(`5`, `6` or `null`). Each `reference_state` field uses the
[normalized settings convention](geo-opt-contract.md):
a value is non-null only with `parsed` status; `missing`, `conflicting` and
`unsupported` retain null rather than assuming a state. This evidence does not
change the frequency report's strict status.

For a complete mode table, it observes the unique `Electronic energy (U)` row
in its adjacent native `NORMAL MODES - THERMOCHEMICAL DATA` footer, as a
`{value, unit, source}` quantity in the printed `kJ/mol`. CP2K v2026.2
[passes the restored-reference energy to that footer](https://github.com/cp2k/cp2k/blob/v2026.2/src/motion/vibrational_analysis.F#L709-L713).
Missing, malformed or duplicate rows yield null; ordinary FORCE_EVAL energies
are not substitutes. This is not a convergence or stationarity claim. Strict
frequency status and CSV columns are unchanged.

`modes` is a list in file and column order. Each record has a 1-based observed
`ordinal`, nullable `mode_id` and `mode_source` (printed ID and its line only
when columns pair, never inferred), exact `token`, `frequency` as `{value, unit,
source}` with unit `cm^-1`, and `classification`. Finite decimal and E/e/D/d
exponents are accepted, with complete-token validation; tokens preserve printed
precision and sign independently of JSON floating-point representation. Invalid,
nonfinite, overflowing or zero-underflowing tokens are diagnosed, never repaired
or filled. Duplicate/out-of-order IDs are preserved when clearly paired, but
make the block incomplete.

For finite nonnegative `zero_threshold_cm_1 = t`, `f < -t` is `negative`,
`f > t` is `positive`, otherwise `near_zero`. Default `0.0` is not a noise
criterion. `counts` includes `observed`, `raw_negative` (`f < 0` independently
of the threshold), `negative`, `near_zero` and `positive`. Printed negative zero
retains its sign in the token but counts as zero. No scaling, correction or
classification changes the frequency value.

`status` is `complete` or `incomplete` (also Boolean `complete`). Complete means
at least one usable observation, contiguous well-formed groups with displacement
closures, and either a matching adjacent diagnostic count or a subsequent
recognized CP2K footer/boundary (DBCSR statistics, timing, thermochemistry
heading or program-end banner). A following start or normal-mode heading is not
such a footer. Without an independent count, even a well-formed table and footer
cannot detect a group excised from the end of an edited log. EOF immediately
following an otherwise closed group is insufficient without corroborating count.
Each displacement row must contain three valid finite numeric components per
mode in its group. The components are checked but not exported as vectors.
Recognizable broken blocks return retained observations (possibly none) and
`diagnostics`/`warnings`; they do not silently pass. No supported heading,
invalid UTF-8, explicit unsupported scope/version or only unsupported frequency
units produce `ParseError` rather than a usable report.

`strict_passed` requires textual completeness, recognized printed version and
run type, and an observed `PROGRAM ENDED AT` in the selected segment. It does
not require all-positive modes or claim electronic convergence. `scf_summaries`
counts recognized converged/not-converged summaries in the selected segment
before the heading; they are not matched to a force replica or mode.
`electronic_converged`, `exit_status` and `stationary_point` remain null. Text
completeness, program end, clean process exit, SCF/force/numerical convergence
and stationarity are independent; `Minimum Structure` is only a native label.
No interpretation as a minimum/transition state, no IR/Raman intensities or
spectra, thermochemistry, or periodic dispersion is provided.

## Export and errors

`write_vibration(stream, report, fmt='json')` accepts `json` or `csv` and does
not own the stream. CSV is long form: one `record=frequency` row per observation;
a report with no usable observations has one `record=block` row of metadata and
heading evidence with empty mode/value fields. `frequency_cm_1` and
`zero_threshold_cm_1` encode units in column names. CSV repeats source identity,
selection and textual status; use JSON for summary counts and complete
diagnostics. CLI diagnostics go to stderr; stdout is JSON by default, CSV with
`--format csv`. With `-o` / `--output` (or `export_vibration`), one exclusive new
file is written, stdout is empty, and there is no sidecar. Existing files,
including source aliases, `.inp` and symlinks, are not replaced.

For 3D inspection of complete tables without a Molden `.mol` file,
`build_viewer_scene(report, geometry_path, *, frame=-1, fixed_atoms='off')` /
`export_viewer_scene(...)` and CLI
`cp2kkit vibration <out> --format viewer-scene --geometry <structure> [--frame N] [--fixed-atoms SPEC] [-o scene.json]`
pair the observed Cartesian normal-mode displacements with an explicit reference
structure (checking every printed 1-based displacement atom index and element).
For observed `NONE`, all reference atoms must be covered and the structure must
not declare periodic axes. For observed `XYZ`, the structure must supply a valid
cell with all three periodic axes; sparse partial-Hessian displacements remain
valid. Missing periodicity in the vibration report is not inferred, and matching
indices and elements cannot establish that two geometries came from the same run.
The exporter emits a deterministic `cp2kkit-viewer-scene-v1` JSON document without modifying
the standard `vibration_observation` JSON/CSV contract or schema `0.1.0`.
Adding `--view` (with `--geometry`, and optional `--viewer PATH`) or selecting
`v` in main menu **7** launches the optional standalone `cp2kkit-viewer` binary
in the foreground on the exported scene (or a temporary scene cleaned up on
close) and exits with code **6** if the viewer executable is unavailable.
Incomplete vibration tables, missing/mismatched geometries, and target collisions
are rejected (`KitError` / `OutputExists`).

CLI exit codes: **0** report produced (including an ordinary incomplete report),
**2** invalid requests/selectors or I/O, **3** ambiguous selection, **4** outside
the recognized format or supported scope, **5** output collision, **7** report
produced with `--strict` but `strict_passed=false`. File collisions and other
request errors take precedence over strict status. The Python API exposes the
same expected toolkit errors; strict policy is a report property. No optional
runtime dependencies are needed. Review the
[public synthetic example](../examples/vibration-results/README.md) for an
executable selected-field baseline. Existing parse/quality/CSV and generation
contracts are unchanged; this is a distinct additive operation under schema
0.1.0, not a new field in `Run` or an input manifest.
