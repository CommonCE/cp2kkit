# Development handoff: 0.4.5 thermochemistry and follow-up priorities

Task keyword: **CP2KKIT-NEXT**. This is a reference label for this document.

Use English for maintained documentation, code, CLI/TUI messages and tests unless
the user explicitly requests another communication language. Preserve original
scientific keywords, quotations, units, paths and user data.

## Start here

Read [AGENTS.md](../AGENTS.md) and the
[development rules](../.agents/DEVELOPMENT.md), then inspect Git status and the
actual implementation. The bounded **0.4.4 molecular vibrational-result
observation stage** is closed; see the [acceptance record](closeout-0.4.4.md)
and [result contract](vibration-results-contract.md). The original
[implementation prompt](../.agents/prompts/implement-vibration-postprocessing-0.4.4.md)
and delivery steps below are retained as scope and acceptance history. The
[0.4.5 stage](roadmap.md#045-stabilization-energy-vibrations-and-shermo)
adds external Shermo thermochemistry and bounded CP2K reference observations.
A future internal engine is a separate task, not a capability in 0.4.5.

## Current handoff: 0.4.5

The 0.4.5 implementation is in the uncommitted working tree, including new
files. The latest committed baseline at handoff is `9392ced` (0.4.4). Preserve
both tracked edits and untracked additions; use `git status --short` and do not
assume checking out `HEAD` reconstructs 0.4.5. The working-tree software version
is 0.4.5 and the exchange schema is 0.1.0.

The target workflow starts from an optimized molecular geometry. The user runs
vibrations and a separate, possibly larger-basis single point in parallel on
that same geometry. `cp2kkit thermochemistry --energy-output ...` (or main
**7 / s**) takes frequencies from the vibration output and electronic energy
from the explicitly selected single-point output. `--energy-segment` selects a
1-based segment if needed. The code does not launch either CP2K calculation or
fall back to the vibrational energy when an explicit single point is invalid.
Shermo supplies corrections to add to the single-point electronic energy; ZPE
is reported separately, not added twice. Without an explicit single point, a
usable native vibration footer may supply the electronic energy; the current
bounded generator emits `THERMOCHEMISTRY F`, so do not assume that footer exists.
See the [thermochemistry contract](shermo-thermochemistry.md) and
[provenance](../THIRD_PARTY_NOTICES.md#shermo) for source formats and tested scope.

- **Implemented:** explicit local Shermo 2.6.2 execution, read-only import via
  `shermo-read`, distinct single-point and vibration provenance, shared CLI/TUI
  path, one selected isolated molecular mode table with strictly positive modes,
  one temperature/pressure and harmonic or Grimme low-frequency treatment.
- **Verified at handoff:** Python 3.12.16, 32 focused tests passed; full regression
  ran 705 tests (702 passed, three optional Matplotlib skips). Compile and diff
  checks passed. Shermo interface checks used the supplied 2.6.2 source,
  synthetic stdout and a mocked process. Neither real CP2K nor real Shermo had
  run at that handoff; see the subsequent native checks below. No package build,
  installation, commit, tag, or push was performed for this stage.

### 0.4.5 source-tree closeout

- Managed thermochemistry now rejects evidence of a different charge between
  the selected CP2K files or a printed multiplicity inconsistent with the
  explicit request. Missing metadata remains unknown. Vibration JSON adds
  `reference_state`; CSV and exchange schema 0.1.0 are unchanged.
- On Linux, Python 3.12.16 passed all 707 source tests and Python 3.10.22 passed
  704 with three optional Matplotlib skips (707 collected). Both passed 38
  focused tests, compileall and the `cp2kkit 0.4.5` CLI version check.
- No new native calculations or external Shermo execution were performed for
  this closeout. The two water checks below are earlier, case-specific evidence.
  This closes the bounded source iteration, not a build, package release,
  publication or broader scientific validation.

### Native external follow-up: adapter smoke check passed

With explicit authorization, local Shermo 2.6.2 ran once with a hand-written
exchange file and once through `cp2kkit thermochemistry`. Both used existing
CP2K 2026.2 water files: PBE/GPW frequencies and a separate GFN2-xTB single
point with identical input coordinates, charge 0 and multiplicity 1. The
adapter selected `-5.070436321212379` Hartree from single-point segment 1 and
three modes from vibration segment 1/block 1. Both runs exited 0 with empty
stderr; `shermo-read` also imported the direct stdout. At 298.15 K, 1 atm,
unit scaling and Grimme entropy interpolation (100 cm^-1 cutoff), ZPE and
U/H/G corrections and totals agreed at Shermo's printed precision. The three
frequencies are all above the cutoff, so this case does not exercise the
below-cutoff regime. No CP2K calculation was run. The hand-built reference
geometry has nonzero forces; this is adapter evidence, not validation on an
optimized minimum or justification for mixing these two electronic methods.

### Optimized water follow-up: native vibration-footer path passed

One authorized CP2K 2026.2 GFN2-xTB frequency job used an existing geometry
converged with the same model (charge 0, multiplicity 1). It completed with code
0 and empty stderr; tblite/OT warnings were present. The strict parser matched
all three positive modes in the Molden output and selected the native footer
energy (`-13312.71246887` kJ/mol, approximately `-5.070544433589856` Hartree)
without an independent single point. Direct Shermo 2.6.2 and the adapter agreed
at printed precision on ZPE and U/H/G corrections and totals for harmonic
frequencies at 298.15 K and 1 atm.

This is not agreement between the native CP2K and Shermo RRHO implementations.
Their ZPE agreed at Shermo's displayed kJ/mol precision, but Shermo's H and G
corrections differed by about +1.239 and -1.646 kJ/mol, respectively. CP2K printed
symmetry number 1, while Shermo identified nonlinear C2v with symmetry number 2.
Symmetry alone does not explain those differences. The H difference is close
to RT/2, consistent with the linear-rotor branch in the reviewed CP2K 2026.2
`get_thch_values` implementation for molecular-scale SI moments of inertia.
The adapter does not substitute CP2K's thermal corrections for Shermo's.

### Next-session priority: external Shermo `imode=1` for surface modes

**Proposed, not implemented or natively validated.** Keep the existing 0.4.5
isolated-molecule path as the default. Consult the supplied Shermo 2.6.2 source
(`Shermo.f90`, `sub.f90`, `calc.f90` and `loadfile.f90`) as an interface
reference; do not port it.
Shermo `imode=0` includes ideal-gas translation and free rotation. `imode=1`
omits those terms but still treats the supplied modes and electronic levels.
It does not select Hessian atoms, remove hindered modes or perform q-point
integration. CP2K `FULLY_PERIODIC` is a separate Hessian projection control.

- **Evidence first:** look for an existing real CP2K 2026.2 periodic surface
  partial Hessian, its full slab-plus-adsorbate structure and a same-geometry
  full-system single-point output. Verify the native active-atom indices,
  order and mode count before changing validation. Look for existing Shermo
  2.6.2 `imode=1` stdout. Ask before any new native run or submission; prior
  authorizations do not cover this case.
- **Proposed interface:** explicit `--thermo-model ideal-gas|vibrational-only`
  with equivalent Python/TUI settings. Preserve gas defaults; continue
  passing `-noset` and an explicit native `-imode`. Record the thermal model
  separately from the Hessian's active atom scope; do not auto-select a model
  from PBC, the atom count or a filename.
- **Bounded first case:** whole-atom constraints with an explicit active list
  matched against the displacement rows in the complete periodic reference
  structure. Verify the expected `3 * active_atom_count` positive modes for
  this native branch; do not use the gas-phase `3N-5/6` rule or silently drop
  zero/imaginary modes. Require an independent same-geometry full-system
  electronic energy: CP2K skips its molecular thermochemistry footer when
  atoms are frozen. Retain separate provenance for those modes and that energy.
- **Result and acceptance:** verify Shermo's native `imode=1` markers for
  omitted translation and rotation, including in `shermo-read`. The mode does
  not print gas-phase rotational symmetry or molecular linearity; represent
  inapplicable quantities explicitly and do not label the result an ideal-gas
  pressure standard state. Start with harmonic settings; compare direct Shermo
  and adapter ZPE and U/H/G at printed precision, including U/H correction
  equality in this mode. Retain `imode=0` regression coverage and evaluate
  schema compatibility independently. This is a selected-mode correction,
  not a complete adsorption free energy.

Full-system periodic Gamma vibrations, q-point integration, hindered-motion
models and adsorption free-energy subtraction remain outside this first case.

### Other follow-up work

1. **Optimized-geometry independent-single-point reference check.** Prefer
   existing outputs: use one optimized XYZ with convergence evidence, its
   CP2K 2026.2 frequency output, a separate same-geometry single-point output
   and Shermo 2.6.2. Check file/segment identities, the exact selected single-
   point Hartree value, mode count and settings, then compare ZPE and U/H/G
   against an independently prepared Shermo run at the same settings and
   reported precision. Preserve small distributable excerpts with provenance
   if available. Any new native execution requires separate authorization and
   a disposable/new directory.
2. **Internal backend (not implemented).** Once the external reference cases
   are established, define bounded algorithm parity and review upstream terms
   before reusing code or data. Keep the backends explicit; no silent backend or
   method substitution. Do not treat the I/O adapter as an algorithm port.
3. **Automatic cross-file association (not implemented).** Current association
   is a caller assertion plus atom-order, mode-count and available charge/spin
   checks; it does not prove identical coordinates, charge/spin or the optimization's
   final converged frame. There is no optimization-to-frequency-to-single-point
   job orchestration, automatic final-frame/energy selection, general CP2K
   energy extraction redesign or broad version/format support matrix.
4. **Deferred scope.** No transition-state/imaginary-mode thermochemistry,
   temperature/pressure scans, solution standard states, ensembles, additional
   Shermo low-frequency policies, or periodic phonons. Energy here means
   electronic energy, not activation barriers or NEB analysis. Formal packaging
   and expanded delivery checks remain a 0.5 readiness task.

For a later round, inspect the working tree and read the [Shermo
contract](shermo-thermochemistry.md). The read-only `imode=1` reference search
is a suggested starting point if surface-mode support is selected. It is not
required for 0.4.5 closeout and does not authorize execution.

## Historical 0.4.3 baseline

At handoff preparation, software is **0.4.3** and exchange schema is **0.1.0**.
The bounded vibrational input generator exists; a vibrational-result parser and
the planned application menu grouping do not. See the
[0.4.3 closeout](closeout-0.4.3.md) for historical acceptance evidence.

Existing working changes include the 0.4.4 implementation prompt, its index entry,
and roadmap/menu planning. Preserve these and unrelated user work. Historical
test counts and native checks are evidence of earlier stages, not current results.

## Original delivery plan: 0.4.4

1. Establish supported CP2K 2026.2 frequency-block formatting from tagged native
   source/manual and available existing output. Record headings, units, printed
   mode identities, block boundaries and completeness evidence before choosing
   parsing rules. Do not infer mode counts or scientific validity from a filename.
2. Implement one shared read-only parser/report/writer path. Preserve signed
   frequencies in cm^-1, source hashes, line evidence, observed order, incomplete
   records and explicit segment/block selection. Keep the raw negative count
   separate from threshold-dependent categories; the reporting threshold does
   not modify frequencies or establish numerical convergence.
3. Expose the same results through Python, the planned batch vibration command,
   and TUI. Keep the result implementation distinct from input-generation policy
   in `vibration.py`. Follow the final public contract rather than treating the
   proposed signatures in the implementation prompt as existing APIs.
4. Apply the [menu migration](menu-numbering-draft.md#application-workflow-layout-044):
   retain main 1-4, group output analysis at 5 and CUBE analysis at 6, and put
   vibration at 7. Old main-7 subtraction moves to 6/2. Preserve structure state,
   cancellation, terminal behavior and existing batch commands.
5. Complete the public result contract, deterministic JSON/CSV, opt-in exclusive
   file export, error/ambiguity behavior and relevant executable examples/tests.
   Preserve existing GEO_OPT observation meanings and source protection.
6. Run the focused and regression checks required by the implementation prompt
   with verified available interpreters. Report actual outcomes, skips and limits.
   Update software to the assigned 0.4.4 once; assess schema compatibility
   independently. Formal package builds remain deferred to the planned 0.5 stage.

The implementation prompt contains the full acceptance matrix, including malformed
numbers, partial/repeated blocks, strict reporting, file collisions and PTY cases.
Finish those applicable checks before reporting the stage complete. Reading a
frequency block, observing an end marker, and establishing a stationary point
remain separate conclusions.

## Original roadmap maintenance scope

Update the [roadmap](roadmap.md) to match the delivered state. Keep current status,
the next bounded milestone and future candidates visibly separate. In particular:

- Reconcile the old status table's deferred plane-average wording with the
  implemented 0.4.0 native-grid profiles.
- Distinguish existing bounded RI-HFX and vibrational input support from broader
  combinations and tasks that remain deferred.
- Preserve historical closeout counts, failed candidates and provenance. Link
  historical records rather than silently rewriting them as current acceptance.
- Retain full Multiwfn generator coverage as a long-term goal. Order subsequent
  increments by useful research workflows and their evidence requirements.

Keep this documentation update proportional; a repository-wide documentation
reorganization is not a prerequisite for completing 0.4.4.

## Broader follow-up candidates (historical 0.4.4 handoff)

| Priority | Candidate | Required boundary before implementation |
|---|---|---|
| Focused checks in 0.4.5; broader coverage later | Representative native-format fixtures and compatibility matrix | Separate synthetic tests, format evidence, actual execution and numerical/scientific validation. Use small distributable examples with provenance. |
| Bounded to the 0.4.5 workflow | Energy/structure/frequency association | Define evidenced step/frame/run relationships and unknown/ambiguous states. Preserve last-observed energy semantics; do not infer final structures from filenames or the last frame. |
| Toward 0.5 | Delivery readiness | Propose a current support matrix, lightweight CI, install/package checks and compatibility/distribution boundaries. These are readiness recommendations, not authorization to publish. |
| Separate track | Read-only Agent/MCP adapter | Reuse stable public parsing/quality contracts. Follow AGENT-1 in the roadmap; a complete generator refactor is not its prerequisite. |
| External in 0.4.5; internal later | Shermo-related thermochemistry | Preserve independent provenance for exchange, read-only import and explicit external execution. Establish external comparison evidence and terms before implementing the internal backend. |
| Later independent workflows | Periodic phonons, trajectories, MD and reaction paths | Establish each workflow's inputs, normalization, scientific meaning and acceptance separately. Do not expand the molecular frequency parser to imply these capabilities. |

Follow the roadmap's bounded 0.4.5 scope; the remaining candidates are not
part of that release. Incrementally separate generator validation/resolution,
rendering and manifest assembly when a concrete preview/capability consumer needs
it, following ARC-3 in the roadmap. Avoid broad preparatory refactoring.

## Execution boundaries and delivery report

This handoff does not authorize CP2K/Shermo execution, scheduler submissions,
replacement of scientific results, dependency installation, package publication,
Git commits, tags or pushes. Use existing outputs read-only and disposable test
artifacts; retain unknown evidence as unknown. Do not add consumer-specific
databases, private fixtures or workflow-engine dependencies.

Report changed paths, actual API/CLI/menu usage, contract and migration impacts,
representative synthetic results, checks actually run and remaining gaps. Distinguish
completed work from follow-up proposals. Do not claim native/scientific validation
or downstream integration from producer tests.
