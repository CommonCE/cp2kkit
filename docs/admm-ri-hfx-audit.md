# ADMM + RI-HFX Read-Only Audit and Implementation Handoff

## Status and scope

This document records a read-only audit of the current cp2kkit combination gate,
local CP2K reference source, and Multiwfn input generation. It is a development
handoff, not a claim of implemented support, native execution, convergence,
accuracy, or speedup. Recheck current repository state before implementing.

No code was changed, no tests or CP2K calculations were run, and no jobs were
submitted during the audit. The worktree was clean at the beginning and end of
the audit. Documentation added afterwards does not change that validation status.

## Reference identity

- CP2K local reference root: `/home/xwp/soft/cp2k-2026.2`.
- Its `REVISION` file reads `git:c92cc08`; this is a local reference identity,
  not verification of an upstream release tag or installed binary.
- Multiwfn local reference:
  `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`, subroutine `outCP2Kinp`.
- These external paths are development locators, not runtime dependencies.
- Existing reference terms and provenance remain applicable:
  [third-party notices](../THIRD_PARTY_NOTICES.md),
  [Multiwfn terms](../third_party/multiwfn/TERMS.md), and
  [provenance](../third_party/multiwfn/PROVENANCE.md).

SHA-256 identities checked during the audit:

| Local reference file | SHA-256 |
|---|---|
| Multiwfn `cp2kmate.f90` | `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402` |
| CP2K `src/cp_control_utils.F` | `da04a34bb800c6ccc9314a9e434abca7b0f1482a250f1672bb0cd27adff6aa39` |
| CP2K `src/qs_environment.F` | `51acf59832239e5610dcb8b3c7117d1311f42d5eb5beb39400591b724ed5e777` |
| CP2K `src/hfx_admm_utils.F` | `41bdcc775ad8a7461d9f811a8058434195da7004135651d7308fe27b5bb0c0ed` |
| CP2K `src/input_cp2k_dft.F` | `93887178d0208020a96826b794459bac9937a66cec8ff6a69b7d4e1d393d5648` |

Target-version manual pages opened during the audit:

- [HFX with ADMM](https://manual.cp2k.org/cp2k-2026_2-branch/methods/dft/hartree-fock/admm.html)
- [Gamma RI-HFX](https://manual.cp2k.org/cp2k-2026_2-branch/methods/dft/hartree-fock/ri_gamma.html)

Branch documentation can change. Source locators and hashes above identify the
local bytes inspected; they do not certify the online branch or executable.

## Verified findings

### 1. ADMMS changes the ADMM model

`src/cp_control_utils.F`, approximately lines 306–345, expands named ADMM types.
The `admms_type` case sets:

| Effective setting | Existing cp2kkit ADMM | CP2K ADMMS |
|---|---|---|
| Method | BASIS_PROJECTION | CHARGE_CONSTRAINED_PROJECTION |
| Purification | OT auto: MO_DIAG; diagonalization auto: NONE | NONE |
| Exchange scaling | NONE | MERLOT |

CP2K reads the correction functional separately. It also warns about explicit
projection/purification/scaling settings overwritten by a named ADMM type.

Consequently, enabling RI must not silently change existing ADMM into ADMMS.
Appending `ADMM_TYPE ADMMS` to the current explicit ADMM block is not a safe
implementation strategy.

### 2. RI-HFX does not require ADMMS

The target-version Gamma RI-HFX guide explicitly supports combining ADMM and
RI-HFX and includes an ADMMS example. Independently, the local regression input
`tests/QS/regtest-hfx-ri/CH3-ADMM.inp` combines:

- BASIS_PROJECTION;
- MO_DIAG purification and OT;
- PBE-based 25% HFX;
- non-periodic conditions;
- AUTO_BASIS RI_HFX and an HF/RI section.

It is registered in that directory's `TEST_FILES.toml`. This is evidence of an
upstream regression case, not evidence that it was run in this audit. It uses
limited SCF iterations and IGNORE_CONVERGENCE_FAILURE, so it must not be copied
as a production convergence policy. It is also open-shell and is not an exact
fixture for the proposed closed-shell minimum below.

The local `tests/QS/regtest-admm-type/H2O-ADMMS-HYB.inp` separately exercises the
ADMMS shortcut, but is not itself an RI combination case. Do not conflate these
two source examples.

### 3. The automatically generated RI basis changes parent space

`src/qs_environment.F`, approximately lines 1371–1388, constructs a missing
RI_HFX basis as follows:

- without ADMM: default orbital parent;
- with ADMM: `create_ri_aux_basis_set(..., basis_type="AUX_FIT", ...)`.

cp2kkit's current `resolve_ri_hfx` hardcodes `basis_parent_role='ORB'`.
Combination support must instead record AUX_FIT and retain traceability to the
actual resolved auxiliary basis identity. Checking ORB files alone does not
check the RI parent in combination mode. The generated RI coefficients remain
CP2K runtime output, not validated generator data.

### 4. DEFAULT correction has source support for the proposed PBE0 scope

`src/hfx_admm_utils.F`, subroutine `create_admm_xc_section`, reads the actual HF
operator and fraction. The DEFAULT/full-Coulomb branch constructs a PBE exchange
correction using the HF fraction. Short-range and truncated operators have
separate branches.

This supports retaining `EXCH_CORRECTION_FUNC DEFAULT` for an initial isolated
PBE0/full-Coulomb scope. It is not numerical validation of a chosen ORB/AUX_FIT
pair. Do not expand this finding into an audit of other functionals or all
operator/variant combinations.

### 5. Multiwfn generates input; CP2K performs the calculation

In the inspected `outCP2Kinp`:

- method names containing ADMM trigger AUX_FIT and ADMM-section output;
- the pseudopotential branch chooses admm-dzp-qN and BASIS_ADMM_UZH;
- an independent `iRIHFX` flag emits AUTO_BASIS RI_HFX MEDIUM and SORT_BASIS EXP;
- ADMM together with RI selects ADMM_TYPE ADMMS;
- ordinary ADMM without RI selects BASIS_PROJECTION with solver/task-dependent
  purification.

Relevant approximate source ranges: 936–990 (chooser), 1543–1548 (AUX_FIT),
1704–1726 (libraries/auto basis), 1962–1988 (ADMM), 2168–2240 (HF/RI).
Multiwfn's combination choice is a reference policy, not proof that ADMMS is
mandatory or optimal. No Fortran or basis payload needs to be bundled.

## Recommended staged implementation

### Stage 1: ordinary ADMM + RI-HFX

Proposed first supported intersection:

- target CP2K 2026.2;
- PBE0, GPW, Gamma;
- isolated PERIODIC NONE;
- closed-shell RKS, OT, ENERGY;
- existing supported classic orbital basis families and checked actual ORB and
  AUX_FIT data; retain all existing data/potential/electron-count protections;
- existing BASIS_PROJECTION ADMM and existing purification semantics;
- RI_METRIC HFX with AUTO_BASIS RI_HFX, now derived from AUX_FIT;
- existing RI size/filter/batching controls, subject to current validation;
- no new physical defaults or automatic changes to charge, spin, solver or cell.

This is a deliberately bounded generator policy, not a CP2K-wide restriction or
an already validated capability. Explicit incompatible requests must fail rather
than be ignored or repaired. Exclude CDD bundles in the first implementation
unless separately reviewed: ENERGY/RKS on the whole system does not guarantee
those conditions for its fragments. Preserve independent-mode CDD behavior.

Do not add ADMMS in this stage. Keeping the ADMM model fixed makes comparison
with the existing ADMM path easier to interpret.

### Stage 2: explicit ADMMS selection

Add a separately selected variant only after Stage 1 integration. Keep old
configuration meaning and default behavior. Resolve and record effective method,
purification, exchange scaling and correction. Reject incompatible retained
purification requests, particularly MO_DIAG, rather than rely on native override.
Exact new field/CLI names remain a design decision; they were not implemented or
verified by this audit.

## Current implementation touchpoints

Line numbers are navigation aids and may move.

| Path | Required consideration |
|---|---|
| `src/cp2kkit/ri_hfx.py` | Replace unconditional combination rejection (about lines 55–56) with bounded policy; fix parent role/identity, warnings and capabilities |
| `src/cp2kkit/admm.py` | Preserve Stage 1 model/output; remove inaccurate no-RI warning in combination mode; variant support is Stage 2 |
| `src/cp2kkit/inputgen.py` | Validation around 320–321; AUX resolution around 450; RI resolution around 492; pass resolved parent information rather than infer its data identity |
| `src/cp2kkit/hybrid.py` | Preserve HF operator/fraction, resource handling, data protection and truthful warnings |
| `src/cp2kkit/input_tui.py` | Review text and truthful effective model display; current scaling text is hardcoded NONE |
| `src/cp2kkit/input_editor.py` | RI editor currently says no ADMM combination; keep inactive-control handling explicit |
| `src/cp2kkit/cli.py` | Update bounded help; no new ADMMS option in Stage 1 |
| `src/cp2kkit/menu_registry.py` | Keep stable menu IDs 121/122/223; do not renumber |
| `src/cp2kkit/density_workflow.py` | Existing whole/fragment checks compare AUX_FIT, ADMM and HFX identity; enforce initial combination CDD exclusion explicitly |
| `tests/test_ri_hfx.py`, `tests/test_admm.py` | Add combination fixtures and checks; preserve independent-mode coverage |

The existing resolution order already resolves AUX_FIT before RI. Reuse that
information and existing parsers/provenance instead of introducing duplicate
basis parsing. `InputSettings.from_config` and manifest replay are part of the
public contract and need coverage.

## Software acceptance checklist for Stage 1

- Supported combination emits exactly one ADMM block and one HF/RI block with
  correct nesting; it does not emit ADMMS or direct-only HF/MEMORY.
- ADMM projection, purification, correction and HF/XC identity remain consistent
  with the equivalent existing ADMM calculation.
- RI parent role is AUX_FIT and parent identity is tied to resolved data.
- Generated RI coefficients and physical basis pairing remain explicitly
  unvalidated; no native/build/runtime certification is introduced.
- Opening controls in either order yields equivalent effective settings.
- Unsupported functional, spin/magnetism, PBC, solver, task, metric and CDD
  combinations fail before publication; retain all existing general gates.
- Existing invalid/unknown/non-finite and inactive-control behavior remains strict.
- Configuration and generated-manifest replay preserve effective identity.
- Direct, independent ADMM and independent RI paths retain behavior except for
  intentionally documented capability descriptions.
- File collision, protected source paths, publication rollback and no-submission
  guarantees remain intact.
- Add focused synthetic and CLI/TUI tests, then relevant regression checks.
  Synthetic fixtures do not certify CP2K compatibility.

## Remaining validation and authorization boundaries

No native syntax check, binary feature check, SCF convergence check, numerical
comparison, force validation or performance benchmark was performed. Tests were
not run because this stage only inspected files and documentation.

Actual validation later requires explicit calculation authorization and new run
paths. Compare direct HFX, existing ADMM, independent RI-HFX and the combination
with the same physical setup. To isolate RI error, compare the combination with
ADMM; to measure total approximation error, compare with direct HFX. Treat
unconverged results and unknown timing/memory as such, never as successful or zero.
Check process exit status and stderr as well as convergence and termination text.

Do not widen Stage 1 to HSE06, periodic systems, UKS, diagonalization, forces,
optimization, k-points, stress, smearing, +U, GAPW or correlated methods merely
because broader paths exist in CP2K. Those are separate generator audits.

See the [next-session implementation prompt](../.agents/prompts/implement-admm-ri-hfx.md).
