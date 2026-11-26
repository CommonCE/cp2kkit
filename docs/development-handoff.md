# Development handoff: 0.4.9 and follow-up priorities

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
adds external Shermo thermochemistry and bounded CP2K reference observations;
[0.4.7](roadmap.md#047-surface-adsorbate-vibrations-and-shermo-imode1) extends
the full generation/parsing/Shermo chain to periodic surface partial-Hessian
adsorbate vibrations and external Shermo `imode=1`.
A future internal engine remains a separate task.

## Current handoff: 0.4.9

The working-tree software version is **0.4.9** with exchange schema **0.1.0**.
This stage completes bounded read-only GEO_OPT/CELL_OPT convergence criteria
observation and explicit trajectory-step association:

- **Convergence criteria observation (`models.py`, `parser.py`, `quality.py`,
  `export.py`, `plot.py`):** parses CP2K 2026.x `OPT|` and legacy
  `Convergence check` records for the four Cartesian criteria (`bohr`,
  `hartree/bohr`) and `CELL_OPT` signed pressure deviation/tolerance (`bar`),
  retaining Step 0, exact `0.0`, and per-line provenance while keeping legacy
  `Energy` indexing and long-form CSV columns unchanged. Malformed records and
  completion-marker contradictions block `passed`. `plot --kind convergence`
  writes exclusive PNG/CSV/JSON with a linear signed pressure subplot when
  present.
- **Explicit trajectory-step association (`structure.py`, `trajectory.py`,
  `cli.py`, `viewer.py`, `main_tui.py`):** adds `cp2kkit match-trajectory`
  and TUI **5/4** with explicit `.out` + `.xyz`/`.extxyz` paths, 1-based
  `--segment` selection, `1e-6` hartree default tolerance, CP2K 2026.2 EXTXYZ
  `Step=`/`Time=`/`Energy=` parsing, conservative preceding line-search
  disambiguation via `OPT| Total energy [hartree]`, and segment-scoped
  `- Atoms:` count cross-checking (`atom_count_mismatch`). Export (`-o`
  reserved before `--export-structure`) and single-frame `--view` staging
  require verified step matches and never fall back to `frames[-1]`.
- **Source-tree closeout checks (Linux):**
  - Python 3.12.16 full environment (with optional Matplotlib/Rich): all **770**
    tests passed with **0** skips (including 27 tests in
    `tests/test_opt_criteria_trajectory.py`, `tests/test_project_text.py`, and
    `tests/test_version.py`); `compileall`, `cp2kkit --version` (`0.4.9`), and
    `git diff --check` passed.
  - Core-only verification (with Matplotlib and Rich blocked): 25 of 27 tests
    in `tests/test_opt_criteria_trajectory.py` passed with 2 optional
    Matplotlib skips.
  - Bounded read-only format checks exercised CP2K 2026.2 `BFGS` `GEO_OPT`
    (`XYZ`) and `CELL_OPT` (`EXTXYZ`) outputs (confirming signed pressure
    deviations, `Step=`/`Time=`/`Energy=` EXTXYZ headers, Step 0/extra-frame
    separation, and cross-system `- Atoms:` mismatch rejection); these checks
    do not certify general CP2K execution, real X11 viewer rendering, `CG`/
    `LBFGS` native line-search outputs, or scientific validity.
- **Deferred (next stages):** `0.5.0` packaging/CI/PyPI/MCP (`AGENT-1`) and
  documentation restructuring (`DOC-1`) remain separate work. See the
  [optimization observation contract](geo-opt-contract.md).

## Historical handoff: 0.4.7

The software version at this stage was **0.4.7** with exchange schema **0.1.0**.
This stage implements the end-to-end bounded periodic surface adsorbate workflow:

- **Generation (`vibration.py`, `inputgen.py`, `input_tui.py`, `cli.py`):**
  accepts `PERIODIC XYZ` + explicit whole-atom `--fixed-atoms` (at least one
  fixed and one active atom), skew cells, `POISSON_SOLVER PERIODIC`,
  `FULLY_PERIODIC T`, minimal `&MOTION/&CONSTRAINT/&FIXED_ATOMS`, and `OT/STRICT`
  or `diag` with optional Fermi-Dirac smearing and `ADDED_MOS` at Gamma. Isolated
  molecular inputs keep their exact 0.4.6 text and catalog-only SHA-256.
- **Observation (`vibration_results.py`):** accepts consistent `CELL|`/`POISSON|
  Periodicity XYZ` outputs without `ROT|` projection, preserves non-unit starting
  `displacement_atoms`, checks positive unique atom indices per group, and adds
  `periodicity`, `periodicity_sources` and `rotovibrational_vectors`.
- **External Shermo `imode=1` (`thermochemistry.py`, `cli.py`, `main_tui.py`):**
  adds explicit `--thermo-model ideal-gas|vibrational-only`, required
  `--active-atoms` and independent full-system `--energy-output` for
  `vibrational-only`, explicit `--element-masses EL=MASS ...` alongside
  `--masses-amu`, `-imode 1 -PGlabel C1` execution, default `harmonic` with
  optional `grimme` (carrying an explicit rotational-inertia caveat), `U == H`
  verification, nullable gas-phase rotation/linearity/point-group fields and
  `shermo-read` import for both `imode=0` and `imode=1`.

- **Source-tree, interpreter and packaging checks (Linux):**
  - Python 3.12.16 full environment (with optional Matplotlib/Rich): all **731**
    tests passed with **0** skips; `compileall` (bytecode directed to a
    temporary cache), `cp2kkit 0.4.7` CLI version check and `git diff --check`
    passed.
  - Python 3.12.16 core-only environment (no Matplotlib/Rich): **727** of
    **731** tests passed with **4** optional Matplotlib skips; `compileall` and
    CLI version check passed.
  - Python 3.14.10 core-only environment: **727** of **731** tests passed with
    **4** optional Matplotlib skips; `compileall` and CLI version check passed.
  - Offline wheel build and isolated virtual-environment install: built
    `cp2kkit-0.4.7-py3-none-any.whl` (52 files including `THIRD_PARTY_NOTICES.md`,
    `third_party/multiwfn/TERMS.md`, `third_party/multiwfn/PROVENANCE.md` and
    the `cp2kkit` console script), installed offline into a clean venv, and
    verified `cp2kkit --version` (`cp2kkit 0.4.7`) and `cp2kkit vibration --strict`
    outside the source tree. Python 3.10 was not locally installed and remains
    untested.
- **Pre-release 0.4.7 hardening (P1/P2 fixes):**
  - `_select_single_point()` now inspects only the selected `ENERGY`/`ENERGY_FORCE`
    segment's line range (without altering raw `parser.parse_output` energy
    semantics) and rejects nonzero Fermi-Dirac `Electronic entropic energy`
    (`-T_e S_e`), nonzero Gaussian/Methfessel-Paxton/Marzari-Vanderbilt
    `Smearing free energy correction` (kept distinct from physical electronic
    entropy), differing `Total energy (extrapolated to T->0)` or `Total energy
    (extrapolated to sigma->0)`, damaged field delimiters/unit brackets/values,
    total atom-count conflicts against the full reference XYZ, and periodicity
    conflicts against the vibration segment / reference XYZ / thermal model
    before launching Shermo. Genuinely unprinted fields remain `missing` (`null`).
  - `vibration_results.parse_vibration()` recognizes complete `CELL|`/`POISSON|
    Periodicity` and `ROT|` field names before validating native whitespace
    separators and full values so malformed lines (including non-native
    punctuation such as `POISSON| Periodicity: XY` or trailing tokens) raise
    `ParseError` instead of being downgraded to `null`.
  - `vibration._check_dx_resolvable()` rejects `DX` values that overflow `2*DX`
    or displaced `+/-DX` bohr coordinates (e.g. `1e308`), preserving normal
    molecular input bytes and defaults.
- **Post-fix native CP2K 2026.2 and Shermo 2.6.2 acceptance (bounded):**
  - **Periodic surface generation and `imode=1` end-to-end (35-atom periodic
    `XYZ` MgO(001) 2x2x2 slab with atoms `1-32` fixed + adsorbed H2O active
    atoms `33-35`, PBE-D3(BJ)/DZVP-MOLOPT-SR-GTH):**
    - Verbatim 0.4.7-generated `VIBRATIONAL_ANALYSIS` inputs ran cleanly on
      CP2K 2026.2 with both `OT/STRICT` (on an initial symmetry-constrained
      saddle point, detecting `-270.51 cm^-1` and confirming `cp2kkit
      thermochemistry` rejects imaginary modes before Shermo launch) and
      non-smearing `--scf diag` (on the symmetry-broken local minimum, yielding
      9 strictly positive modes `287.08..3760.83 cm^-1`, passing `cp2kkit
      vibration --strict` with active atoms `33-35`).
    - Pairing that local-minimum vibration output with its verbatim
      0.4.7-generated non-smearing `--scf diag` `ENERGY` single point
      (`-1288.062278931975470` Hartree, `- Atoms: 35`, no smearing/entropic
      records) through `cp2kkit thermochemistry --thermo-model vibrational-only
      --active-atoms 33-35` and local Shermo 2.6.2 succeeded for both default
      `harmonic` (`ZPE = 0.026431`, `corr U = corr H = 0.027815`, `corr G =
      0.025789`, `tot U = tot H = -1288.0344638`, `tot G = -1288.0364899`
      Hartree; exact printed-precision parity with independent direct Shermo
      2.6.2 `-imode 1 -PGlabel C1` imported via `cp2kkit shermo-read`) and
      explicit `grimme` (`tot G = -1288.036494` Hartree with the rotational-
      inertia caveat).
    - Observed SCF caveat: on the minimum geometry without a wavefunction
      restart, tight `EPS_SCF 1e-8` with `OT DIIS / ALGORITHM STRICT / FULL_ALL`
      diverged in outer SCF, whereas non-smearing `--scf diag` converged cleanly.
  - **Native CP2K 2026.2 Gaussian-smearing gate check (4-atom periodic fcc Al,
    `METHOD GAUSSIAN`):** CP2K 2026.2 printed `Smearing free energy correction:
    -0.00308524639573` and `Total energy (extrapolated to sigma->0):
    -8.03013924817456` alongside `Total FORCE_EVAL: -8.031681871372426` Hartree;
    raw `parser.parse_output` preserved `-8.031681871372426`, while hardened
    `cp2kkit thermochemistry` rejected it before Shermo launch without
    mislabeling it as physical electronic entropy and wrote no output file.
  - **Scope limit:** these bounded native checks verify the 0.4.7 generation,
    parsing, smearing-gate and Shermo `imode=1` pipeline on specific small test
    systems; they do not certify arbitrary chemical systems, SCF/frequency
    convergence or scientific accuracy.
- **Historical adapter-parity evidence (pre-smearing-gate; NOT post-fix end-to-end acceptance):**
  - Prior to adding the P1 smearing electronic-entropy gate, an authorized
    read-only local Shermo 2.6.2 comparison used an existing periodic `XYZ` CP2K
    2026.2 surface partial-Hessian output (183-atom slab+adsorbate, 180 frozen
    atoms, active atoms `181-183`, 9 positive modes) paired with its matching
    Fermi-Dirac smearing single-point output (`-7122.823623845493` Hartree, which
    contains a nonzero `Electronic entropic energy: -0.00015332267878` Hartree).
  - That historical check established that `cp2kkit vibration --strict`,
    `cp2kkit shermo-read`, and the Shermo `-imode 1` adapter agreed at printed
    precision with a direct Shermo 2.6.2 harmonic run (`ZPE = 0.025945`,
    `corr U = corr H = 0.028040`, `corr G = 0.024002`, `tot U = tot H =
    -7122.7955838`, `tot G = -7122.7996217` Hartree) and exercised the
    below-cutoff `56.08 cm^-1` mode under explicit `grimme`.
  - **Post-fix status:** verified against local Shermo 2.6.2 that hardened 0.4.7
    rejects combining that nonzero `-T_e S_e` single-point output automatically
    with Shermo before launching Shermo and writes no output file.

## Historical handoff: 0.4.6

The working-tree software version is 0.4.6 with exchange schema 0.1.0. The
[0.4.6 stage](roadmap.md#046-analysis-menu-parity-and-molecular-vibration-inputs)
adds only three local analysis adapters and widens the existing molecular input
subset to D3/D3(BJ) and UKS. See the [tagged-source force path](vibration-contract.md#pair-dispersion-force-path)
for static evidence. No CP2K or Shermo execution is part of this milestone;
closed-shell no-dispersion inputs, batch CLI commands and main **7 / s** are retained.

Source-tree checks: Python 3.12.16 passed all 38 focused and 726 regression
checks with no skips. Python 3.10.22 passed 37 of 38 focused and 722 of 726
regression checks, with one and four optional Matplotlib skips, respectively.
The seven project text/link and version tests, compileall, and the CLI version
check passed on both interpreters; `git diff --check` passed. These checks do
not establish native CP2K or Shermo acceptance, force/frequency convergence,
spin-state continuity, scientific validity, or packaging readiness.

## Historical handoff: 0.4.5

Historical 0.4.5 workflow and acceptance notes follow; they do not validate
0.4.6 inputs or expand its scope.

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

Follow the roadmap's bounded 0.4.6 scope; the remaining candidates are not
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
