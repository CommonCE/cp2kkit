# cp2kkit v0.2 architecture

## Design principles

The initial analysis MVP baseline is preserved in [the roadmap](roadmap.md).
Later requirements add an [input-generation](input-generation.md) subset.
No submission system or deferred Bader/PDOS/NEB post-processing is introduced.

1. **Read-only sources:** analysis never runs external calculations or writes back to sources.
2. **Facts separate from judgments:** parsers, quality rules, display/export are independent.
3. **Evidence first:** absolute paths, SHA-256, byte sizes, lines, and original text.
4. **Conservative assessment:** null is unknown; unknown/failed/truncated cannot pass.
5. **No implicit selection/restart merging:** sort candidates by name, not time/size guesses.
6. **Non-destructive outputs:** exclusive creation; rollback newly created files on multi-file failure.
7. **Minimal dependencies:** standard-library core, isolated optional plotting, no ASE requirement.

## Modules and dependency direction

```text
cli.py
 |-- discovery.py -- io.py / errors.py
 |-- parser.py ----- models.py / io.py
 |-- quality.py ---- models.py (facts -> rules)
 |-- export.py ----- models.py / quality.py (CSV)
 |-- structure.py -- models.py / io.py (independent geometry)
 |-- plot.py ------- export.py / quality.py / optional matplotlib
 |-- main_tui.py --- input_tui.py / structure.py (application menu/load/dispatch)
 |-- structure_formats.py (strict GJF/CIF/POSCAR; lazy dispatch from structure.py)
 |-- input_tui.py -- inputgen.py / structure.py (TTY editor seeded by CLI)
 |-- inputgen.py --- structure.py / models.py / io.py (pure generation/exclusive writes)
 `-- cube.py ------- models.py / io.py / structure.py (units; streaming checks/differences)

models.py: data model/schema version
io.py: strict reads, hashes, stable JSON, exclusive outputs
errors.py: domain exceptions/machine-readable exit codes
__main__.py / pyproject.toml: module/console-script entry points
```

Conventional src layout. No plugins, database, workflow engine, or configuration
framework yet; avoid complexity exceeding MVP value.

## Result pipeline

```text
output/directory -> deterministic selection -> line format matching -> Run/Segment/Quantity/Evidence
                                                                     |-> quality_report
                                                                     |-> JSON/long-form CSV
                                                                     `-> PNG/data CSV/manifest
```

- Start markers/non-increasing optimization/MD steps split segments.
- Energies retain record indices and nullable calculation steps.
- Associate each energy with the preceding SCF summary, never the previous step's success.
- Historical SCF failures remain evidence even after recovery.
- Do not infer process exit codes or charge/spin from total energies.
- Preserve original settings strings; semantic normalization/cross-input merging is future work.

Positive quality requires normal completion, final electronic convergence, SCF
convergence associated with the final energy, an energy, supported run type, and
no errors/historical SCF failures. GEO_OPT/CELL_OPT also need geometry success evidence.
Maximum-step failures override generic geometry-end markers.

## Structure pipeline

```text
XYZ/extXYZ/restart/GJF/CIF/POSCAR -> Structure (angstrom/cell/PBC/source)
                                  |-> extXYZ (preferred, preserves cell)
                                  `-> plain XYZ (known cell loss requires permission)
Both exports also write a complete structure JSON sidecar.
```

Support explicit vectors or ABC/ALPHA_BETA_GAMMA, UNIT, SCALED, KIND/ELEMENT.
Do not guess labels, drop damaged final frames, or expand CP2K preprocessing.

## Input-generation pipeline

```text
structures -> Structure + InputSettings -> validation -> CP2K text/manifest -> new input/JSON
```

Do not inherit original electronic settings. Unknown PBC, electron/spin conflicts,
and unsupported combinations are rejected. Element presets explicitly match
basis/potential valence counts; optional local data checks verify names/hashes.
No calculation or Multiwfn/adjacent-source dependency.

The standard-library editor maintains drafts, performs local type/range checks,
then delegates chemistry/cross-field validation to the shared generator.
Previews do not write; explicit confirmation uses the exclusive writer.
Complete batch subcommands stay noninteractive; terminal generate-input without
structure/output can open the editor. Bare cp2kkit/cp2kkit STRUCTURE opens the
application menu for generation/export etc. Dynamic hiding never silently repairs
conflicting physical settings. All maintained UI/documentation/development text is English.

## Cube pipeline

```text
CUBE -> CubeReader (header/streamed scalars/byte hash) -> statistics -> check JSON
aligned density streams -> subtraction/statistics -> staged cube/JSON -> exclusive publication
```

CubeOptions states producer/spatial/scalar meaning; unknown is not electron count.
Bohr-normalized grids provide comparisons; scalar unit conversion does not move
samples. No registration/interpolation. Different atom counts are valid; preserve
AB atom fields. Step-vector determinant gives voxel volume.
io.staged_files preflights, stages in the same directory, and publishes exclusive
hard links. Rollback removes only outputs still owned by the operation.
See [cube guide](cube.md) for formats/physics/validation.

## Safety and reproducibility

- No current-time metadata in normal JSON/CSV: identical inputs/paths stay reproducible.
- Hash raw bytes; moving files changes paths, not content hashes.
- Lines/energy/SCF record indices are 1-based; segments 0-based.
- Plot manifests record PNG/CSV hashes, axes, parsed data, and quality.
- Multi-file rollback is supported; power-loss transaction atomicity is not promised.
  Existing targets must never be overwritten.
- Schema changes update docs/tests; do not add large scientific binaries/results.

## Validation strategy

Standard-library unittest covers normal/truncated/nonconverged outputs, zeros,
exponents, provenance, ambiguity/duplicate outputs, restart segmentation,
cell/PBC/unit round-trips, damage, collisions/rollback, and plot-data consistency.
Evidence is **synthetic format regression**, not actual CP2K version certification.
A real-file version matrix remains a release prerequisite.
