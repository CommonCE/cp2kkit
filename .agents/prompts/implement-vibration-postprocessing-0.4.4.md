# Prompt: implement bounded vibrational post-processing for 0.4.4

Work in the cp2kkit repository. Implement the first bounded vibrational-result
post-processing stage described below, not a general vibrational spectroscopy
or thermochemistry platform. This is the original handoff plan; see the
[implemented result contract](../../docs/vibration-results-contract.md) for
current interfaces, behavior and limits.

Use English for maintained development text, code, CLI/TUI messages and tests
unless the user explicitly requests another communication language. Preserve
original scientific keywords, source quotations, units, paths and user data.

## 1. Establish the actual baseline

Read AGENTS.md, `.agents/DEVELOPMENT.md`, README, pyproject.toml,
`docs/architecture.md`, `docs/schema.md`, `docs/contracts.md`,
`docs/vibration-contract.md`, `docs/closeout-0.4.3.md` and the applicable
feature/contract/version prompts before editing. Inspect current Git status,
source, tests, fixture provenance and existing user changes; preserve unrelated
work. Repository state wins over this plan if the implementation has moved on.

Inspect in particular:

- `src/cp2kkit/main_tui.py`: ACTIONS, run_main_menu and analysis routing;
- `src/cp2kkit/cli.py`: batch dispatch, output conventions and error handling;
- `src/cp2kkit/parser.py`, `models.py`, `quality.py` and `discovery.py`:
  existing observation, segment, provenance, selection and status semantics;
- `src/cp2kkit/io.py`, `export.py` and `errors.py`: finite deterministic JSON,
  exclusive publication, rollback and exit codes;
- `src/cp2kkit/vibration.py`: input-generation policy, not a result parser;
- main-menu/PTY, parser, GEO_OPT contract, file-protection and project-text tests.

Use the Python-environment guidance before execution. Reuse available verified
Python 3.10/3.12 environments; do not download interpreters or install optional
packages without authorization. Keep logs in new ignored local directories.
Do not hard-code personal environment paths into maintained files.

## 2. Deliverable and bounded scope

The user assigns software **0.4.4**, overriding the normal feature-version rule.
Keep software at the actual baseline while investigating; update to 0.4.4 once
for the implemented round. Formal release packaging is deferred until **0.5**:
no sdist/wheel builds, package upload, tag or Release creation for this task.
Do not commit or push without a new explicit authorization.

Deliver read-only observation of existing **molecular CP2K vibrational output**:

1. Locate and parse the supported native frequency blocks.
2. Retain printed mode order, frequency values/signs/units and exact evidence.
3. Report observed positive, negative and near-zero frequencies with an explicit
   user-controlled reporting threshold; retain raw values without correction.
4. Distinguish complete versus truncated/malformed text evidence and unsupported
   format/scope. Never promote a partial spectrum into a complete result.
5. Offer the same report through Python, batch CLI and application main menu,
   plus deterministic JSON and long-form CSV export.

Initially establish supported format evidence against CP2K **2026.2**, matching
0.4.3's generated task. Do not impose PBE/RKS/OT as parser restrictions merely
because the input generator has those restrictions: parsing support depends on
observed format and result semantics. Conversely, do not advertise other native
versions, task variants or periodic phonons without evidence and tests.

Out of scope: IR/Raman intensities or spectra, broadening, animation/eigenvector
export, reconstructed Hessian diagonalization, mass/isotope changes, scaling
factors, ZPE/entropy/free energy/thermochemistry, periodic phonon dispersion,
automatic optimization/restarts, execution and scheduler integration. These may
be planned later, but must not delay or silently enlarge this first stage.
The 0.4.3 generator disables intensities/thermochemistry; missing data cannot
be synthesized from frequencies or reported as zero.

Future Shermo integration belongs to the molecular vibration/thermochemistry
workflow, with independent requests, derived-result provenance and explicit
execution authority. Periodic phonons require a separate future workflow and
scientific contract. Both remain outside 0.4.4; this navigation plan does not
authorize running Shermo, preparing phonon calculations or expanding the parser.

## 3. Main-menu placement and navigation

At the inspected 0.4.3 baseline, ACTIONS contains seven application entries.
The user-approved pre-release workflow layout supersedes the earlier append-only
main-8 proposal; see docs/menu-numbering-draft.md. Implement this explicit migration:

- Preserve main entries **1-4**, entry **0 Exit** and existing structure state.
- Main **5 Output analysis** groups output workflows. Local **1 Quality report**
  retains the old main-5 operation; local **0 Back** returns without writing.
- Main **6 CUBE analysis** groups local **1 Check scalar CUBE** and
  **2 Subtract density CUBEs**, formerly main 6 and 7. Local **0 Back** returns.
- Main **7 Vibrational analysis** opens the frequency workflow directly, without
  a redundant single-operation submenu. Use semantic ID `vibration` and
  requires_structure=False. All three post-processing entrances work without
  a loaded geometry and preserve any existing structure state.
- Existing parse/plot/cube-planar CLI adapters are future menu additions, not
  required scope for this round. Do not display unimplemented placeholders.
- Input-generator **640** remains a finite-displacement input setting, not a
  post-processing entry. Application, local and generator IDs are separate.
- If concurrent changes conflict with this layout, reconcile rather than silently
  reorder. Do not keep ambiguous numeric aliases for the old main-7 operation.
- Add explicit dispatch for workflow groups and vibration before scalar-CUBE
  handling; group/vibration actions must not fall through into CUBE parsing.
- Ask for an existing output path, resolve any segment/block ambiguity, then show
  a bounded summary: source, selected block, observed count, signed frequencies,
  threshold/categories, completeness and warnings. Do not dump Hessians/forces.
- Provide optional full details and explicit JSON/CSV export to a new path.
  Merely opening or inspecting the report must not write files.
- Reuse scrolling Presenter/Menu navigation, back/cancel/q and non-TTY rejection.
  Returning retains the previously loaded structure. Preserve the positive-width
  fallback and narrow-terminal behavior fixed during 0.4.3 acceptance.

## 4. Native-format investigation before implementation

Inspect the relevant tagged CP2K 2026.2 source/manual and any available existing
outputs read-only. Establish actual headings, unit labels, mode identifiers,
frequency grouping, signed/imaginary notation, block boundaries and end markers.
Locate the relevant writer routines rather than invent a universal regex from
one frequency line. Record references and supported format limits.

Specifically distinguish normal-mode results from displaced-force/SCF replicas,
Hessian matrices, vibrational diagnostics and the native Minimum Structure label.
Investigate what CP2K prints or projects for translations/rotations; do not assume
that every printed block contains 3N, 3N-5 or 3N-6 frequencies. Do not silently
remove the lowest five/six values or decide linearity from a filename.

Do not copy actual private logs, paths, scheduler IDs or installation diagnostics
into versioned fixtures/docs. Public fixtures must be tiny, synthetic or
appropriately provenance-documented native-format excerpts. Synthetic format
coverage is not native execution or scientific validation. Existing local native
outputs may inform inspection but must not become a mandatory test dependency.
No new CP2K run or submission is authorized by this prompt.

## 5. Implementation architecture and proposed interfaces

Prefer a focused result module such as `vibration_results.py`, distinct from
input-generation `vibration.py`. Keep CLI/TUI as adapters over one parser/report
and writer implementation. Do not put scientific classification in the UI or
change general GEO_OPT energy/final-state meanings to accommodate this feature.
Reuse Evidence/Quantity, raw-file hashes, finite-number helpers and exclusive
writers where appropriate, without building a generic plugin framework.

Proposed interfaces below are design targets, **not existing APIs**. Reconcile
names/signatures with actual project conventions and document the final contract:

- A read-only Python parse/report entry point accepting an explicit output file
  and optional segment/block selection and reporting threshold.
- Batch command `cp2kkit vibration PATH`, with `--format json|csv`, optional
  `-o PATH`, explicit segment/block selectors when needed,
  `--zero-threshold-cm-1 VALUE` and optional `--strict`.
- Stdout contains the requested JSON/CSV when no output path is supplied;
  diagnostics belong on stderr. File output is opt-in and exclusive.
- CLI and TUI call the same public report/writer functions. No configuration or
  replay loader is required merely because generated-input manifests have one.

Start with explicit output files. If directory discovery is added, reuse existing
ambiguity rules and require explicit resolution; never select by mtime or guessed
filename. If concatenated runs/repeated analyses offer multiple candidate blocks,
require selection rather than quietly choose the last or most complete block.
Use stable, documented selectors and retain incomplete candidates in diagnostics.

Use deterministic stateful parsing if needed for block context. Accept supported
Fortran E/D exponent forms with complete-token validation. Reject or explicitly
diagnose nonfinite, overflow-placeholder and malformed frequency records; never
turn them into zero, silently omit them or salvage numeric prefixes as values.
Retain valid observations from recognizable partial blocks with diagnostics;
unrecognized/unsupported input must not masquerade as an empty successful result.

## 6. Meaning, evidence and classification

Define a small typed result/report with source SHA256/path, detected native
software/version, segment/block identities, observed mode records, diagnostics,
completeness/status and cp2kkit parser identity. Preserve line numbers and raw
source text for each observation. Use printed mode IDs only when present;
otherwise use a separately labeled record ordinal, not a fabricated native ID.

Report frequencies in explicit **cm^-1** after verifying the source unit.
If conversion of another supported source unit is implemented, document the
constant/provenance and retain the original unit/value. Preserve printed precision
and sign; never take abs(), scale frequencies or perform automatic unit guessing.
Missing/unknown fields are null/absent with documented semantics, never numeric 0.

Default reporting threshold is **0.0 cm^-1**, not a scientific noise criterion.
Accept a finite nonnegative threshold t. For frequency f, classify f < -t as
negative, f > t as positive and abs(f) <= t as near-zero; retain f unchanged.
Keep the raw negative-frequency count separate from threshold-dependent counts,
so a small negative value cannot disappear into an unqualified "no negatives".
Only describe a printed imaginary notation as such after its native meaning is
verified. A negative-frequency marker is not automatically a validated saddle.

Keep separate, evidence-qualified axes for frequency-block completeness, program
end markers, electronic convergence, process exit status, stationarity and
scientific interpretation. Missing process exit status remains unknown; a native
Minimum Structure heading does not prove optimization. Positive frequencies do
not certify a minimum, nor does one negative frequency certify a transition state.
A reporting threshold does not prove numerical convergence or justify discarding
low modes. Do not infer geometry identity or stationarity from a supplied input
manifest, selected structure, project name or filename.

## 7. Errors, publication and contract

Preserve existing exit-code meanings: 2 invalid request/I/O, 3 ambiguous selection,
4 unrecognized/unparseable supported input, 5 collision, 6 optional dependency
when relevant, and 7 only for an explicitly requested strict report not passing
its documented **textual** criteria. Negative frequencies alone must not cause a
strict failure or a scientific "failed" verdict. Recognizable partial observations
may be exported with incomplete status; define/test the distinction from ParseError.

Use shared exclusive publication: no source overwrite, no replacement of existing
analysis files, including .inp targets, and no symlink-following escape from source
protection. Preflight all bundle targets; if multiple artifacts are necessary,
reuse staged_files and its owned-inode rollback, without a crash-atomic claim.
Prefer one requested JSON or CSV artifact rather than mandatory extra sidecars.

Assess the contract against docs/contracts.md and docs/schema.md. Add a focused
vibrational-result contract and tiny public selected-field example only where
this distinct observation boundary warrants them. Keep it separate from the
0.4.3 generation contract; a proposed calculation is not an observed spectrum.
Determine schema compatibility explicitly; do not bump schema just because the
software becomes 0.4.4 or force new observations into an unrelated result type.
Specify types, units, optional/null fields, evidence, selection, statuses, errors,
stdout/file effects and consumer tolerance. No downstream consumer repo,
credentials, database or adapter integration is required or certified.

## 8. Acceptance and delivery

Add tests covering:

- Complete supported frequency blocks; zero, positive, negative and small negative
  values; t=0 and explicit thresholds/boundaries; E/D forms and precision.
- Truncation, malformed/nonfinite tokens, unsupported units/formats, duplicate IDs,
  missing mode IDs and partial blocks, with no silent numeric defaulting.
- Repeated/concatenated blocks, explicit selectors, invalid selection and ambiguity;
  no frequency records fabricated from SCF/force/Hessian diagnostics.
- No assumptions that missing translations/rotations are zero-valued observations,
  including documented linear/nonlinear printing variations where supported.
- Python/CLI/TUI report parity, JSON/CSV and source hashes/line evidence, stderr
  separation, strict versus ordinary behavior and actual exit codes.
- Main-menu action 7 without a structure; 1-4 routing unchanged; main-5/local-1
  quality and main-6/local-1/2 CUBE migration; cancel/back, retained structure,
  non-TTY behavior and real-PTY/narrow/unsized-terminal handling.
- Existing-output/symlink/source protection, bundle rollback where applicable,
  deterministic output, and all prior generation/GEO_OPT observation contracts.

Run focused checks first, then full regression and compileall with the selected
verified interpreters. Retain exit statuses and bounded logs, not raw log dumps.
Do not install Matplotlib to eliminate expected optional skips. Report actual
passed/skipped counts and tested Python/OS combinations, not inherited totals.
Update software to 0.4.4 once, README/changelog/roadmap, menu documentation and
applicable schema/contract/provenance records. Preserve historical acceptance
counts and third-party terms; a format-reference inspection is not a new grant.
Check English maintained text, local links, version consistency and whitespace.

Deliver changed paths, actual API/CLI/menu usage, representative synthetic output,
checks and gaps. Clearly separate observations, numerical/scientific assessment
limits and future visualization/spectroscopy work. Do not claim a published
release, package acceptance, native execution or scientific certification.

Related: [development rules](../DEVELOPMENT.md),
[feature workflow](implement-feature.md),
[contract maintenance](maintain-contract.md),
[public contracts](../../docs/contracts.md),
[0.4.3 generation contract](../../docs/vibration-contract.md).
