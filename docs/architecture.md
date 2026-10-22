# cp2kkit v0.3.4 architecture

## Design principles

The initial analysis MVP baseline is preserved in [the roadmap](roadmap.md).
Later requirements add an [input-generation](input-generation.md) subset.
The [numbering/allocation guide](menu-numbering-draft.md) records implemented
menu layout v1 (introduced in 0.2.9, retained in 0.3.4) plus separately labeled provisional future features.
The current registry contains only implemented entries; no placeholder categories.
No submission system or deferred Bader/PDOS/NEB post-processing is introduced.

1. **Read-only sources:** analysis never runs external calculations or writes back to sources.
2. **Facts separate from judgments:** parsers, quality rules, display/export are independent.
3. **Evidence first:** absolute paths, SHA-256, byte sizes, lines, and original text.
4. **Conservative assessment:** null is unknown; unknown/failed/truncated cannot pass.
5. **No implicit selection/restart merging:** sort candidates by name, not time/size guesses.
6. **Narrow replacement permission:** analysis/JSON/exports remain exclusive;
   ordinary single-input generation alone may atomically replace regular .inp,
   never sources/data/symlinks. Density bundles require all requested targets to be new.
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
 |-- input_editor.py -- menu_registry.py (category/direct routing, aliases, drafts; same generator/writer)
 |-- presentation.py (scrolling text, optional Rich; no batch rendering)
 |-- inputgen.py --- structure.py / spin_settings.py / method_profiles.py / models.py / io.py
 |-- xtb.py -- xtb_versions.py (GFN model/backend/count/data policy; tagged-version syntax and sources)
 |-- functional_registry.py (shared XC definitions/aliases, exact-exchange/nonlocal/build/dispersion/scope policy)
 |-- hybrid.py (direct-HFX validation/operator/radius/data provenance; no executor)
 |-- admm.py -- auxiliary_basis.py (bounded projection/purification/correction and independent AUX_FIT registry)
 |-- auxiliary_basis.py -- basis_registry.py / basis_resolution.py / cp2k_data.py (checked auxiliary q/payload, final ORB/AUX file union)
 |-- method_profiles.py -- functional_registry.py / basis_resolution.py / data_catalog.py (XC, approvals, per-element resolution)
 |-- basis_registry.py (immutable allocated numbers/string IDs, roles/status, explicit legacy migration)
 |-- basis_resolution.py -- basis_registry.py / cp2k_data.py / data_catalog.py (ORB/potential protocol checks)
 |-- cp2k_data.py -- io.py / structure.py (actual aliases, selected payload/q checks, paths/hashes/ambiguity)
 |   Basis/potential/D3/nonlocal-kernel whole-line filenames use literal unquoted serialization.
 |-- basis_ui.py -- basis_registry.py / cp2k_data.py (one grouped scrolling basis-value list)
 |-- data_catalog.py (header-only names/q/files and pinned official source hashes)
 |-- all_electron_catalog.py (audited AE subsets, local reference identity; no parameters)
 |-- gapw.py (versioned derived numerical setup; explicit OT overrides win)
 |-- constraints.py (compact fixed-atom parsing, bounded active expansion, keyword evidence)
 |-- density_workflow.py -- inputgen.py / io.staged_files (whole/A/B bundle, shared generator, explicit mapping)
 |-- spin_settings.py (explicit Ueff/L parsing, collinear atom seeds, stable KIND splitting)
 `-- cube.py ------- models.py / io.py / structure.py (units; streaming checks/differences)

models.py: data model/schema version
io.py: strict reads, hashes, stable JSON, exclusive outputs
errors.py: domain exceptions/machine-readable exit codes
__main__.py / pyproject.toml: module/console-script entry points
```

Conventional src layout. No plugins, database, workflow engine, or configuration
framework yet; avoid complexity exceeding MVP value.

## Density input bundle (0.2.9)

inputgen dispatches enabled workflows to density_workflow; that module calls the
same generator for each component with the workflow flag disabled. It does not
contain another chemistry parser/renderer. Resolve the whole geometry and derived
numerical defaults once, then select fragment subsets without centering or cell
reconstruction. Filter per-element requests to present atoms and explicitly map
magnetic @whole selectors to local indices. Compare selected per-element basis,
potential and source identities. Lock whole NGRIDS=5 when applicable; requested
common grids are not proof of matching produced CUBEs.

The ordinary generator manifest remains complete, extended with component manifests
and mapping; settings/replay/config remain semantic. CSV mapping is mandatory for
the bundle, JSON optional. bundle_paths is shared by writer, CLI and TUI. The
workflow reuses io.staged_files to preflight, stage and publish exclusively, rolling
back only owned inodes on ordinary errors/interrupts. No existing bundle input is
replaceable; no crash-atomic multi-file guarantee, calculation or subtraction.
See [workflow/schema](schema.md#generated-input-json-menuworkflow-additions-software-029).

## Result pipeline

```text
output/directory -> deterministic selection -> line format matching -> Run/Segment/Quantity/Evidence
                                                                     |-> quality_report
                                                                     |-> JSON/long-form CSV
                                                                     `-> PNG/data CSV/manifest
```

- Start markers/non-increasing optimization/MD steps split segments.
- Energies retain record indices and nullable calculation steps.
- ENERGY records accept explicit `[a.u.]` or `[hartree]` labels (case-insensitive);
  both are stored as hartree without numerical conversion. Other units remain
  unsupported. Values require a complete numeric token followed by whitespace or line end.
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

functional_registry defines the 15 non-hybrid profiles plus six hybrid profiles, aliases, exact XC
components/native shortcuts, build/dispersion requirements and intrinsic nonlocal
assembly. It is dependency-light and shared by basis policy, CLI, TUI and generation,
not a parallel generator. method_profiles resolves explicit XC branches, per-element basis overrides and fixed-q
catalog entries; inputgen still orchestrates physical validation, rendering and
protected writes. Multiple basis files are emitted/checked independently. Matched
potentials are preferred; explicit approval is required for a GTH-PBE approximation.
RPBE, all meta-GGAs and BEEF-vdW (native shortcut using Libxc PW92) require a
user Libxc-build assertion, not runtime/build detection. Meta-GGA/nonlocal scope
is GPW Gamma ENERGY/ENERGY_FORCE/GEO_OPT without +U. Required nonlocal terms
are separate from additional pair dispersion. Kernel source bytes/hashes and
emitted filenames are recorded separately from runtime/numerical validation;
CDD compares whole/A/B nonlocal identity before protected publication. Method
metadata distinguishes catalog references from installed-data hashes and preserves
actual potential library identity. No generic input-rewriting migration is introduced.
hybrid.py validates explicit HF controls and resolves direct-four-center HFX
operator/radius/resources and optional t_c_g.dat byte provenance. inputgen renders
its HF section alongside ordered native XC parameters or Libxc components.
resolve_functional requires explicit PBEh fraction and derives a single effective
profile for XC/HF/metadata, without mutating the shared registry. M06-2X shares
the kinetic-energy-density flag/warnings with the semilocal meta-GGAs. Its D3
reference M062X is separate from canonical profile ID M06-2X. No extra Libxc
semilocal scaling or automatic exact-exchange inference is introduced. Hybrid
scope is target 2026.2, GPW classic MOLOPT/UCL, Gamma, NONE/XYZ,
ENERGY/ENERGY_FORCE/GEO_OPT without +U/smearing. Periodic global hybrids use
face-spacing-bounded truncated Coulomb; isolated ones use full Coulomb; HSE06
uses matching XC/HF omega=0.11 bohr^-1. ADMM is separately opt-in for
PBE0/HSE06 since 0.3.4; no RI-HFX or UZH-PBE0 protocol is activated. Existing density/CDD and staged publication are reused. HF control
edits at menu 120 share CLI/config/replay semantics; inactive nondefault requests
fail rather than silently disappearing. Defaults add no HF section to pure DFT.
ADMM assembly lives in admm.py, not the XC definitions or HF operator resolver.
It retains the direct four-center backend but uses the smaller AUX_FIT basis.
Solver-derived purification is explicit in the effective model, never a solver
repair. auxiliary_basis.py owns separate immutable 200-203 IDs/numbers using
the existing BasisOption/AUX_FIT role and Libraries Gaussian parser; ORB choices
are unchanged, RI_AUX remains rejected. Actual ORB/AUX source files are mandatory,
with selected-entry/q checks and duplicate checks across the final emitted union.
Only used files are emitted, deduplicated, hash-recorded and writer-protected.
Kinds carry aux_fit metadata; CDD compares per-element auxiliary identity and
global ADMM settings as well as HFX identity. No calculation is invoked.
This is not the deferred ARC-3 prepared-state/render/manifest separation.

Do not inherit original electronic settings. Unknown PBC, electron/spin conflicts,
and unsupported combinations are rejected. Element presets explicitly match
basis/potential valence counts; optional local data checks verify names/hashes.
Omitted whole-system multiplicity resolves from selected PP/AE electron-count parity
minus charge (even 1, odd 2); explicit values are preserved. This is not a prediction
of ground-state spin. Default UZH references use portable BASIS_MOLOPT_UZH /
POTENTIAL_UZH aliases, while resolved paths/hashes and emitted_data_files remain
separate manifest evidence. Explicit data-file overrides are preserved.
No calculation or Multiwfn/adjacent-source dependency.

The initial registry-v1 follow-up retained software 0.2.6 by explicit user request. Basis
numbers are permanent allocated IDs, not tuple positions; stable strings are
persisted in settings/replay. Legacy names are normalized at boundaries, numeric
migration needs explicit legacy version information, and registry-v1 configs never
infer old positions from software 0.2.6 alone. Actual files override header catalogs;
missing/ambiguous/q-incompatible entries are rejected without physical repairs.
All emitted libraries are checked for cross-KIND alias shadowing. One potential
file must represent all KINDs; no automatic library merge/replacement is performed.
[The basis guide](basis-selection.md) specifies source precedence, UZH-PBE pairs,
custom 900, unknown-q/templates and unavailable/retired/reserved roles. Auxiliary
roles are modeled separately but not selectable. Selected-entry data checks and
recognized reference pairs are separate from native acceptance and scientific fitness.

The line-oriented input editor maintains drafts, performs local type/range checks,
and rechecks changes through the shared generator without repairing physical conflicts.
menu_registry owns full IDs, category, aliases, semantic key, label and editor;
shared visible_fields rules provide applicability. Main, category and direct
routes all dispatch the same entry/editor/state, including source/data/output
controls. Category 0/back returns without publication; edits and read-only previews
return to their origin. Generator-main 0 invokes the shared validator/writer directly,
without review/confirmation; w reviews first and requires explicit y/yes. Successful
generation returns immediately without a pause. Automatic TUI output naming follows
the source stem and CDD toggle (.inp / -CDD.inp), unless explicitly overridden.
Function layout v1 is independent of immutable basis registry v1 and atom indices;
value prompts do not dispatch function IDs. Old 0.2.8 extension numbers migrate
explicitly, without ambiguous aliases or changes to semantic CLI/config fields.
Hidden requests remain retained and scientifically validated. Presenter handles
folding/optional Rich, Menu handles prompts, and editor/application dispatch the
existing business APIs. Source/frame changes warn about retained atom selections,
never remap identities. Collision recovery can choose a new target.
Complete batch calls stay noninteractive; stdin/stdout TTY are required for menus.
Bare cp2kkit/cp2kkit STRUCTURE opens the grouped application menu. cli.menu_request
handles this syntax separately from batch parsing; command names come from actual
argparse registrations, not a second list. A single unknown word retains path
semantics. -- PATH (optionally preceded by --plain) treats PATH literally, including
leading hyphens; invalid mixed arguments still go through argparse usage errors.
Both streams must still be TTY. --plain/NO_COLOR
disable styling. EOF/q exits the session; Ctrl+C cancels an operation (exits at main).
Default physical settings are unchanged. Library filenames are now unquoted;
JSON is opt-in (501/--write-json), existing regular .inp replacement is permitted.
write_input returns (input_path, nullable_json_path, warnings). Optional JSON is
completed before input publication, so its collision/failure preserves old input.
Sources/data/symlinks and all other output workflows remain protected. IDs 112/103 request
explicit Ueff/L and collinear magnetic initialization; 210 edits orthorhombic cell
lengths, 230-234 edit data sources, also accessible in the basis chooser. spin_settings validates and maps element/atom selectors without changing
charge/multiplicity or source geometry. Split KIND labels retain ELEMENT-specific
basis/potential/U. Only target 2026.2 is checked for these opt-in features. The 0.2.6 GGA/basis profiles
also require target 2026.2. Menu 221 configures explicit element basis overrides;
114 approves unmatched-functional PBE potentials; 113 asserts target Libxc support.
114/113 follow functional applicability while preserving hidden values. NGRIDS uses
shared resolve_ngrids over actual effective basis IDs: only classic non-SR
TZVP/TZV2P/TZV2PX emit 5; others omit it and record null.
Menu 324 configures OT IRAC/STRICT (hidden/retained for diag); 225 selects the
legacy AE auto/native names (same explicit IRAC default). PP OT explicitly
emits STRICT; manual selections override either model. Electron-model classification precedes spin validation.
AE uses Z rather than PP valence, with null PP q/valence fields. Effective GAPW
settings (numerical profile v4) omit explicit QS split tolerances and KIND atomic
grids in both auto/native modes. Empty qs/kind and cp2k_default_controls record
this omission without guessing runtime values. Other settings are rendered by the
same generator, and disclosed in review/JSON. No automatic physical-state repair. Schema 0.1.0 gains additive raw settings, generated
KIND mapping, method/catalog/file identity and reference metadata.

Restart hints, motion output and radius handling also live in inputgen, not in
CLI/TUI forks. Trajectory format (-5) is visible for GEO_OPT/CELL_OPT; radius
(403) only for BFGS/LBFGS optimization. Hidden requests persist in settings/replay;
restart_template and motion_output distinguish hints/raw requests from emitted
controls. Restart filenames derive from resolved PROJECT and Gamma/non-Gamma
naming, not the .inp output path. Suggestions remain metadata/review only, not
commented input directives. Only generator/Multiwfn header comments remain.
SCF and MOTION explicitly disable restart backups, not restart writing. No restart
is opened by generation.

Optimization-only menu 9 / --fixed-atoms delegates to constraints.py and the
same inputgen writer. Selections stay compact until checked against the active
loaded structure; repeated LIST lines keep emitted input bounded. Source/frame
changes retain indices with a warning, never infer identity remapping. Explicit
fractional XYZ constraints and inactive requests are distinguished in metadata.
No source/POSCAR constraints are implicitly inherited.

## GFN-xTB dispatch (0.3.1)

InputSettings.method defaults to DFT, preserving old configs/default text.
generate_input dispatches xTB to xtb.py before GPW/GAPW electron/basis resolution;
xTB never calls BasisResolver or GPW density generation. resolve_geometry and
motion_lines remain shared with DFT; write_input retains its source/data/staged
publication protections. Model electron counts, intrinsic dispersion, native
parameter hashes and tblite build assertion/accuracy are explicit, not a second
interpretation of GTH q. xtb_versions.py pins tagged 2024.2-2026.2 capabilities
and source hashes; unsupported model/version pairs fail before publication.
Legacy/new parameter filenames and tblite activation/mixer/accuracy layouts stay
separate. OT remains available for GFN1; GFN2 OT generation is gated by the shared
version profile to target 2026.2 only after a native 2026.1 crash. Legacy targets
2025.2/2026.1 require explicit diag; unsupported default/explicit/retained OT fails
in the shared generator before publication, without changing SCF choices.
The 2025.2 gate is conservative, not native validation. gfn2_ot_enabled records
generator policy, not build detection. convergence_control/accuracy_role describe
OT versus native SCC semantics.
No parameter coefficients or external process is used.

Chooser 1/110 appends upstream xTB 30/31/32 while retaining old DFT positions.
140/141/142 share semantic model/build/accuracy fields, CLI and replay. Hiding an
inapplicable field never clears it; generation rejects conflicting nondefault
DFT/density requests. xTB review uses model semantics, never claims a GPW basis,
Poisson solver or installed backend version. Initial scope and manifest branch
are described in [generation](input-generation.md#gfn-xtb-methods-031) and
[schema](schema.md#generated-input-json-gfn-xtb-branch-software-031).

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
