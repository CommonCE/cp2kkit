# Development status and next steps

Current software: **0.3.6**; schema: **0.1.0**.

The sections below record implementation and preparation milestones. Subsequent
small-system smoke checks do not broaden the supported combinations or establish
general scientific accuracy, force accuracy or performance.

## Native validation preparation (0.3.6; no calculations)

- [Preparation protocol](admm-ri-native-validation.md) and example helper stage
  six water ENERGY cases: direct HFX, ordinary ADMM, ADMMS, independent RI,
  ordinary ADMM+RI and ADMMS+RI. Identical PBE0/RKS/OT/NONE geometry, cell,
  charge/spin, ORB/potential and common numerical settings isolate the declared
  approximation/backend differences. Inputs/data are written to a new directory.
- Byte provenance, portable case-local data links and null pending result fields
  accompany the inputs. Synthetic helper tests do not establish native acceptance.
- Native syntax/build, clean exit, SCF convergence, paired energy differences,
  convergence studies and timing/memory each have separate acceptance gates.
  No binary probe, CP2K/MPI run or scheduler submission is performed; actual
  execution still requires explicit authorization, resources and new run paths.

## Explicit ADMMS Stage 2 (0.3.6)

- Explicit `admm_variant` / `--admm-variant` / menu 122 selection defaults to
  BASIS_PROJECTION, preserving legacy meaning. ADMMS is never implied by RI.
- ADMMS resolves charge-constrained projection, NONE purification and MERLOT
  scaling with DEFAULT correction. MO_DIAG is rejected, not overridden.
- Initial scope: target 2026.2 PBE0 classic GPW Gamma NONE RKS OT ENERGY,
  without explicit magnetism/CDD; optional RI requires metric HFX. Broader
  independent ordinary ADMM behavior is unchanged.
- Config/manifest/CLI/TUI replay and protected publication are covered by synthetic
  tests; native syntax/build, convergence, accuracy and performance remain unverified.
  Actual calculations require separate authorization and new run directories.

## Ordinary ADMM + RI-HFX Stage 1 (0.3.6)

- Implement the [audited minimum](admm-ri-hfx-audit.md): target 2026.2 PBE0,
  classic GPW Gamma NONE closed-shell RKS OT ENERGY / RI_METRIC HFX only.
  Explicit magnetism and CDD bundles are excluded, independent modes unchanged.
- Reuse checked AUX_FIT identity as the automatic RI parent. Preserve ordinary
  BASIS_PROJECTION, purification, scaling NONE and DEFAULT correction; no ADMMS.
- CLI/TUI/config/manifest replay share validation and existing protected writers.
  Parent/source checks and synthetic tests are not native or numerical validation.
- Stage 2 adds explicit ADMMS above. Deferred: broader combination scopes, native syntax,
  convergence, comparison with ADMM/direct HFX and performance checks. Native
  work requires separate authorization and new run directories.

The following version sections describe historical implementation stages;
0.3.6 supersedes their blanket RI+ADMM exclusion only for the intersection above.

## Returned-run hardening (0.3.5)

- Automatic hybrid data files use portable runtime names when they resolve to
  the checked sources in the selected data root. Explicit overrides remain
  unchanged; absolute source evidence remains protected. T_C_G_DATA uses t_c_g.dat.
- Hybrid ENERGY_FORCE explicitly prints forces to stdout in hartree/bohr.
  Periodic HSE06 range preflight warns using the documented screening equation
  and emitted-cell face spacing, without model/threshold changes.
- User-returned native 2026.2/git:c92cc08 evidence contains 71 input-matched
  SCF-converged outputs, all with late SIGSEGV, plus one stale failed reference;
  all 16 GEO_OPT cases report convergence. Eighteen HSE06/XYZ cases warn about
  range/cell compatibility. Thirty RI/direct energy pairs are provisional;
  force accuracy, finite differences, RI size/radius convergence and speedup
  remain unverified. No clean-exit acceptance or stable RI release claim.
- Next: resolve runtime shutdown failures, recover the missing fresh reference,
  review periodic HSE06 models and collect actual force/convergence evidence in
  separately authorized new run directories. Existing inputs/results are not
  repaired or resubmitted. Menu IDs, physical defaults and schema are unchanged.

## RI-HFX and hybrid acceleration matrix implemented (0.3.5)

- Add explicit PBE0/HSE06 Gamma RI-HFX at 121 for target 2026.2, retaining
  classic GPW NONE/XYZ ENERGY/ENERGY_FORCE/GEO_OPT, RKS/UKS and OT/diag
  without +U/smearing. Other-hybrid RI, RI+ADMM, non-Gamma, CELL_OPT,
  GAPW, manual RI bases and UZH-PBE0 remain deferred.
- Require actual ORB files and reuse selected payload/alias/q/hash checks;
  AUTO_BASIS RI_HFX MEDIUM (optional SMALL/LARGE/HUGE), SORT_BASIS EXP,
  metric HFX inheriting the shared exchange operator, RI_FLAVOR RHO.
  This is not an AUX_FIT/RI_AUX registry expansion.
- Optional independent TRUNCATED metric requires an explicit angstrom radius;
  XYZ bounds use emitted-cell face spacing. HFX stays the default; no automatic
  Multiwfn-matching radius. All RI modes resolve/protect T_C_G_DATA for startup.
  Full-path threshold metadata/review separates QS source-derived precision from
  HF/RI native defaults, without changing numerical inputs.
- Shared CLI/TUI/config/replay exposes metric/radius, size, EPS_FILTER and MEMORY_CUT;
  inactive nondefaults fail. MEMORY_CUT is batching, not total memory;
  direct HF/MEMORY is not emitted and nondefault hf_memory conflicts with RI.
- Publish the [hybrid acceleration capability matrix](input-generation.md#ri-hfx-and-hybrid-acceleration-matrix-035)
  and additive effective metadata, reusing CDD HFX identity checks and protected
  writers. Existing direct/ADMM input text defaults remain unchanged.
- Initial implementation used target-version manual/local sources and synthetic
  generation/regression only. Later returned-run observations and remaining
  validation limits are recorded in the 0.3.5 section above; real checks still
  require separate authorization and fresh run directories.


## ADMM auxiliary-library emission correction (0.3.4, version retained)

Version remains 0.3.4 by explicit user request; the correction is retained.

- Require matching orbital records before applying a portable UZH orbital alias;
  auxiliary-only files keep their resolved source paths. The default data-directory
  and environment paths no longer need the explicit orbital-file workaround.
- Add emitted-file/manifest checks for all auxiliary sizes, source-selection
  routes, CLI and shared libraries; preserve the genuine UZH orbital behavior.
- Existing 0.3.4 inputs are not repaired automatically. Regenerate to new paths.
  No physical settings, schema or interfaces change; no CP2K calculation is run.

## ADMM and auxiliary-basis infrastructure implemented (0.3.4)

- PBE0/HSE06 opt-in ADMM: BASIS_PROJECTION, exchange scaling NONE,
  operator-consistent DEFAULT correction; auto MO_DIAG for OT / NONE for diag.
  No change of solver, HFX fraction, range parameter, radius or potential family.
- Independent AUX_FIT registry 200-203 / admm-dz, admm-dzp (default),
  admm-tzp, admm-tz2p. Actual ORB/AUX data required, with selected Gaussian
  payload/q/hash checks and conflicting-alias rejection across emitted files.
- Shared CLI/API/TUI/config/replay, menu 122/223, split KIND and CDD identities;
  existing writers protect auxiliary sources and preserve sidecar exclusivity.
- Existing target-2026.2/classic-GPW/Gamma/NONE-or-XYZ/hybrid task/spin/SCF
  gates remain. No RI-HFX, UZH-PBE0, GAPW or ADMM on the other hybrids.
- Defaults remain ADMM-off and schema 0.1.0. Local source/data inspection and
  synthetic software checks are not native acceptance or scientific validation.
  See [ADMM capability and limits](input-generation.md#admm-and-auxiliary-bases-034).


## Remaining direct-HFX profiles implemented (0.3.3)

- Add BHandHLYP (50% HF), M06-2X (54% HF, kinetic-energy density), and PBEh
  (explicit dimensionless fraction in (0,1], no default) at chooser 19/20/21.
- Require Libxc assertion for the two fixed Libxc hybrids; preserve existing
  bounded direct-HFX tasks/models/operators, family potentials and writers.
- M06-2X permits D3 with reference M062X, not D3(BJ); BHandHLYP/PBEh permit
  no extra pair correction pending a separate parameter/identity audit.
- All 21 Multiwfn-referenced DFT selections now have bounded generation paths;
  this is not full Multiwfn feature parity, native acceptance or scientific validation.
- CLI/TUI/config/replay/CDD use the same effective XC/HF definition. No calculations.
- User-authorized fresh comparison: Multiwfn 2026.10.18, 64 pairs/128 successful
  generator processes, 62 policy-adjusted matches. Two M06-2X-D3 inputs differ
  in upstream reference key (M06-2X versus checked CP2K 2026.2 M062X); other
  checked semantics/data match in 64/64. High-precision PBEh allows documented
  upstream rounding, not exact fraction identity. 48 negative CLI checks and
  479 regression tests passed; no native CP2K calculation or acceptance test.

## Hybrid family-potential correction (0.3.2)

- Prefer actual exact-hybrid entries; otherwise select GTH-BLYP for B3LYP and
  GTH-PBE for PBE0/HSE06 without extra approximation approval.
- Preserve family identity, approximation status, data hashes and fixed q.
  Missing family entries fail without cross-family substitution. Other XC
  approval policies and hybrid scope remain unchanged; no CP2K calculation.


## Implemented first direct-HFX hybrids (0.3.2)

- PBE0 → HSE06 → B3LYP input generation, shared API/CLI/TUI/config/replay;
  local chooser 16/17/18 preserves original 1-15 and xTB 30/31/32.
- Target 2026.2, GPW classic MOLOPT/UCL Gamma NONE/XYZ ENERGY/ENERGY_FORCE/
  GEO_OPT, RKS/UKS, OT/diag without smearing or +U; existing density/CDD reused.
- Complete native XC/HF definitions: PBE0 25%, HSE06 25% short-range with
  matching omega=0.11 bohr^-1, B3LYP 20% and explicit VWN3.
- Explicit full/short-range/truncated operators; periodic global auto radius
  min(6 angstrom, minimum emitted-cell face spacing/2.01); user radius bounds,
  screening and per-MPI-process MiB memory controls at 120/CLI.
- No restart-dependent SCREEN_ON_INITIAL_P, solver/model changes, automatic
  ADMM/RI-HFX, UZH-PBE0 enablement or fabricated matched potentials.
  Data-directory TRUNCATED inputs require protected/hash-recorded t_c_g.dat.
- Source/manual checks and synthetic generator tests only; no CP2K calculation.
  Broader combinations and native/scientific validation remain separate.
  See [capability matrix](input-generation.md#direct-hfx-hybrids-032).


## Implemented parser compatibility follow-up (0.3.1 retained)

Version retained by explicit user request. Total FORCE_EVAL energy parsing accepts
both `[a.u.]` and `[hartree]` labels, preserving hartree values and original
text/line/hash evidence. Complete-token checks, rejection of unsupported units,
malformed/non-finite handling, segmentation and conservative quality rules remain
unchanged. Regression fixtures are synthetic; read-only checks of existing local
CP2K 2026.1 xTB output are a separate, narrow format check, not version certification.
Validation: 455 regression tests passed, none skipped, including expanded synthetic
unit/token-boundary cases and a CLI subprocess check. Read-only re-parsing of the
10 existing local xTB outputs recovered all reported energies in the seven normally
terminated runs, matching recorded values/evidence and unchanged source hashes;
the three crashed GFN2 runs still have no energy records. These logs remain local
under `test-workspace/xtb-native-20261021-123240-bJMHj1/`, not bundled fixtures.
No new calculation or submission is part of this parser fix. GFN0 non-SCC quality
classification and the observed GFN2 OT runtime crash remain outside this fix.

## Implemented GFN2 OT crash protection (0.3.1 retained)

Reject GFN2 OT for legacy targets 2025.2/2026.1 in the shared generator before
writing; require explicit `--scf diag` / menu 320, without changing saved requests
or automatically falling back. Target 2026.2 retains OT; version_compatibility
adds gfn2_ot_enabled as generation policy, not proof of installed build support.
The 2025.2 restriction is conservative and has no native-run evidence.

Earlier user-authorized diagnostics used isolated H2O, charge 0/multiplicity 1,
Gamma/no smearing, one/four MPI ranks, one thread and bounded optimization:
local 2026.1/git:5e54ba2 default OT at one rank and IRAC OT at four ranks crashed
with exit 139, matching the earlier default four-rank crash. Its diagonalization
ENERGY (one/four ranks), ENERGY_FORCE and GEO_OPT converged; local
2026.2/git:c92cc08 OT passed the same four-case task/rank matrix, including
geometry completion. Local sources show the legacy OT p_mix_new density-update
path versus the newer use_rho branch. Compiler/backend builds also differ;
revision strings alone do not prove official-release equivalence or a unique fix.
Evidence and hashes remain local under
`test-workspace/gfn2-ot-diagnosis-20261021-124634-mJ9t2F/` (not bundled fixtures).
No new calculation or submission is part of this generator protection change.
GFN0/GFN1, default DFT physics and schema 0.1.0 remain unchanged.
Validation: 458 regression tests passed, none skipped, including 23 xTB tests.
Read-only replay of 20 prior local input manifests produced byte-identical input
text for 15 still-supported cases and rejected five legacy GFN2 OT requests;
source inputs remained unchanged. Version/text/link checks, compileall and
`git diff --check` passed. No new native run is implied by these checks.

## Planned Agent integration and optional MCP support

Status: **planned, not implemented**. This is a parallel development track to
scientific feature coverage, not a claim of an available MCP server, registered
Pi tools, or company-platform compatibility. No release version or delivery date
is assigned yet.

### Scope and architecture

Support the personal Pi Agent and the company-developed computational Agent
through a shared deterministic toolkit API. Keep intent interpretation and
workflow decisions in the host Agent; cp2kkit remains responsible for validated
input generation, parsing, quality assessment, and evidence-preserving exports.

- Reuse existing domain models, registries, validators, parsers and protected
  writers. CLI, TUI and Agent adapters must not implement separate scientific rules.
- Define supported request/result contracts with semantic parameter names, units,
  index conventions, side effects and compatibility rules. TUI navigation numbers
  are not an Agent protocol. Preserve existing CLI exit codes and distinguish the
  tool-contract version from software and scientific-data schema versions.
- Add MCP as an optional thin adapter, with an optional dependency or separate
  adapter package; preserve the standard-library core and independent CLI/TUI.
  Company integration may instead use an existing internal tool protocol over
  the same API. Do not require a plugin framework, database or workflow engine.
- Confirm the actual Pi integration mechanism and company tool protocol, file
  access model and execution ownership before implementing host-specific setup.

### Staged delivery and acceptance

| Stage | Planned scope | Acceptance boundary |
|---|---|---|
| AGENT-1: contracts and read-only MVP | Define supported API/error contracts; expose project discovery, output parsing and quality assessment through a local stdio MCP adapter | Test tool discovery, request/result schemas, ambiguity, malformed/truncated output, non-TTY operation and protocol-only stdout; results agree with shared core logic and preserve evidence/unknown values. Host integration is claimed only after an actual client smoke test. |
| AGENT-2: preview and protected generation | Add structure inspection, input validation/preview and explicit file publication; incrementally advance ARC-3 validation/resolution/render/manifest separation | Preview creates no files; shared defaults, scientific settings and generated text remain consistent with CLI/TUI. Agent writes reject existing targets by default; any replacement requires separately defined explicit authorization. Test collisions, source changes between preview/write, repeated calls, interruption and rollback without changing existing CLI replacement behavior. |
| AGENT-3: capabilities and enterprise integration | Expose capabilities derived from shared registries/rules; map workspace-relative paths or artifact IDs; add a company adapter and remote MCP transport only when needed | Report target-version, task/model/build/data restrictions and validation levels without duplicating policy. Verify workspace isolation, artifact resolution, bounded responses, authentication/authorization and audit requirements in the agreed deployment. Company compatibility remains unverified until checked there. |

The first MVP does not depend on completing the full ARC-3 refactor. Extend the
adapter incrementally after read-only contracts are stable; structure export and
Cube checks/differences are later candidates, not automatically exposed commands.
Prefer local stdio for the initial personal integration. Evaluate Streamable HTTP
for remote/shared deployment only after checking client compatibility, the target
MCP specification/SDK, and service-security requirements.

### Tool contracts, safety and evidence

- Return structured domain errors with stable identifiers, affected fields and
  explicit candidates or missing information. Preserve ambiguity rather than
  choosing by file time; request scientific decisions instead of silently changing
  charge, spin, periodicity, approximations or unsupported combinations.
- Keep validation/preview separate from publication. Recheck source identity and
  target protection at write time; reuse staged publication and ownership-aware
  rollback. Do not imply crash-atomic multi-file writes or blind retry safety.
- Enforce allowed read/write workspaces, path/symlink checks and resource limits
  in the tool/service boundary, not merely in prompts or tool descriptions.
  Define timeouts, cancellation and partial-output behavior. Bound file reads and
  responses; large logs/Cubes should return summaries and artifact references.
- Keep content hashes, units, source locations and scientific evidence. Define
  path/raw-text redaction before external transfer; do not embed secrets or
  sensitive company structures/results in prompts, fixtures or audit logs.
  A remote file path alone does not transfer or grant access to an artifact.
- Distinguish tool completion, input generation, syntax acceptance, actual execution,
  normal termination, electronic/geometry convergence and scientific validity.
  Build assertions and source/data checks must not become runtime certification.
- Exclude arbitrary shell execution, job submission/cancellation, deletion and
  autonomous repair/reruns from the initial tools. Future execution integration
  requires separate scope and authorization, stable job identities, duplicate-job
  prevention and recovery; prefer the company's existing execution system.
- Review actual third-party authorization for the intended internal use, service
  deployment or distribution before company rollout. The unresolved boundaries in
  [third-party notices](../THIRD_PARTY_NOTICES.md) remain; MCP wrapping or a Python
  rewrite does not establish additional permission.

### Verification and dependencies

Add deterministic contract and adapter tests with synthetic fixtures/mocks for
normal, invalid, ambiguous and interrupted requests, write protections and host/core
consistency. Keep stdio protocol output separate from diagnostics. Test installation
with and without optional MCP dependencies and retain CLI/TUI regression coverage.
No test may implicitly launch CP2K or submit jobs; real client checks, native CP2K
validation and scientific validation are separate evidence levels.

Continue the existing real-fixture/version-matrix and packaging/CI priorities below.
Agent access does not improve parser coverage by itself. This roadmap entry changes
no current API, schema, dependency, Agent configuration or execution authorization.

## Proposed 0.3.x scope: functional and method coverage

The [functional/method expansion proposal](functional-roadmap-0.3.md) follows
Multiwfn 2026.10.1's outCP2Kinp menu and XC/HF/ADMM/RI/dispersion branches,
not an independently chosen 14-profile list. The reference DFT scope contains
21 selections (including configurable PBEh and complete B97M-rV/BEEF-vdW),
without counting ADMM/dispersion variants as additional functionals. Preserve the original five profiles.
Add the **GFN-xTB series (GFN0, GFN1, GFN2)** separately: native GFN0/1,
tblite GFN2. Stage registry/LDA/GGA, meta-GGA, complete nonlocal methods and
hybrids; xTB can proceed after method dispatch exists. Audit target-version
keywords/units, data/model pairing, spin, tasks and build requirements; do not
copy automatic physical changes, unchecked parameters or direct writes blindly.
MP2/RPA/GW, double hybrids and other non-XC methods remain separate later scopes.
The non-hybrid subset is implemented in 0.3.0 below; 0.3.1 adds xTB before
hybrids at the user's request. Version 0.3.2 now adds PBE0/HSE06/B3LYP;
version 0.3.3 adds BHandHLYP, M06-2X and configurable PBEh. Default PBE input
physics is unchanged.

### 0.3.1 implemented GFN-xTB scope

- Separate method dispatch and model reference electron counts, not XC profiles
  or GTH q reuse. Exact new chooser IDs: 30 GFN1, 31 GFN0, 32 GFN2 (tblite).
  140/141/142 expose model, explicit tblite build assertion and numerical accuracy.
- Checked release targets: 2024.2/2024.3/2025.1/2025.2/2026.1/2026.2 for GFN1;
  GFN0 starts at 2025.1, GFN2/tblite at 2025.2. Emit legacy/new syntax, filenames
  and data hashes per target; reject unavailable upstream backends without fallback.
  Keep H-Rn, nonperiodic Gamma closed-shell ENERGY/ENERGY_FORCE/GEO_OPT.
  GFN1 defaults to OT; GFN2 OT is now enabled only on target 2026.2, with explicit
  diag required on legacy targets as documented above. GFN0 is non-SCC. GFN2 OT uses
  EPS_SCF, 2026.2 native SCC/diag uses ACCURACY. Fixed-atom references are
  target-specific for xTB; EXTXYZ starts at 2026.1.
- Shared geometry/motion/constraints and staged input writer; optional JSON,
  config/replay and menu applicability. Native parameter/D3 files can be read/
  hash-checked at pinned identity; no model coefficients or Fortran are bundled.
- Historical compatibility follow-up, before the native crash guard: 450 tests passed (20 xTB-specific tests), none skipped.
  Earlier 0.3.1 checkpoint: 444 tests/14 xTB tests; no native calculations.
  Source/data-only assembly passed 39 valid model/version/task cases across
  all six targets; all native H-Rn electron tables agree. GFN2 built-ins remain
  backend_unchecked; no linked build is probed. Generated DFT text matched the pre-change
  generator in all 45 water profile/task comparisons. Read-only native data
  assembly checked GFN0 model bytes and GFN1 model/D3 bytes; GFN2 built-ins stay
  backend_unchecked. Synthetic generation/interface/negative/protection tests
  and static source/data checks only.
  No CP2K/Multiwfn/tblite execution, linked-build detection or scientific validation.
  Periodic/open-shell/non-Gamma/CELL_OPT/density/CDD/+U/refits and hybrids remain
  deferred. See [the xTB guide](input-generation.md#gfn-xtb-methods-031).

### 0.3.0 implemented non-hybrid scope

- Fifteen profiles: original five GGAs plus PADE/BP86, TPSS/revTPSS/SCAN/r2SCAN/
  MN15L/HLE17 and complete B97M-rV/BEEF-vdW. Shared semantic registry, aliases,
  CLI/menu/config/replay and additive XC/kernel provenance; basis/function IDs
  and existing first-five functional chooser positions are unchanged.
- Target 2026.2 for new profiles. Meta-GGAs/nonlocal methods: GPW Gamma
  ENERGY/ENERGY_FORCE/GEO_OPT without +U. Explicit build assertions include
  BEEF-vdW's internal Libxc PW92. No automatic PBE-potential approximation,
  q/model changes or pair-dispersion addition to nonlocal methods.
- PADE/BP header coverage audited at fixed q; complete nonlocal parameters/kernel
  filenames and supplied-file hashes recorded. Kernel source checks do not
  validate numerical kernels; runtime/grid convergence remain unverified.
- Validation: **430 tests passed, none skipped**, including 27 new synthetic
  non-hybrid methods and retained default-input regressions; compileall, CLI
  version, 126 local links/anchors across 20 Markdown files and diff checks passed.
  Read-only actual-data assembly covered all 15 water GPW profiles with checked
  basis/potential sources and nonlocal-kernel byte hashes; no native execution or
  scientific acceptance/convergence claim. See the
  [capability/dispersion matrix](input-generation.md#non-hybrid-xc-profiles-030).
- User-authorized actual-generator follow-up: **95/95 paired cases** against
  Multiwfn **2026.8.31**, covering all 15 profiles for ENERGY/ENERGY_FORCE/GEO_OPT,
  charged doublets and XYZ periodic water, plus 20 allowed D3/D3(BJ) combinations;
  **79/79 rejection checks** passed without input publication. XC/nonlocal semantics
  and selected H/O basis/potential payloads matched. Original inputs/logs, corrected
  scratch-comparator history and final summaries remain locally under
  `test-workspace/pure-functional-0.3.0-20261020-155629-SwFpIH/` (ignored, not bundled).
  The executed binary is not the 2026.10.1 development source. No CP2K execution,
  scientific/convergence validation or broader element-coverage claim follows.
- At the 0.3.0 checkpoint, hybrids/HFX/ADMM/RI-HFX, UZH-PBE0, GFN-xTB,
  arbitrary mixtures, extra DFT D4 and broader
  meta-GGA task/model combinations remain future work.

### 0.2.9 implemented development scope

- Menu layout v1: compact common shortcuts, unexpanded categories 100-600,
  full IDs for category/direct access, shared semantic state/applicability/editors
  and return context. 500 is output, 600 properties; empty/future menus are hidden.
- Explicit extension-number migration, e.g. old 112 ADDED_MOS -> 341, new 112 U.
  Existing CLI/config/replay names and immutable basis registry v1 are unchanged.
- 602: shared ENERGY GPW whole/A/B density inputs and atom-map CSV; explicit
  fragment charges/spins, charge-conserving complementary partition, original
  relative order and common generated geometry/grid controls. Map magnetic seeds,
  filter per-element requests to included atoms, verify basis/potential sources.
- Exclusive staged bundle publication and optional combined JSON; no existing
  target replacement. Ordinary single-input writer policy remains unchanged.
- Generator-main 0 validates/writes directly; w reviews and confirms. Category/602
  0 returns without writing; successful generation returns without an extra pause.
- Whole-system multiplicity defaults to electron parity after charge (even 1,
  odd 2); explicit values are preserved and fragment states remain explicit.
  This is not a ground-state spin prediction.
- Shared -3/601 cube selector (0 None / 1 Electron density); CDD enables density
  output and blocks disabling it while active. 602 option 4 edits six whole/A/B
  state integers transactionally; option 2 prompts directly for atom indices.
- Automatic TUI output naming follows the source stem with -CDD.inp while CDD is
  active, .inp otherwise; explicit paths win. Default UZH runtime references use
  BASIS_MOLOPT_UZH / POTENTIAL_UZH while provenance retains resolved sources.
- [Numbering/allocation guide](menu-numbering-draft.md) distinguishes this
  implemented subset from provisional unimplemented electronic/property models
  and categories 700-1000. [Workflow guide](input-generation.md) records limitations.
- Historical 0.2.9 validation: **403 tests passed, none skipped**, including menu/workflow
  tests, migrated UI regressions and follow-up parity/cube/naming/navigation cases;
  compileall, CLI version, maintained-text/link and diff checks passed. Synthetic
  generation and PTY/CLI smoke only.
- Actual CUBE grids, CP2K native acceptance/convergence and scientific reference
  fitness remain unverified. No calculations, new dependencies, commit/push or
  publication authorized by input generation.

### 0.2.8 implementation (historical baseline)

Latest retained-version policy supersedes the historical universal grid/OT/hint
defaults below: only effective classic non-SR TZVP/TZV2P/TZV2PX emit NGRIDS 5;
all others omit it (null metadata). OT always emits PP STRICT / AE IRAC in both
legacy AE profiles; explicit overrides win. Numerical profile v4 retains native
GAPW controls. SCF wavefunction and MOTION restart backups are explicitly zero,
without disabling writing. Only generator/Multiwfn opening comments remain;
restart suggestions are metadata/review only, not enabled or emitted directives.
EPS_SCF now defaults to 1e-6 for every task, including ENERGY (previously 5e-6).
Explicit overrides still win; task-dependent EPS_DEFAULT remains unchanged.
Optimization menu 9 / --fixed-atoms adds explicit 1-based fixed-atom selections,
including ranges, with default off. Shared CLI/menu/config/replay handling writes
fractional XYZ constraints only for GEO_OPT/CELL_OPT and target 2026.2. Atom/frame/
expanded-CIF order is explicit; source changes warn without identity remapping.
Malformed/overlapping/active out-of-bounds selections fail before publication;
inactive requests remain compact and hidden. No source constraints are inherited.
CELL_OPT can move fixed fractional positions with the cell. Existing defaults,
protected-result writes and native-validation boundaries are retained.
Historical 0.2.8 validation: **346 tests passed, none skipped**, including 22 fixed-atom
methods and nine latest-policy regressions; compileall, CLI version, documentation links/text and diff checks passed.
No calculations, submissions, new dependencies, publication, commit or push in this round.

### 0.2.7 implementation (historical)

Version 0.2.7 was retained by explicit request, including the D3 filename fix; schema 0.1.0.
D3/D3(BJ) PARAMETER_FILE_NAME now uses literal whole-line serialization instead
of quoted-token output; the input-writing follow-up extends it to basis/potential
filenames. Default output is input-only, JSON is opt-in (132/--write-json).
Existing regular .inp may be atomically replaced; sources/data/symlinks, optional
JSON and all other results remain protected. This fixes
the statically identified blank-prefix path, without claiming native execution.
Historical validation: **315 tests passed, none skipped**, including 22 AE/OT tests,
five filename regressions, 17 input-writing tests and 17 restart/motion tests;
compileall, CLI version, documentation links/text and diff checks passed. All 10
local reference hashes matched in the preceding audit. Default PP physics still
keeps the old method/charge/spin/cutoffs, with an explicitly changed NGRIDS=5;
bytes differ by grid count, basis/potential filename quote removal and inactive
restart hints replacing explicit SCF_GUESS ATOMIC. The isolated-O regression
restores only those known text changes for the historical SHA-256 comparison.
Optimizations now use BFGS/LBFGS TRUST_RADIUS 0.2 angstrom (133), selectable
PDB/XYZ/EXTXYZ trajectories (-5, XYZ default), and MOTION restart backups=0
without disabling restart writing. EXTXYZ is checked only for target 2026.2;
CG hides/retains the radius but never emits it. PROJECT-based restart hints use
.wfn for Gamma, .kp otherwise. Multiwfn's explicit NGRIDS 5 branch applies only
to ibas 3/4/5; the local universal five-grid policy remains a separate user request.
No CP2K/Multiwfn execution, new dependencies, publication, commit or push.
AE choices 50-59 derive GAPW/ALL, core-inclusive electron counts, a disclosed
basis-aware pob IRAC. Numerical profile v3 leaves GAPW split tolerances and
atomic grids to CP2K defaults (no five extra lines); NGRIDS=5 is universal for
PP/AE and SR/non-SR bases. Old profile inputs are not rewritten. OT-only main-menu 110
selects IRAC/STRICT (explicit overrides win); AE-only 131 selects auto/native.
No physical-state repair or native-execution/convergence certification.
Read-only local-data checks cover 332 AE basis/nuclear-potential pairs; local
REVISION git:c92cc08 is not assumed equivalent to upstream v2026.2.
Remaining AE work includes heavy-element/ECP/relativistic protocols, mixed AE/PP,
GAPW density reconstruction/charge analysis, +U and cell/stress/k-point validation.

### Registry follow-up (historical 0.2.6)

Software 0.2.6 was explicitly retained for that round; schema was 0.1.0.
The [registry-v1 basis follow-up](basis-selection.md) adds permanent allocated
numbers, stable string settings/replay IDs, explicit legacy-position migration,
SZV non-SR, paired UZH-PBE DZVP/TZVP/TZV2P, custom pseudopotential ORB 900,
actual alias/payload/q/source checks, cross-KIND shadowing/ambiguity rejection and
per-KIND origin/version metadata. PBE0 IDs 30-32 remain unavailable: no hybrid
method template; reserved/auxiliary/all-electron families are not selectable.
The 71-element fixed-valence policy, charge/spin/U, 400/55 Ry and protected writes
are unchanged. No data yields an explicitly unverified template, not runnable
certification. Software 0.2.6 alone does not distinguish legacy and registry menus;
registry_version=1 does. Analysis/CSV contracts remain unchanged.

Current validation: **254 tests passed, none skipped**, including 38 new registry
methods; compileall, diff, CLI version and local documentation tests passed.
Actual pinned CP2K v2026.2 data were parsed read-only for **213 UZH-PBE pairs**
(3 families x 71 preset elements), with full source hashes and selected-entry/q
checks. This is real-data parsing, **not CP2K execution**. A default synthetic-O
input hash matches the earlier generator at commit 229d09d. No dependencies,
calculations, submissions, package publication, commit or push were performed.

### Initial 0.2.6 GGA/profile round (historical)

See [the changelog](../CHANGELOG.md). That round added native PBEsol/revPBE and Libxc
RPBE, TZVP/TZV2P short-range and TZV2PX MOLOPT families, and explicit element basis
overrides. Tagged v2026.2 header catalogs select actual basis files and fixed-q
potentials. Matched potentials are preferred; unmatched GTH-PBE approximations need
explicit approval. RPBE requires a user target-build Libxc assertion, not probing.
New requests are gated to target 2026.2, not runtime/scientific certification.

The scrolling grouped application menu and single numbered editor introduced in
0.2.4 remain. No alternate screen, redraw or full-screen framework is used. Applicable
fields have fixed numbers, and hidden values remain without implicit resets. Source/
frame controls stay in the header; 0 reviews/generates with confirmation, -10 returns.
Slots 124/125 retain explicit Ueff/L and collinear initial moments for target 2026.2,
including split same-element KIND labels. U values, charge/multiplicity and scientific
defaults are not inferred or changed. No U-value dictionary is implemented.
Menu 128 edits element basis overrides, 129 approves a potential approximation,
and 130 asserts Libxc availability; 129/130 follow functional applicability without
resetting values. New UCL triple-zeta SR families cover 54 current elements and lack
H/C/N/O. Mixed bases must be explicit; q values and source files are never rewritten.
Multiple libraries are checked/hashed separately. Schema 0.1.0 gets additive method,
file-identity and reference metadata; default PBE/DZVP-SR/400-55 Ry is unchanged.

Initial profile-round validation: **216 tests passed, none skipped**; compileall, diff, CLI version,
and local Markdown-link checks passed. Added 23 profile test methods cover fixed-q
family availability, XC definitions, approval/build assertions, actual potential
identities, multi-file name/hash checks, malformed API maps, combined RPBE/+U/AFM/
mixed bases, CLI replay and menu edit/clear/hidden flags. All legacy parser, export,
PTY/navigation, generation, CUBE and collision/rollback tests remain passing.
No Python dependencies were installed; no calculations, submissions or package
publication were performed. RPBE's target CP2K Libxc requirement is not detected or
installed by cp2kkit. Runtime/scientific validation remains pending.

## Recent historical validation

- **0.2.5:** 193 tests passed, none skipped. Fixed ENERGY token boundaries and
  completed ARC-4 shared format recognition, CLI-1 menu routing, ARC-1 shared
  protected export. Remaining architecture review items were explicitly deferred.
- **0.2.4:** 176 tests passed, none skipped. Added scrolling menus, optional Rich
  styling/plain fallback, conditional settings and explicit Ueff/initial magnetism.
  Rich 15.0.0 import/render was verified in the existing environment; ui declares
  rich>=13.7. No real CP2K execution/scientific certification was performed.
- **0.2.3:** 138 tests passed, none skipped. Standardized maintained documentation,
  prompts and project text in English; preserved original quotations/hashes and
  consolidated the standalone MVP into this roadmap. No scientific/default changes.
- **0.2.2:** 134 tests passed, none skipped. Application/editor/submenu text became
  English; numbering/defaults and 0.2.1 formatting stayed intact. Compileall/diff
  checks passed; CLI reported 0.2.2. CP2K was not run.
- **0.2.1:** 132 tests passed. Fixed EPS notation and eight-decimal CELL/COORD;
  generated JSON matches rounded text, originals retain precision, thresholds unchanged.
- **0.2.0:** 128 tests passed. Added package/module/README/changelog/CLI/generator
  version-consistency tests.

All earlier counts below are historical, not current test totals.
The original estimate remains 22 person-days within a 25-person-day budget.
A runnable preliminary implementation **does not equal complete production acceptance**.

## Status

| Feature | Current state | Remaining validation |
|---|---|---|
| CLI/discovery | Implemented, synthetic regression | Real naming patterns, large-file performance |
| Output parser | Common-marker subset | Actual CP2K version matrix/run types |
| Structure export | Strict text subset | Real restart/extXYZ and more legal syntax |
| Quality reports | Conservative evidence rules | Real convergence/failure text and geometry thresholds |
| CSV/JSON | Versions/units/hashes/evidence | Schema freeze and user feedback |
| Plots | Segmented energies/SCF counts | Real restart paths; residual/gradient plots if needed |
| Input generation | GPW/density cubes/CLI/TUI implemented, incomplete | Full Multiwfn generation coverage is the goal; syntax checks through 2026.2, real execution still needed |
| Cube validation/difference | Streaming scalars, strict grids, multi-fragment subtraction/provenance | Real cubes, integration/sampling error; plane averages later |

## Initial implementation validation record

- Python 3.12.14, Matplotlib 3.11.1; no new dependencies installed.
- 41 unittest tests passed, including plotting; no skips.
- Compileall passed for source/tests.
- Subprocess CLI checks passed: help/version/discovery, JSON/CSV, strict report,
  extXYZ, energy/SCF PNG, hashes, overwrite protection.
- CP2K was not run; values were synthetic, not calculation results.
- Wheel/editable installation was not verified. At that stage setuptools was not
  installed; build dependencies were declared and validation used PYTHONPATH=src.

## Priorities

1. Add licensed, distributable, anonymized real output/restart fixtures: normal
   single points, SCF failure/truncation, geometry success/max steps/restarts.
2. Check formats per version and build an evidence-based compatibility matrix.
3. Inspect actual TIMER/force/stress/optimization thresholds before extending parsers.
4. Extend strict restart support using real examples; do not ignore physical settings to read more files.
5. Add CI, multiple Python versions, packaging/install/release checks. The owner decides licensing.
6. Assess streaming large output files and schema compatibility.
7. Extend CP2K generation in stages toward full Multiwfn coverage, recording provenance
   and checking versions/parameter combinations.
8. Develop the parallel [Agent integration and optional MCP track](#planned-agent-integration-and-optional-mcp-support):
   start with stable contracts and a read-only local adapter, then preview/protected
   generation and deployment-specific company integration. These are planned features,
   not existing commands or authorization to execute calculations.

## Review follow-up backlog

These are deferred review recommendations, not implemented features or fixed dates.
In 0.2.5, BUG-1, ARC-4, CLI-1 and ARC-1 are completed with regression coverage.
Keep future rounds small and independently testable; no mass renaming/refactoring.

| Review ID | Deferred work | Constraints and acceptance boundary |
|---|---|---|
| ROB-1 | Improve unsupported-hard-link diagnostics and filesystem-specific tests | Current temporary files are already beside each target; failure cleans up safely and CLI returns I/O code 2. Prefer a clear supported-filesystem error first. Do not automatically copy to final paths without separately evaluating partial visibility, ownership-aware rollback and no-overwrite semantics. |
| ARC-2 | Clarify field/navigation/editor module responsibilities | Keep public run_interactive compatibility while extracting useful shared pieces. Renaming alone is not a priority; ignored bytecode is not a tracked-source defect. Preserve all menu IDs/navigation. |
| ARC-3 | Separate generator validation/resolution, rendering and manifest assembly | Keep generate_input's public signature and one authoritative CLI/TUI implementation. A validated intermediate state should not require text/manifest construction. Preserve physics, effective settings, text hashes, determinism and exclusive writers; compare old/new outputs before migration. |
| PERF-1 | Stream large output/restart reads and discovery | Preserve full-byte SHA-256, strict UTF-8, evidence line numbers, segmentation and malformed/truncated-record handling. Discovery must scan the whole file for multiple project names, not inspect only the header. Retain read_text for full-text consumers. |
| MNT-1 | Consider smaller CubeReader header/interpretation units when needed | Preserve bounded streaming, explicit unit/meaning assertions and source identity checks. Exhaustive semantics tests should precede extraction; no inference from magnitudes/charges. |
| MNT-2 | Share only truly common numeric conversion primitives | structure_formats already reuses structure.floats. Preserve context-specific errors, integer rules, Fortran exponents, finite checks and CIF uncertainty handling; avoid a permissive universal parser. |
| MNT-3 | Revisit structured settings/models only when semantic consumers require them | Intentionally defer dataclass/settings redesign. Keep original strings/evidence and null distinct from zero; do not normalize or merge physical settings implicitly. |
| PKG-1 | Add lightweight CI, optional lint/type checks and packaging metadata/checks | Keep unittest/compileall, standard-library core and optional Rich/plotting isolation. Add only verified links/authorship; the owner decides licensing and unresolved upstream terms remain explicit. No package release is implied. |
| TEST-1 | Expand bounded/property-style edge-case matrices incrementally | Use unittest loops/deterministic cases without new mandatory dependencies. Extend filesystem errors, parser segmentation and generator combinations; build on existing collision/race/inode-aware rollback tests rather than claiming these are absent. |

Hard-link portability is a compatibility enhancement, not evidence that current
rollback overwrites files. Refactoring is not automatically low-risk where physical
settings, provenance, or write safety are involved. No plugin/configuration engine,
mandatory UI dependency, relaxed quality rule or parallel CLI/TUI generator is planned.

## UZH protocol follow-up: modc.py reference

The original 0.2.6 planning below is retained for provenance. The registry-v1
follow-up now implements paired UZH-PBE selections, audited over all 71 current
preset elements; UZH-PBE0/hybrid templates remain unimplemented. See
[basis selection](basis-selection.md) for current scope and permanent numbers. User-provided `test-workspace/modc.py` was inspected read-only (SHA-256
`b37f4c2cb1b7051f6fd4d3a19cd00dbb511f9aca355e0fb936f3d033362e7dbd`),
not executed, copied, modified or committed. No redistribution authorization for
that user script is inferred. It demonstrates preserving q while selecting UZH
basis/potential libraries, but string renaming alone is not protocol verification.

Confirmed tagged v2026.2 header examples include H/C/O/Fe
TZVP-MOLOPT-PBE-GTH-q1/q4/q6/q16 and TZV2P equivalents with corresponding
POTENTIAL_UZH GTH-PBE aliases. This is representative header evidence, not complete
coverage or CP2K execution. Future protocol implementation must audit every enabled
pair and retain library identity even when aliases match an older library.

- [BASIS_MOLOPT_UZH_2026.2](https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/BASIS_MOLOPT_UZH_2026.2),
  SHA-256 `8ca617142cc73b02e47d5806d97e91d2c3312444c411c5a093f4dfe8fb9355c4`.
- [POTENTIAL_UZH_2026.2](https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/POTENTIAL_UZH_2026.2),
  SHA-256 `8ab49093391f67f2705679f0b3bfc5b84bbeb4003955b556ded322e9d1d6093d`.

Do not port the script's in-place overwrite default, forced EPS_SCF/cutoff resets,
order-dependent KIND rewriting or substring replacements. In particular, switching
BASIS_MOLOPT without reliably replacing GTH_POTENTIALS can mix protocols, and a
BASIS_MOLOPT prefix substitution can produce an invalid UZH_UCL filename. Quoted
paths, units, numeric exponents and basis roles require structured handling.
A future UZH feature should be an explicit paired profile in the protected generator,
not a general overwrite-based regex migration. r2SCAN and hybrids/HF/ADMM remain
separate later stages; arbitrary q changes require their own charge/spin review.

## Input generation: incomplete by design

**Goal: cover all Multiwfn CP2K input-generation functionality.** Current generation
is a GPW subset with electron/applicable spin density, not a completed full port.
The initial baseline is user-provided Multiwfn 2026.10.1 cp2kmate.f90.
Record versions/hashes/new or changed branches for subsequent references.
The goal is useful capability coverage, not line-by-line copying, preserving every
old default, or emitting target-version-unsupported keywords without checking.

### Staged extensions

1. **Defaults/behavior:** verify differences, solvers, WAVELET box shapes, low-dimensional
   vacuum, centering, cell repetition, external structures, configuration.
2. **KIND/spin/constraints:** explicit element/atom magnetic guesses and Ueff/L
   are implemented for target 2026.2. Remaining: arbitrary independent KIND/basis/
   potential controls, richer +U projectors/occupations, CDFT, atom freezing,
   cell constraints, anisotropic pressure, and actual magnetic-state validation.
3. **Methods/bases:** 0.2.6 adds PBEsol/revPBE/RPBE and explicit catalog-backed
   MOLOPT/UCL mixed bases; the registry follow-up adds UZH-PBE pairs and custom ORB.
   Version 0.3.0 adds the non-hybrid registry and complete nonlocal methods;
   0.3.1 adds the bounded GFN-xTB branch; 0.3.2 adds the first three direct-HFX hybrids;
   initial GAPW/all-electron bases were added in 0.2.7. Remaining: broader meta-GGA
   model/task support, native/scientific UZH validation, UZH-PBE0,
   broader HFX/ADMM combinations, RI-HFX, additional auxiliary and all-electron bases/families/
   q policies, correlated wavefunctions, semiempirical/force fields and SCF options.
4. **Tasks:** frequencies/vibrations/Raman, MD, dimer TS, BAND/NEB, NMR, polarizability,
   BSSE, real-time electrons, PIMD, XAS, appropriate TDDFT.
5. **Environment/outputs:** SCCS, fields, surface dipole correction, trajectory/restart
   printing, cube/Molden, charges, orbitals/matrices, cutoff/k-point convergence templates.

### Acceptance and provenance

- Track upstream options/branches as implemented, partial, missing, or version-inapplicable.
- Register source/version/file/subroutine/hash, usage/differences/citations/permission
  for each module in [provenance](../third_party/multiwfn/PROVENANCE.md).
- Diagnose incompatible combinations without silently repairing physics.
- Add synthetic tests, representative input comparisons, and authorized actual execution
  per stage. Syntax acceptance is not scientific appropriateness.
- Preserve complete input/settings/units/source/protection. Never run/submit automatically.
- Full coverage is a goal, not completion, extra permission, or certification.
  Check terms and licenses before publication/relicensing/paid distribution.

### Initial GPW subset validation

See [input-generation scope](input-generation.md). Added generation without changing
analysis. Tests covered defaults/tasks/section balance/geometry/PBC/spin/electrons/
dispersion/SCF/k-points/local data headers/hashes/CLI/protection.

- 58 tests passed (41 previous + 17 generator tests), none skipped.
- Compileall/diff checks passed.
- Subprocess checks covered all four tasks, JSON/input hashes/citations, collision refusal, help.
- No new dependencies or CP2K execution; synthetic numbers were not scientific results.
- Terms/provenance/papers recorded in [notices](../THIRD_PARTY_NOTICES.md), not evidence
  of separate permission or settled relicensing boundaries.

Actual CP2K syntax execution and system-specific convergence remain necessary.

## Completed stage: density cubes and subtraction

- Added electron/applicable UKS spin switches, three-direction STRIDE, final-step policy.
- Syntax checks through **2026.2**, default target 2026.2; tagged definitions inspected
  for 2024.1/2/3, 2025.1/2, 2026.1/2, without whole-program certification.
- Added bounded streaming cube-check/cube-diff, unit/meaning evidence, nonorthogonal
  integrals, normalized-grid tolerance, multiple fragments, staged exclusive publication/rollback.
- Unknown scalars are not electron counts; atom fields do not imply valence counts;
  electron/spin differences remain separate and integrals are not fragment net transfer.
- Scope excludes Bader/interpolation/registration/plane averaging/DOS/bands/submission.
  Plane averaging awaits an explicit separate request.
- Retained 58 tests and added independent hand-derived density/cube cases:
  **92 passed**, no skips; compile/diff/local-link checks passed.
- Subprocess checks covered four task outputs, AB/A/B check/subtract/reread, hashes,
  protection/help. Streaming smoke: 120000 constant samples (~2.78 MB), Python
  tracemalloc peak ~11.4 KB for that case only, not a general performance guarantee.
- No new dependencies or CP2K installation/execution. No usable real cubes in tests/
  authorized test-workspace at implementation time; no real-cube regression.
  Official source checks and synthetic evidence remain distinct.
- Details in [cube guide](cube.md)/[schema](schema.md); Multiwfn references recorded.

## Completed stage: input editor

- Retained parameter CLI; added --tui/--interactive, seeded by arguments.
  Bare generation in a terminal can open the editor; non-TTY scripts stay noninteractive.
- Standard-library editor covers all InputSettings with grouped revisits, units,
  complete previews, quoted replay commands, default-no confirmation.
- Local range/type vs shared scientific validation; invalid drafts remain editable
  without automatic charge/spin/SCF/PBC/k-point changes.
- Existing writer/manifest/schema/protection reused; no shell/CP2K/Multiwfn execution.
  UI references registered separately, not a full upstream-menu port.
- Added 19 tests: **111 passed**, none skipped. Covered mode equivalence, seeds/edits,
  previews/cancel, conflicts/manual fixes, collisions, EOF/Ctrl-C, non-TTY refusal,
  actual POSIX PTY subprocess sessions. Compile/diff/link checks passed.
- No new dependencies or actual CP2K certification.

## Completed stage: application menu and structure formats

- Bare/path invocations open the application menu; select current-directory files
  or paths. Generate/cancel returns to it. Batch commands retained.
- Strict standard-library GJF/COM, CIF (explicit symmetry/P1), VASP5 POSCAR/CONTCAR;
  reject occupancy/disorder/incomplete/unsupported data. Record constraints/source
  without inheriting calculation settings.
- PROJECT from filename; 400/55 Ry; OT 25/20, diag 128; automatic smearing empty
  orbitals max(30,NINT(natoms/2)), override allowed; explicit UKS spin values.
- Pressure only CELL_OPT, padding only NONE, OT hides/rejects smearing/nonzero empty orbitals.
- **125 tests passed**, none skipped; compile/diff passed. Real POSIX PTY smoke:
  load CIF -> generate -> application menu -> exit.
- No new dependencies or CP2K/Multiwfn runs; no convergence/runtime certification.
  Format restrictions/provenance updated.

Deferred Bader/multi-directory/NEB-DOS post-processing/submission remain outside scope.
BAND/NEB goals above concern input generation only, not post-processing/submission systems.

## Original MVP planning baseline

This historical section replaces the retired standalone early-development document;
it is not the current feature list. Goal: connect result reading and traceable analysis.
Weights were user value 40, frequency 20, foundations/enabling value 15, ease 25.
Six selected modules totaled 22 person-days against 25 budgeted. Estimates excluded
learning/waiting/review; prerequisite closure was complete.

| Feature | Priority | Difficulty | Days | Prerequisite |
|---|---:|---:|---:|---|
| CLI/project discovery | 87 | 2/5 | 3 | None |
| Output parser | 90 | 3/5 | 6 | CLI/discovery |
| Structure/cell export | 92 | 2/5 | 4 | CLI/discovery |
| Convergence/quality | 92 | 2/5 | 3 | Parser |
| CSV/JSON/provenance | 87 | 2/5 | 3 | Parser |
| Energy/convergence plots | 77 | 2/5 | 3 | Parser and exports |

Original acceptance/dependencies:
- CLI: deterministic valid/missing/multiple-project handling, help/exit codes; Python/filesystem.
- Parser: normal/truncated/unconverged regression, units/source/defined compatibility;
  Python and actual CP2K output examples.
- Structures: matching counts/coordinates/cells, explicit unknown XYZ PBC, no silent
  cell loss; restart/XYZ and optional ASE were initial candidates (ASE is not required now).
- Quality: separate electronic/geometry assessment, no success for unfinished jobs,
  evidence links; rules/parser.
- Exports: versioned schema, units, missing vs zero, deterministic repeated results;
  standard library.
- Plots: explicit axes/units, correct restart/reset handling, matching exported data;
  Matplotlib.

Initially deferred: multi-directory summaries, cube checks, Multiwfn batches/logs,
Bader/transfer, density differences, plane averages/cumulative integrals, PDOS,
bands, adsorption/reaction tables, AIMD thermodynamics/trajectories, RDF/MSD/coordination,
orbital/real-space entry points, analysis input fragments, reproducible reports.
Some later additions are documented above; the original deferral is not current status.

Original boundaries: independent CP2K/Multiwfn installations, evidence-based version
claims, units/settings/source on every result, no invalid data promoted to science,
physicochemical judgment not replaced by automation, read-only analysis/no auto-submission.
