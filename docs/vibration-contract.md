# Vibrational generation contract (software 0.4.7)

This is an input-generation contract for independent API/CLI consumers, not a
frequency-result or execution contract. It covers both the isolated molecular
subset (0.4.3–0.4.6) and the bounded periodic surface partial-Hessian subset
added in **0.4.7**. See the separate [result contract](vibration-results-contract.md)
for read-only frequency observations. Generation reuses schema **0.1.0** and the
[shared consumer rules](contracts.md). The authoritative supported/rejected
scientific combinations, presets and numerical limits are in the
[input-generation task policy](input-generation.md#molecular-vibrational-inputs-043);
[manifest fields](schema.md#generated-vibrational-inputs-software-043) and
[closeout boundaries](closeout-0.4.3.md) are linked rather than duplicated here.

## Public calls

```python
import json
from pathlib import Path
from cp2kkit.structure import read_structure
from cp2kkit.inputgen import InputSettings, generate_input, write_input

source = Path('examples/vibration-contract/water.xyz')
request = json.loads(Path('examples/vibration-contract/settings.json').read_text())
settings = InputSettings.from_config(request)
structure = read_structure(source, frame=0)
text, manifest = generate_input(structure, settings)  # No output publication.
# Optional publication to an existing writable parent, preferably a fresh directory:
# output, sidecar, warnings = write_input(structure, settings, 'test-workspace/new-run/water.inp')
```

Equivalent noninteractive CLI, with the example's project and scientific settings:

```bash
mkdir -p test-workspace
run_dir=$(mktemp -d test-workspace/vibration-contract.XXXXXX)
cp2kkit generate-input examples/vibration-contract/water.xyz \
  --frame 0 -o "$run_dir/water.inp" --project vibration-contract \
  --run-type VIBRATIONAL_ANALYSIS --cp2k-version 2026.2 \
  --method DFT --functional PBE --basis molopt-sr-dzvp \
  --periodic NONE --charge 0 --scf ot --ot-algorithm STRICT --write-json
```

The recipe chooses a fresh directory in the ignored manual-test workspace;
other callers may use any suitable writable output parent. Source-tree invocation is
`PYTHONPATH=src python -m cp2kkit ...`. The CLI does not have a configuration-file
or manifest-replay flag; configuration loading/replay is a Python API operation.
Do not invoke a TUI or parse human progress messages for automated integration.
Generation writes no JSON to stdout: success/warnings are human text on stderr.

## Request and resolution

- `read_structure(path, frame=...)` returns a Structure with angstrom coordinates
  and cell, source path/SHA-256/size/line provenance, and zero-based selected XYZ
  frame. Default -1 selects the last XYZ frame; selection does not establish
  optimization or association with a parsed output. Non-XYZ readers have their
  own frame restrictions. Plain XYZ has unknown PBC/cell, not isolated PBC.
- `InputSettings(...)` or `InputSettings.from_config(mapping)` use existing
  settings, not a separate request format. Set `run_type=VIBRATIONAL_ANALYSIS` and
  resolve periodicity explicitly (`NONE` for isolated molecules; `XYZ` with
  explicit partial `--fixed-atoms` for periodic surface partial Hessians). Source
  geometry does not supply charge, spin, functional, basis or other calculation
  settings.
- Periodic surface partial-Hessian requests (`periodic="XYZ"`) require explicit
  whole-atom `fixed_atoms` constraining at least one atom and leaving at least one
  unfixed (active) atom. Full-system periodic Gamma vibrations (`fixed_atoms="off"`
  with `XYZ`) and all-fixed selections are rejected. Skew periodic cells are
  accepted; `POISSON_SOLVER PERIODIC`, `FULLY_PERIODIC T` and a minimal
  `&MOTION/&CONSTRAINT/&FIXED_ATOMS` block (`COMPONENTS_TO_FIX XYZ`) are emitted.
  Both `scf="ot"` (`STRICT`, no smearing) and `scf="diag"` (with optional
  Fermi-Dirac `smearing` and `added_mos`) are accepted at Gamma `(1, 1, 1)`.
  Isolated molecular requests (`periodic="NONE"`) retain `MT`, `FULLY_PERIODIC F`,
  `OT/STRICT` without smearing, at least two atoms, and inactive `fixed_atoms`.
- Absent/null `vibration_displacement_bohr` means auto 0.01 bohr; explicit values
  must be finite positive numbers, not Booleans, keep finite `2*DX` and finite
  displaced `+/-DX` bohr coordinates (rejecting finite-difference overflow as
  well as displacements that round away at coordinate precision), and pass any
  applicable box checks. Absent/null eps_scf selects this task's 1e-8 preset;
  explicit values must be finite positive and <=1e-8. There is no accuracy-safe
  DX guarantee.
- Existing charge defaults to integer 0. Auto/null multiplicity resolves to 1
  for even and 2 for odd valence-electron counts; explicit values must pass the
  same parity and electron-count checks. Multiplicity >1 or explicit `magnetism`
  (including `()` for seedless UKS) enables UKS. Atomic seeds are initial guesses
  only, not moment constraints or a reason to change charge or multiplicity.
  Do not use electron parity as a ground-state spin prediction. UKS vibration
  manifests warn that displaced-geometry SCF solutions are not verified to remain
  on the same spin/electronic state, including when no seeds were requested.
- `dispersion` accepts `none` (unchanged default), `d3` and `d3bj`. When a data
  directory is selected, `dftd3.dat` must be readable and its byte identity is
  recorded in `data_sources.dispersion`; otherwise CP2K must resolve the basename
  at runtime and the manifest warns that it was unchecked.
- `data_dir`, explicit library paths and the CP2K_DATA_DIR fallback affect data
  resolution. For the catalog-only public expectation, unset CP2K_DATA_DIR and
  do not supply data files. Real checked libraries change validation/provenance;
  data_checked is not runnable_verified or numerical convergence.
- Use supported setting keys/types. from_config accepts a settings mapping or
  a generator sidecar containing settings; it is not a complete JSON Schema
  validator. Arbitrary malformed mappings/unknown setting keys may raise Python
  type errors rather than KitError. Validate untrusted application requests in
  the consumer adapter; do not promise uniform CLI errors from arbitrary Python
  objects or tolerance of unknown request keys.

## Return values and selected manifest semantics

`generate_input` returns `(text: str, manifest: dict)`, with no file publication.
`write_input` returns `(output: pathlib.Path, sidecar: pathlib.Path | None,
warnings: list[str])`. It returns paths/warnings, not the manifest object;
read the opt-in sidecar or call generate_input for metadata.

| Manifest field | Type and meaning |
|---|---|
| schema_version; generator.name/version | Strings; exchange and toolkit identities, not CP2K runtime identity |
| target_software/target_version | Strings CP2K/2026.2 for this task; requested target, not detected installed version |
| runtime_version; runtime_validated | Null and false; no runtime probe performed |
| settings | Normalized settings object; not a lossless copy of the original request. DX/eps_scf auto nulls remain null, but auto multiplicity is stored as the resolved integer |
| input_text; input_sha256 | Generated string and SHA-256 of its UTF-8 bytes; recompute if bytes change |
| source_structure; generated_structure | Independent Structure objects in JSON form; original versus emitted/rounded/possibly auto-centered geometry |
| coordinates_translated | Boolean describing generator translation, not optimization |
| effective_eps_scf; poisson_solver | Finite number and `MT` (isolated molecular) or `PERIODIC` (periodic partial Hessian): effective configuration, not observations |
| vibrational_analysis | Object for this task; may be null/absent for older or other task manifests. `scope` is `"molecular"` or `"periodic_partial_hessian"`; `active_atoms`, `active_atom_count` and `fixed_atom_count` record active/fixed atom scopes |
| displacement_bohr, eps_scf, qs_eps_default within that object | Finite numbers with origin labels; not observed force/frequency errors |
| nproc_rep | Integer 1, processors per replica, not total cores or replica count |
| fully_periodic, intensities, thermochemistry | Boolean configuration flags (`fully_periodic` is `false` with `fully_periodic_origin: "native_default_explicit"` for molecular, `true` with `fully_periodic_origin: "task_preset"` for periodic partial Hessian), not unknown results |
| program_run_info; program_run_info_origin | True and task_preset: native diagnostics enabled to stdout |
| stationary_point_verified; runtime_validated within that object | False: generator did not verify either; not a failed-calculation observation |
| mt_box | Object (`density_extent_verified: false`) for isolated molecular `MT`, or `null` for periodic partial Hessian |
| sources within that object | Array of inspected reference URL/SHA-256 objects, not executable/build fingerprints |
| warnings | Array of strings; wording/order are not stable identifiers |

Origin labels distinguish user_explicit, task_preset and native_default_explicit.
Preserve actual zero charge, false flags and null runtime identity independently.
For full field names/units see the schema section. Absence of the newer task
object means unavailable metadata, not a successful/failed vibrational result.
`force_output` describes FORCE_EVAL/PRINT/FORCES specifically; its explicit_print
can be false while vibrational PROGRAM_RUN_INFO force diagnostics are enabled.
Do not mistake it for an overall "no forces printed" flag. No frequencies,
Hessian observations, stationary-point judgment or scheduler outcome are exported.

## Pair dispersion force path

Static inspection of CP2K tag **v2026.2** traced `+DX` and `-DX` in
[`motion/vibrational_analysis.F`](https://github.com/cp2k/cp2k/blob/v2026.2/src/motion/vibrational_analysis.F)
through the force-enabled replica call (`replica_methods.F`, `f77_interface.F`)
and Quickstep dispatch (`force_env_methods.F`, `qs_force.F`). The force call
passes `calc_forces=.TRUE.` to `qs_energies`; `qs_energy_init.F` invokes
`calculate_dispersion_pairpot` with that flag. Both DFTD3 and DFTD3(BJ) in
`qs_dispersion_pairpot.F` dispatch to `calculate_dispersion_d3_pairpot`;
`qs_dispersion_d3.F` accumulates in the dispersion force component, which
`replicate_qs_force` in `qs_force_types.F` includes in the total. The replica
forces are differenced to form the Hessian. These links are hash-recorded in
`vibrational_analysis.sources` for D3/D3(BJ) requests. The shared method profile
already records the tagged D3 parameter lookup source (PBE in both branches).

This is source-path evidence, not native execution, measured force/frequency
agreement, SCF spin-state continuity or scientific validation. Closed-shell
isolated `dispersion='none'` inputs and input hashes are unchanged since 0.4.5;
the software identity in new sidecars advances to 0.4.7. No new request keys or
exchange schema changes are needed.

## Publication, failures and replay

- Output parent directories must already exist and be writable. With write_json
  true, the sidecar is exactly `str(output) + '.json'`; false returns None and
  writes only input. A pre-existing sidecar is left unchanged when JSON is off,
  with a stale-sidecar warning in the writer result/CLI stderr.
- A regular existing .inp may be replaced. Existing non-.inp/non-regular targets,
  symlinks and opt-in sidecar collisions are rejected; source/data paths and
  hardlinks are protected. Invalid generation does not publish input or metadata.
  See the shared writer rules for staging/rollback; no power-loss-atomic
  multi-file transaction is promised. Use new output directories in automation.
- Expected request/task errors use KitError (CLI 2), malformed structure input
  uses ParseError (4), and output collisions use OutputExists (5). File I/O
  failures can raise OSError in Python and map to CLI 2. Source/data replacement
  protection uses KitError/2, not the collision code. argparse usage errors exit
  2; success is 0, not proof CP2K ran. Do not branch on exact exception prose.
- Replay with `InputSettings.from_config(manifest)` and an explicitly supplied
  structure. Metadata/input_text are not an executable request and source paths
  are not automatically opened by from_config. Keep source/data identities and
  environment fixed when comparing regenerated bytes. Additional output metadata
  is ignored by this loader; unknown keys inside settings are not guaranteed
  accepted. from_config does not negotiate schema_version; consumers must check
  supported exchange/producer versions before replay. This is not a general
  future-version request migration engine.
- Current auto DX/eps_scf origins survive sidecar replay. Do not replace nulls
  with effective values unless intentionally making them user-explicit choices.
  Older unreleased vibration sidecars regenerate with the MT/diagnostic presets,
  not byte-identical initial WAVELET input. Other task text defaults are retained.

The [public synthetic baseline](../examples/vibration-contract/README.md) and
`tests/test_vibration_contract.py` check selected types, API/CLI publication,
identity/replay and failures without running CP2K. Broader scientific/scope gates
remain in `tests/test_vibration.py`. Neither suite establishes compatibility of a
specific chemops adapter; that adapter must test its own mapping independently.
