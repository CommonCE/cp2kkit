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
7. **Minimal dependencies:** standard-library core, isolated optional plotting/Rich presentation, no ASE requirement.

## Modules and dependency direction

```text
cli.py
 |-- discovery.py -- io.py / errors.py
 |-- parser.py ----- models.py / io.py
 |-- quality.py ---- models.py (facts -> rules)
 |-- export.py ----- structure.py / io.py / models.py / quality.py (shared structure export/CSV)
 |-- structure.py -- models.py / io.py (independent geometry)
 |-- plot.py ------- export.py / quality.py / optional matplotlib
 |-- main_tui.py --- input_tui.py / structure.py / export.py (menu/load/direct operations)
 |-- structure_formats.py (strict GJF/CIF/POSCAR; lazy dispatch from structure.py)
 |-- input_tui.py -- input_editor.py / inputgen.py / structure.py (TTY navigation/fields)
 |-- input_editor.py (single numbered settings menu, drafts, review; same generator/writer)
 |-- presentation.py (scrolling text, optional Rich; no batch rendering)
 |-- inputgen.py --- structure.py / spin_settings.py / models.py / io.py (pure generation/exclusive writes)
 |-- spin_settings.py (explicit Ueff/L parsing, collinear atom seeds, stable KIND splitting)
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
- ENERGY values require a complete numeric token followed by whitespace or line end.
  Whitespace-delimited annotations are accepted; adjacent garbage/incomplete exponents
  are not prefix-parsed. Evidence retains the entire original line and byte hash.
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
Both exports also write a complete structure JSON sidecar through
export.export_structure_files(Structure, output, fmt, allow_cell_loss), returning
output/sidecar paths and structured warnings. CLI and menus call this same operation;
the menu no longer imports cli, constructs argv or extracts warnings from stderr.
Existing exclusive creation, cell-loss permission and exception rollback are retained.
structure_format/is_structure_path share the suffix/name aliases used by reader
dispatch and menu discovery. Recognition does not validate file contents.
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

The line-oriented input editor maintains drafts, performs local type/range checks,
and rechecks changes through the shared generator without repairing physical conflicts.
Applicable fields are directly selectable in one list. FIELD_IDS records inspected
Multiwfn main-menu IDs and explicit 100+ local extensions; unsupported IDs are not
repurposed. Source/frame controls are in the header, while output/project/version
are no longer numbered fields. Automatic output follows the source stem; CLI seeds
remain honored. The shared visible_fields rules filter both
rendering and selection. Numbers stay fixed, leaving gaps for hidden fields when
task/SCF/PBC changes; hidden values remain in the validated draft. Presenter handles folding
and optional Rich styling; Menu handles input/navigation; editor/application dispatch
existing business APIs. Review/previews do not write; 0/w plus explicit y/yes uses the
exclusive writer; -10/back/cancel returns from the generator. Collisions have a
new-target recovery prompt, not a permanent path setting.
Complete batch calls stay noninteractive; stdin/stdout TTY are required for menus.
Bare cp2kkit/cp2kkit STRUCTURE opens the grouped application menu. cli.menu_request
handles this syntax separately from batch parsing; command names come from actual
argparse registrations, not a second list. A single unknown word retains path
semantics. -- PATH (optionally preceded by --plain) treats PATH literally, including
leading hyphens; invalid mixed arguments still go through argparse usage errors.
Both streams must still be TTY. --plain/NO_COLOR
disable styling. EOF/q exits the session; Ctrl+C cancels an operation (exits at main).
Default input text and protected writers are unchanged. Slots 124/125 now request
explicit Ueff/L and collinear magnetic initialization; --cell/--data-dir remain
CLI-only. spin_settings validates and maps element/atom selectors without changing
charge/multiplicity or source geometry. Split KIND labels retain ELEMENT-specific
basis/potential/U. Only target 2026.2 is checked for these opt-in features. Schema
0.1.0 gains additive raw settings, generated KIND mapping and reference metadata.

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
