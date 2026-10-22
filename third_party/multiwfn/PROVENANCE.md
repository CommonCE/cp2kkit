# Multiwfn module provenance

This records facts, not permission inferred from labels such as "reference-based"
or "rewritten in another language". Prefer version/file/subroutine/SHA-256;
line numbers are auxiliary. Do not invent upstream commits, inspection dates, or grants.

## ADMM emitted-library correction and executable comparison (0.3.4, version retained)

The fix retains software version 0.3.4 by explicit user request. The comparison
below was executed before that request with temporary version 0.3.5; historical
inputs, manifests, logs and evidence-directory names are preserved unchanged.

- Fix only the local inputgen.py portable-filename predicate: an auxiliary-only
  file has no orbital records and must not qualify through an empty all().
  Resolved AUX_FIT source paths are now emitted; actual UZH orbital aliases,
  physical parameters, data bytes and the existing upstream assembly are unchanged.
- User-authorized fresh executable comparison: cp2kkit 0.3.5 against actual
  Multiwfn **2026.10.18** (banner checked per paired process), not the development
  source version 2026.10.1. Binary/source/helper hashes and local CP2K reference
  revision are recorded in test-workspace/admm-0.3.5-fix-e7UQQm/identity.json.
- 56 fresh real-data cases passed with --data-dir and no explicit --basis-file
  workaround: 32 paired water cases for PBE0/HSE06, NONE/XYZ, OT/diag,
  ENERGY/ENERGY_FORCE/GEO_OPT and charged doublets; plus 24 cp2kkit-only cases
  for admm-dz/tzp/tz2p. The paired default auxiliary is admm-dzp. Checks cover
  emitted auxiliary-library identity, ORB/AUX/potential numerical signatures/q,
  projection/purification, HF fraction/operator/omega/radius and coordinates.
- This is not byte identity: Multiwfn omits scaling/correction where inspected
  CP2K 2026.2 defaults are NONE/DEFAULT; existing resource/screening/restart
  differences remain. No CP2K was executed, no jobs submitted, no convergence,
  energy/force accuracy, speedup or scientific validation established.
- Local evidence: test-workspace/admm-0.3.5-fix-e7UQQm/summary.json,
  per-case inputs/logs/diffs/results, red.log, focused.log and regression.log.
  Earlier failing outputs under admm-0.3.4-comparison-9LH4xs are preserved.
  No additional upstream code, permission or changed licensing is implied;
  the references, required citations and authorization limits below still apply.

## PBE0/HSE06 ADMM and auxiliary-basis infrastructure (0.3.4)

- Local: admm.py, auxiliary_basis.py, shared cp2k_data.py Gaussian-role validation,
  inputgen.py, CLI/TUI/editor, density_workflow.py and data_catalog.py source
  identity. No coefficients, potential parameters or Fortran are bundled.
- Reference: Multiwfn **2026.10.1**, cp2kmate.f90/outCP2Kinp, development locator
  ../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90; SHA-256
  f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402.
  Inspected per-KIND AUX_FIT/q branches around 1543-1548, BASIS_ADMM_UZH file
  inclusion around 1705, and projection/solver-dependent purification around
  1962-1988. These are reference-based Python assemblies, not clean-room claims.
- Retained organization: pseudopotential admm-dzp-qN, DFT-level ADMM section,
  BASIS_PROJECTION, OT MO_DIAG / diagonalization NONE. This iteration adds
  independently numbered admm-dz/dzp/tzp/tz2p choices and actual-data resolution.
  It does not port Multiwfn's GAPW, RI-HFX/ADMMS, TDDFT, XAS or other-hybrid ADMM.
- Differences: explicit opt-in rather than method-name suffix; separate AUX_FIT
  registry and file overrides; exact element/q/payload checks, final ORB/AUX
  file-union alias checks, source hashes/protection, config/replay and CDD locks.
  Explicit EXCH_SCALING_MODEL NONE and EXCH_CORRECTION_FUNC DEFAULT retain
  operator-consistent native correction rather than forcing PBEX universally.
  Existing HFX resources/screening and physical defaults remain unchanged.
- Inspected local CP2K reference: /home/xwp/soft/cp2k-2026.2, REVISION
  **git:c92cc08**, target keyword policy 2026.2. Directory/branch names do not
  establish an unmodified official tag or a linked binary. Exact source hashes:
  - input_cp2k_dft.F:
    93887178d0208020a96826b794459bac9937a66cec8ff6a69b7d4e1d393d5648
  - cp_control_utils.F:
    da04a34bb800c6ccc9314a9e434abca7b0f1482a250f1672bb0cd27adff6aa39
  - hfx_admm_utils.F:
    41bdcc775ad8a7461d9f811a8058434195da7004135651d7308fe27b5bb0c0ed
  - admm_methods.F:
    0a72a5ad6fa9a7398b3a9c8d828c241f32fb7198bbf8d6a90c5e642cc7595317
  - data/BASIS_ADMM_UZH:
    3f08699fd16a79e116de65f7520db362f71468657ab5e1c90c735fa4930393c1
- cp_control_utils.F checks MO-based purification requires OT. admm_methods.F
  supports force paths for BASIS_PROJECTION with MO_DIAG or NONE.
  hfx_admm_utils.F DEFAULT correction follows full Coulomb/PBE, short-range/
  matching XWPBE, or truncated/PBE_HOLE_T_C_LR plus XWPBE and inherits the
  HF fraction, omega and cutoff. These are inspected paths, not numerical tests.
  Target-2026.2 [ADMM guide](https://manual.cp2k.org/cp2k-2026_2-branch/methods/dft/hartree-fock/admm.html)
  and [keyword reference](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/AUXILIARY_DENSITY_MATRIX_METHOD.html)
  were also inspected; the guide's ADMMS/PBEX example is not this chosen profile.
- Local data-only audit: 284 registered auxiliary entries inspected, 282
  structurally accepted. Ca admm-dz-q10 (entry line 1356) and admm-dzp-q10
  (1370) are rejected: the p-shell descriptor specifies one contraction while
  rows contain an exponent and two coefficients. No values are dropped or data
  modified. Native CP2K handling of the extra values is unverified. Only selected
  entries are validated, so other elements and Ca TZP/TZ2P are not blocked solely
  by these entries. No automatic auxiliary-family substitution.
- 32 water generator cases (PBE0/HSE06, OT/diag, NONE/XYZ, four auxiliary sizes)
  passed using actual local data. Local ignored evidence:
  test-workspace/admm-0.3.4-data-audit-TSjzozqx/ (audit.py, preserved first-pass
  script/log, completed.log and completed/summary.json plus inputs/sidecars).
  This is not a fresh executable Multiwfn comparison or any CP2K execution.
  Synthetic tests separately cover malformed/conflicting sources, state gates,
  replay/TUI/CDD and overwrite protections; no energy, force accuracy, speedup,
  convergence, native acceptance or scientific-validity claim.
- Authorization/citations: reference use does not expand upstream permission.
  No separate author grant is recorded; existing custom terms and required
  Lu/Chen 2012 and Lu 2024 citations remain. No license or paid-distribution
  permission is inferred.

## Remaining direct-HFX profiles (0.3.3)

- Local: functional_registry.py, hybrid.py resolve_functional, method_profiles.py,
  inputgen.py and shared CLI/TUI/editor/config/replay. Append chooser 19/20/21
  for BHANDHLYP/M06-2X/PBEH without changing prior IDs or basis numbers.
- Rechecked Multiwfn **2026.10.1**, cp2kmate.f90/outCP2Kinp, development locator
  ../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90; SHA-256
  f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402.
  Actual references: menu/fraction prompt 933-1000, potential default 1557-1572,
  PBEh/BHandHLYP/M06-2X XC definitions 2047-2090 and HF fractions 2179-2184.
  Reference-based Python assembly; no Fortran port/payload is distributed.
- BHandHLYP uses HYB_GGA_XC_BHANDHLYP plus explicit HF=0.50; M06-2X uses
  HYB_MGGA_X_M06_2X + MGGA_C_M06_2X plus HF=0.54. Both require a user Libxc
  build assertion. Libxc already includes the semilocal mixing: no additional
  0.50/0.46 XC scaling. M06-2X records kinetic-energy density and grid warnings.
- Local Libxc **7.0.0** under the supplied CP2K tree tools/toolchain/build:
  src/hyb_gga_xc_b1wc.c defines BHandHLYP B88/LYP with half-exchange parameter,
  distinct from BHandH/BHLYP; SHA-256
  2d5929a4d5ef090cdaecae29bb6ccc5177f7677c8d4f894630aa5347c6188948.
  src/hyb_mgga_x_m05.c defines M06-2X with intrinsic semilocal mixing and 0.54
  exact exchange; SHA-256
  eaf08381d7f16370a46bced3bdf449a663aa089b263264bafcf749814bd387b5.
  src/mgga_c_m06l.c defines MGGA_C_M06_2X; SHA-256
  c02a638cc808d14798afaed2d706eaef00415cd5ac43830d7f89986deb8dc45a.
  No Libxc implementation/parameter arrays are bundled.
- Additional official v2026.2 raw-source hashes rechecked against local bytes:
  xc/xc_libxc.F
  5c7d6d9e1aa6664297e761407530fb1eb5057db87bb38876920f0cedb9ef5e45;
  xc/xc_libxc_wrap.F
  fc0eb02140f09001de9ca35c69589ddefe4ffcf2d84f3fe359d97e6deb0ee40b.
  libxc_add_sections registers named components; RKS/UKS info/derivative paths
  treat HYB_MGGA as tau-dependent. They do not replace the explicit HF section.
  These tagged URLs/hashes join existing HFX source metadata.
  Target-version manual subsection URLs returned 404; the older 2023.2
  HYB_MGGA_X_M06_2X manual was only a cross-check, not the target-version contract.
- PBEh differs from upstream's percentage prompt: explicit dimensionless
  --pbeh-fraction in (0,1], no default; use PBE for zero HF. Derive PBE
  SCALE_X=1-A, SCALE_C=1.0 and HF=A together, without upstream five-decimal
  output truncation. Non-null fractions on other methods fail until reset.
- Preserve target-2026.2 classic GPW/Gamma/NONE-or-XYZ direct-HFX task/solver
  scope and protected writers. Prefer actual matched potentials; otherwise
  all three use GTH-PBE per the upstream default branch, with approximation
  warnings, fixed q and existing source identities. No UZH-PBE0/ADMM/RI-HFX.
- Dispersion differs conservatively from upstream's unrestricted menu: M06-2X
  permits only none/D3; emit REFERENCE_FUNCTIONAL M062X, the exact key in the
  previously hashed qs_dispersion_utils.F zero-damping table. No BJ entry.
  PBEh has no universal fixed-fraction parameters; BHandHLYP's potential BHLYP
  alias identity is not assumed. Both currently allow only none. Existing
  PBE0/HSE06/B3LYP dispersion policies are unchanged.
- Both required Multiwfn papers remain in input/JSON headers. Existing custom
  [terms](TERMS.md), absent separate grants and licensing limitations remain.
  Method references: Libxc's Becke 1993/ Gaussian implementation reference for
  BHandHLYP and Zhao/Truhlar 2008 M06 suite reference. No clean-room, relicensing,
  paid-distribution, native compatibility or full-Multiwfn-parity claim.
- Initial implementation validation: synthetic coefficients/nesting, bounded and inactive fraction
  requests, Libxc assertions, periodic operators, tasks/solvers/spin, CLI/TUI/
  replay/config, CDD identity and protected publication; read-only source hashes.
  No CP2K, Multiwfn or Libxc execution, native input acceptance, convergence,
  derivative accuracy or scientific property validation in this round.

### User-authorized 0.3.3 generator comparison

- Version explicitly designated **0.3.3**, replacing the preliminary unreleased
  0.4.0 assignment. Historical test artifacts were not relabeled or overwritten.
- Fresh cp2kkit 0.3.3 and actual Multiwfn **2026.10.18** binary (banner checked
  in all 64 paired runs), at one Multiwfn thread each. This is not execution
  of the referenced 2026.10.1 development source; binary/source/settings hashes
  are recorded independently.
- Local ignored evidence directory:
  `test-workspace/hybrid-remaining-0.3.3-20261022-125352-T48M5s/`.
  identity.json records binary/settings/source/data/fixture/Python identities;
  case-matrix.json, summary.json/csv, matrix-results.json and per-case comparison.json
  preserve the complete matrix. Four earlier pilot pairs and their initial
  mismatch are retained separately, excluded from 64-pair counts.
- H/O water geometry fixtures, DZVP-MOLOPT-SR-GTH, q1/q6 GTH-PBE; target 2026.2,
  CUTOFF/REL_CUTOFF 400/55 Ry. All three profiles: NONE/XYZ, ENERGY/ENERGY_FORCE/
  GEO_OPT with OT/diag, q=0/multiplicity=1 or q=+1/multiplicity=2 UKS and skew
  XYZ cell. M06-2X D3 covers NONE/XYZ; PBEh additionally covers explicit fractions
  0.01/0.25/0.50/0.75/1.0 and a high-precision fraction.
- All **128 generator processes exited 0**. **62/64 pairs match under documented
  policies**; no unknown discrepancies. BHandHLYP 17/17, M06-2X 17/19, PBEh 28/28.
  Both remaining cases are M06-2X-D3: Multiwfn emits
  `REFERENCE_FUNCTIONAL M06-2X`, cp2kkit emits `M062X`.
  The hashed CP2K 2026.2 qs_dispersion_utils.F qs_scaling_dftd3 uppercases the
  explicit reference without removing hyphens and has CASE("M062X"), not
  CASE("M06-2X"). Preserve this mismatch, not an unverified alias equivalence.
  CP2K was not executed to demonstrate runtime behavior.
- All other checked XC/HF coefficients/components, selected numerical basis/
  potential payloads/q, geometry/cell/PBC, tasks/spin/solver/grid and cp2kkit
  manifest-version/family/approximation settings pass in 64/64. Full inputs are
  not byte-identical. EPS_SCF, initial-P screening, per-rank HF memory and radius
  precision retain the earlier documented local policies.
- PBEh uses fraction versus upstream percent, explicit SCALE_C=1 versus the
  checked CP2K default=1 when omitted. CP2K input_cp2k_xc.F 855-862 verifies
  SCALE_X/C defaults. The high-precision request 0.123456789012345 produces
  upstream HF=0.12346 / PBE exchange=0.87654 versus cp2kkit's preserved fraction
  and complementary exchange. This is documented rounding, not exact method
  parameter identity; the comparison explicitly uses upstream print resolution.
- **48/48 fresh negative CLI checks passed**, including absent Libxc assertion,
  absent/invalid/inactive PBEh fractions, unsupported scope/dispersion and bad HF
  controls. Existing sentinel inputs remained unchanged; no JSON sidecars created.
  **117 focused / 479 full regression tests passed**, with no skips; compileall,
  version, link/file and diff checks are separate software checks.
- Each generator ran in a fresh directory with 15 s wall / 10 s CPU, 4 GiB
  address-space and 8 MiB per-output-file limits. Full argv/stdin/stdout/stderr/
  exit/timing records and input diffs are retained. No data file, generated
  input or binary modification was needed to obtain these results.
- This establishes bounded real-generator/data comparison, not native CP2K/Libxc
  evaluation, syntax acceptance, convergence, force accuracy or scientific
  validation. No calculation/submission, licensing grant or full-Multiwfn-parity
  claim. Existing custom terms and both required papers remain unchanged.

## Direct-HFX hybrid implementation (0.3.2)

### Fixed source and actual reference use

- Local modules: functional_registry.py native XC/HF definitions; method_profiles.py
  scope checks; hybrid.py direct-HFX controls/operator/radius/resources/data references;
  inputgen.py orchestration/render/metadata; CLI/TUI/editor/menu 120 integration.
- Multiwfn **2026.10.1**, supplied cp2kmate.f90, subroutine outCP2Kinp;
  development locator ../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90 (not a runtime
  dependency). Rechecked raw SHA-256:
  f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402.
- Inspected native PBE0/B3LYP/HSE XC branches around 2039-2126, face-spacing/
  truncation and HF/RI assembly around 2153-2240, and dispersion around 2329-2392.
  Reference-based Python assembly, not a claim of clean-room work or a complete port.
- PBE0: PBE SCALE_X=0.75, SCALE_C=1.0 and HF=0.25.
  HSE06: XWPBE SCALE_X=-0.25, SCALE_X0=1.0, OMEGA=0.11 plus full PBE correlation;
  SHORTRANGE HF=0.25, OMEGA=0.11 bohr^-1.
  B3LYP: LYP=0.81, BECKE88=0.72, VWN3=0.19, XALPHA=0.08, HF=0.20.
  Explicit VWN3 retains the upstream Gaussian convention, not CP2K's native
  shortcut VWN5. These are method definitions, not arbitrary input fragments.

### CP2K tagged-source audit

Inspected official v2026.2 sources at
https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/src/ :

| File | SHA-256 | Use |
|---|---|---|
| input_cp2k_xc.F | 332cda33e1d90c5e3002fcc1e965633d009f28caadbc98c188474cd26e314e3b | Native XC keywords, scaling, VWN3 and XWPBE definitions |
| input_cp2k_check.F | e1f26b06bbc6121a31f9c50c4056dbe43f08a328425c46010566b4e6555ccb5d | Native B3LYP shortcut explicitly uses VWN5, hence not reused |
| input_cp2k_hfx.F | 468ef8c01d0285e2341617d9df269dd3eb227c7006da14937f17acad2db7177f | HF fraction, operators, cutoff angstrom, initial-P screening, memory MiB/MPI process, storage |
| xc/xc_xwpbe.F | 652ef1c975b9533e8c4fe1e1d0e43d39887e715e3c0c9496f871924033261dda | Short-range/original-hole scaling, omega and RKS/UKS derivative paths |
| xc/xc_vwn.F | 788ec05f5f5283b70d8e1b9e6bcf50c2d6989b2ccf7a20b70ac34c39d7ef3803 | VWN3/VWN5 and spin implementations |
| hfx_derivatives.F | 52961d2ffba8baabbe44a05b77a410a1e95f19fb943ec46e8363ac97bc004967 | Direct four-center derivative path, not numerical force validation |
| qs_dispersion_utils.F | 587b8b35f0fadba226335ec4b45b5290260ea05c67eb8b77b8ec1511ba4bd337 | PBE0/HSE06/B3LYP D3 and D3(BJ) reference-name whitelist |

Source hashes also accompany generated HFX metadata. Manual checks covered
XC_FUNCTIONAL and HF/INTERACTION_POTENTIAL on the cp2k-2026_2-branch.
Static source identity does not certify an installed executable or backend.

### Local policy differences and scope

- Target 2026.2 GPW classic MOLOPT/UCL Gamma NONE/XYZ ENERGY/ENERGY_FORCE/GEO_OPT;
  RKS/UKS and OT/diag without smearing or +U. No GAPW, CELL_OPT, non-Gamma,
  low-dimensional PBC, ADMM/RI-HFX, custom or UZH-PBE0 basis protocols.
  Existing GPW density/CDD and protected single/bundle writers are reused.
- Isolated global hybrids explicitly use COULOMB. Periodic global hybrids use
  TRUNCATED, auto min(6 angstrom, minimum cell face spacing/2.01), referencing
  upstream but bounding against the cell actually emitted at eight decimal places.
  Explicit radii must stay strictly below half the minimum face spacing.
  No clipping, cell/model/solver replacement or automatic physical fallback.
- HSE06 emits SHORTRANGE, OMEGA=0.11, and omits CUTOFF_RADIUS; CP2K derives the
  short-range numerical cutoff from omega/EPS_SCHWARZ.
- EPS_SCHWARZ=1e-6 and EPS_STORAGE_SCALING=0.1 reference upstream; explicit
  SCREEN_ON_INITIAL_P=F avoids upstream's restart-dependent T. MAX_MEMORY=512
  MiB per MPI process follows the checked CP2K native default, not upstream 3000.
  All three numerical controls have shared CLI/config/TUI replay; no arbitrary
  HF fraction/omega or implicit resource request is introduced.
- Truncated-gamma t_c_g.dat is only referenced, never bundled. Supplied data
  directory requires a read-only byte/hash check and protected absolute path;
  otherwise emit its runtime basename with an unchecked-data warning. T_C_G_DATA
  uses default_c_val (char_t), so paths with spaces are quoted, unlike CP2K's
  whole-line lchar_t basis/kernel filenames.
- Existing matched potential/data/q resolution is preserved. The family-potential
  follow-up (version 0.3.2 retained by explicit user request) corrects the initial
  generic PBE-approval policy: prefer actual exact-hybrid entries; otherwise
  automatically select BLYP for B3LYP and PBE for PBE0/HSE06.
  Reference: same fixed cp2kmate.f90/outCP2Kinp, lines 1557-1572 (B3LYP/BLYP
  branch and default PBE). Actual local Multiwfn 2026.10.18 generation also
  emitted GTH-BLYP for B3LYP; binary and development-source versions differ.
  Record semilocal-family approximation status without claiming exact-hybrid
  matching or user approval. Required family/q absence fails, with no cross-family
  substitution or invented labels. This user-directed policy needs no additional
  numerical payload; existing terms/citations and validation limits remain.
  UZH-PBE0 30-32 remain unavailable pending a distinct paired-data/protocol audit.

### Citations, authorization and validation boundary

Generated input headers and JSON retain both required Multiwfn papers. The
[recorded custom terms](TERMS.md) and absence of separate author permission are
unchanged. No Fortran, Libxc implementation, basis coefficients, pseudopotential
parameters, D3 data or truncated-gamma numerical table is bundled.
No new clean-room, relicensing, paid-distribution or whole-project compatibility
claim is made. Method references remain those of the upstream XC/HFX sources.

Synthetic tests cover complete coefficients/sections/units, operator/radius bounds
including skew cells, invalid combinations, deterministic replay, CLI/TUI, spin/
density/CDD and protected publication. Source/byte checks establish neither native
syntax acceptance nor convergence, derivative accuracy or property correctness.
Fresh local B3LYP generator comparison against Multiwfn 2026.10.18 passed 21/21
cases, including selected basis/potential payload checks; documented screening,
memory and SCF policy differences remain. Local evidence: test-workspace/
b3lyp-0.3.2-retest-20261022-114046-bWjbx5/summary.json (not a distributed fixture).
No CP2K execution or submission was performed for this feature.

## GFN-xTB implementation (0.3.1)

The initial audit below describes the first 2026.2-only implementation. The
compatibility/OT follow-up below supersedes its diag-only/version policy, not
its historical source identity or validation evidence.

- Local: xtb.py model registry/counts/native parameter-byte identities and rendering;
  inputgen.py dispatch/shared geometry/motion/writer; CLI/TUI/editor/menu registry;
  tests/test_xtb.py synthetic fixtures. No external calculation executable is used.
- Rechecked source: Multiwfn 2026.10.1, supplied
  `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`, outCP2Kinp, SHA-256
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
  Actual references: chooser 952 and mapping 1034-1036 (30 GFN1 / 31 GFN0 /
  32 GFN2); QS/XTB 1815-1841 (native 1/0, TBLITE GFN2 for 2026.2);
  omission of basis/potential/XC/grid 1511/1688/1992/2403;
  non-SCC GFN0 and semiempirical OT preconditioning 2432-2505.
- Reference-based Python assembly, not clean-room or a full Fortran port.
  Differences: preserve existing DFT chooser positions/global function/basis IDs;
  separate method state, explicit diag requirement for GFN2 and tblite assertion,
  native tblite SCC AUTO/ACCURACY rather than copying upstream direct-P mixing;
  no automatic solver change, no CHECK_ATOMIC_CHARGES F, no periodic/open-shell/
  CELL_OPT/density/CDD/+U/refits, no extra dispersion, no direct writes or restart
  reads. Retain local EPS_SCF 1e-6 policy for self-consistent profiles. Shared
  geometry/motion/writer and explicit conflicting-request errors remain authoritative.
- CP2K evidence: supplied `/home/xwp/soft/cp2k-2026.2`, REVISION git:c92cc08.
  This is the actual local tree identity, not inferred official-release/binary
  equivalence. Inspected source SHA-256:
  - src/input_cp2k_tb.F (create_xtb_section, create_xtb_parameter_section,
    create_xtb_tblite_section): backend/model/mixer/ACCURACY/char_t path definitions,
    `695ae4fc6f92b20c5cfbb10f0619fd35ffd2c9f2d58aee6dd3f8760c19ea5c7a`.
  - src/cp_control_utils.F: model parameter filenames, native dispersion choices
    and SCC routing,
    `da04a34bb800c6ccc9314a9e434abca7b0f1482a250f1672bb0cd27adff6aa39`.
  - src/xtb_parameters.F: H-Rn zval/reference occupation sums,
    `2c270f3fa0157a0dc9ee1a24857847028fd55ad6ce4f7d9855762f78e20b7b4c`.
  - src/qs_force.F: native/tblite calculate_forces paths at 294-299,
    `ad1c3faee83409cf39913fd8935dac537e77c02b9799ae22ca1de0fca5a4bff0`.
  - src/tblite_interface.F: linked-backend/force interfaces,
    `ffc8387c8d1b7a71dd8710a30443200e799846532a9147dd6cb4b8466d60b374`.
  - src/qs_dispersion_d4.F: compile-time native D4 dependency and missing-build abort,
    `3699c01defd8dd4c13cb57542a04eda0c832a2276af2e5d75e31115de4038097`.
- tblite reference only: supplied CP2K toolchain build/tblite-0.6.0/
  src/tblite/xtb/gfn2.f90 reference_occ sums, SHA-256
  `ad3809ccfe5dde50890ea8e8f365de2541db0c2e27338a29bb812cf0709c7a8a`.
  No coefficients are copied. Backend version in generated manifests stays null;
  this reference does not establish the user's linked library version.
- Header/count/file-byte evidence only; native CP2K data files are not bundled:
  data/xTB0_parameters SHA-256
  `278461cabbf89b14379aedc78ef3e141c8cef1f911f3a3c72530aec7a52b6d34`;
  data/xTB1_parameters
  `81a9d7afdee31f5d8fd67a4d8ec966179317c7b100261c9c82d724bafb460399`;
  data/dftd3.dat
  `4aa1e246a1661bb875590a67229cbc0747e9ad5e11ec1b8e47bce30db866dd1d`.
  Supplying data_dir checks these identities and protects source files; it does
  not validate scientific suitability or permit parameter refits.
- Target-version manuals rechecked:
  [xTB tutorial](https://manual.cp2k.org/cp2k-2026_2-branch/methods/semiempiricals/xtb.html),
  [XTB](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/QS/XTB.html),
  [TBLITE](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/QS/XTB/TBLITE.html).
  Preserve their method references, including Grimme2017/GFN1 and
  Bannwarth2019/GFN2; native parameter-file original DOI headers stay upstream.
- Existing Multiwfn author/copyright/custom terms and both 2012/2024 papers remain
  in code/generated headers/manifests/notices. No separate grant, relicensing,
  paid-distribution authorization or whole-project compatibility is inferred.
- Validation boundary: synthetic model/task/count/nesting/CLI/TUI/config/replay/
  geometry/protection checks; synthetic parameter fixtures patch only expected
  hashes to exercise plumbing. No CP2K/Multiwfn/tblite execution or native syntax/
  convergence/scientific-equivalence claim. Source derivative paths do not prove
  force accuracy or optimized structures. Read-only source comparison confirmed
  all 86 electron counts against both native zval and tblite reference_occ sums,
  and both native parameter files contain H-Rn entries. Read-only water assembly
  checked native GFN0/GFN1/D3 bytes; GFN2 built-ins remain backend_unchecked.
  DFT input text matched the pre-change Python generator in 45/45 water profile/
  task cases. These comparisons are not native calculations.

### GFN-xTB compatibility and OT follow-up (retained 0.3.1)

- User-requested target range: CP2K 2024.2 through 2026.2. Keep the explicitly
  selected software version 0.3.1 within this uncommitted feature round.
  Local xtb_versions.py/xtb.py now use a tagged-source capability/data registry,
  not a version-string-only acceptance change.
- Actual inspected tags: v2024.2, v2024.3, v2025.1, v2025.2, v2026.1, v2026.2.
  Fixed locator pattern:
  `https://raw.githubusercontent.com/cp2k/cp2k/v<VERSION>/<FILE>`.
  [xtb_versions.py](../../src/cp2kkit/xtb_versions.py) SOURCE_FILES/SOURCE_HASHES
  records exact per-tag bytes for input_cp2k_tb.F, cp_control_utils.F,
  xtb_parameters.F, qs_force.F, input_cp2k_scf.F, input_cp2k_constraints.F,
  input_cp2k_motion_print.F and start/input_cp2k_motion.F; supported tblite
  tags also record tblite_ks_matrix.F and qs_scf_initialization.F.
  Generated metadata records these actual tagged URLs/hashes, not guessed manual
  addresses or detected binary identities.
- Native GFN1 is available across all six tags. 2024.x has no GFN_TYPE keyword
  and uses xTB_parameters. Native GFN0 first appears in the checked v2025.1
  tag with GFN_TYPE 0/xTB0_parameters; GFN1 then uses xTB1_parameters.
  v2025.2 is the first checked tag with TBLITE, activated by a logical section
  parameter (T), METHOD GFN2. It has no GFN_TYPE TBLITE, SCC_MIXER or ACCURACY;
  v2026.1 retains this contract. v2026.2 has the explicit TBLITE backend enum
  and the newer mixer/accuracy interface. Missing upstream methods fail with
  minimum-version diagnostics, never fall back to another GFN model.
- Source input-definition hashes, in target order:
  - 2024.2/2024.3:
    `852f5a1c2d0bb569cb329d80a84c1078af159d60a1dee12361436c521ab44744`.
  - 2025.1:
    `02c4769530ae03ac9595a6521b2eba5da94ceafdbd3618a219d3a956bc004465`.
  - 2025.2:
    `892d4b40cf8a6e4b053f3be0883f15624f9c9d8943939b0242074b5f9f84a76d`.
  - 2026.1:
    `e2d7616e33160e117946c39ecc17c30d3099875e51ed30a0dd390b78ffed72e8`.
  - 2026.2:
    `695ae4fc6f92b20c5cfbb10f0619fd35ffd2c9f2d58aee6dd3f8760c19ea5c7a`.
- Tagged native data identities: 2024.2/2024.3 data/xTB_parameters SHA-256
  `d9f11fa6411d203135d88a21178f8a87353449dc3d151b42ce9727054dc8fa45`.
  xTB0/1 parameter hashes for 2025.1-2026.2 match the initial audit above.
  data/dftd3.dat for 2024.2-2026.1:
  `1f5041914fb3a7fa6c97602d82da6cb9129c1c1dba675db23522de9c2837dafd`,
  different from the already recorded 2026.2 hash. No file renaming, payload
  copying or automatic data replacement. All six native zval tables agree
  for H-Rn; this is not proof of identical method energies across releases.
- Same rehashed Multiwfn 2026.10.1 source/hash as the initial audit.
  Reinspected outCP2Kinp 79 (initial idiagOT=1/diag, iouterSCF=1),
  1034-1042 (GFN1 at Gamma switches to OT, not every GFN method;
  GFN2 changes mixing but can retain prior solver state),
  1815-1841 (backend selection), 2432-2505 (non-SCC GFN0, OT preconditioner,
  inner/outer limits, explicit STRICT and legacy GFN2 direct-P/alpha 0.2).
  GFN1 default OT/FULL_SINGLE_INVERSE/DIIS/STRICT and 25/20 agree;
  local ordinary ENERGY EPS_SCF stays 1e-6 versus upstream 5e-6.
  Local atomic-charge sanity checks remain enabled instead of copying GFN1's F.
- Historical policy, superseded for legacy targets by the crash-protection
  follow-up below: remove the initial local GFN2 diag-only gate. Tagged tblite_ks_matrix.F
  on v2025.2/v2026.1/v2026.2 includes the MO derivative path for Gamma OT.
  v2026.2 qs_scf_initialization.F 963-967 explicitly describes OT at Gamma
  without smearing, with SCC variables updated from OT density and SCC_MIXER
  ignored (SHA-256
  `cf50756a032cde1389b7e80f06cb8d500a38c4eaabe001fbea7f1ab3d82407e7`).
  Emit no SCC mixer for OT: EPS_SCF controls convergence. 2026.2 ACCURACY then
  controls numerical setup only; with diag/native SCC it also controls SCC
  convergence. Legacy GFN2 diag uses CP2K direct-P mixing, alpha 0.2.
  Default OT and explicit diag are preserved, with no automatic state repair.
- Shared fixed-atom resolver accepts an evidenced target reference for xTB;
  tagged constraints retain fractional XYZ/repeatable LIST on all six releases.
  Default DFT gate is unchanged. Tagged trajectory definitions contain EXTXYZ
  starting at v2026.1, so older requests fail explicitly. Geometry/motion/writer
  reuse, citations, no-refit policy and other bounded physical scope remain.
- Manuals opened as cross-checks:
  [2024.2 XTB](https://manual.cp2k.org/cp2k-2024_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/QS/XTB.html),
  [2025.2 XTB](https://manual.cp2k.org/cp2k-2025_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/QS/XTB.html),
  [2026.1 TBLITE](https://manual.cp2k.org/cp2k-2026_1-branch/CP2K_INPUT/FORCE_EVAL/DFT/QS/XTB/TBLITE.html).
  Tagged source is the version contract, not the manuals' master-branch edit links.
- Validation: 39 read-only real-data model/version/task assemblies passed
  (ENERGY/ENERGY_FORCE/GEO_OPT for each available pair); no output inputs or
  calculations were run. Source/data/hash checks are separate from synthetic
  CLI/menu/config/replay/negative/protection regressions. CP2K/Multiwfn/tblite
  were not executed. No native acceptance, convergence, optimization or scientific
  validation is claimed. Existing custom terms/citations/unknown grants remain;
  no bundled Fortran/parameter payload or additional licensing grant.

### GFN2 OT native crash-protection follow-up (retained 0.3.1)

- Local changes: xtb_versions.py gfn2_ot_enabled generation-policy flag and shared
  xtb.py validation. GFN2 OT is enabled only for target 2026.2; legacy
  2025.2/2026.1 requires explicitly selected diagonalization. Do not silently
  replace OT, change the target or infer installed-build capabilities. The
  2025.2 gate is conservative; no native 2025.2 failure is claimed.
- Earlier authorized local diagnostics: CP2K 2026.1/git:5e54ba2, water charge 0,
  multiplicity 1, Gamma/no smearing. Default OT at one rank and IRAC at four ranks
  crashed with SIGSEGV/139, consistent with the previous default four-rank run.
  Diagonalization ENERGY at one/four ranks, ENERGY_FORCE and GEO_OPT converged.
  Local 2026.2/git:c92cc08 OT passed that four-case task/rank matrix. Different
  compilers/backends and absent source Git metadata prevent claims of official
  unmodified-release equivalence or isolation of a single upstream fix.
- Inspected local 2026.1 source: qs_scf_initialization.F 420-425 and 721-727
  nullifies mixing storage under OT; qs_scf.F 526-529 calls tb_update_charges
  with use_rho=false; tblite_interface.F 939-949 reads p_mix_new before the
  ao_charges call at 981, matching mulliken.F:776 in the crash backtrace.
  Local qs_scf.F SHA-256:
  `a1076210b6e8497ac51e4e759cd8c2ed14283cb609fb7b7cb1c6c69e3130ab23`;
  local tblite_interface.F SHA-256:
  `6520c7a9ee5a3ff2d0a0969d9cdd96f60f333d6dff93a9a9376c6aeab6c23337`.
  Local 2026.2 qs_scf.F 553-562 instead selects use_rho=true for OT, SHA-256:
  `ec0540cec56c37f47eadaf14c9672c26bd059921609f2190538e2a2a4a384d7b`.
  These are local-source identities, not the tagged hashes above; no debugger
  pointer-state measurement or patched-binary experiment was performed.
- Complete diagnostic inputs/logs, build/library identities and source excerpts
  are local under `test-workspace/gfn2-ot-diagnosis-20261021-124634-mJ9t2F/`,
  not bundled test fixtures. The current guard adds synthetic regression only;
  no new native calculation, source patch, parameter payload or Fortran port.
  Existing citations/custom terms/unknown grants remain unchanged.

## Non-hybrid XC implementation (0.3.0)

- Local: functional_registry.py shared definitions/aliases; method_profiles.py,
  basis_registry/resolution and data_catalog.py matching; inputgen.py XC/kernel
  assembly/provenance; CLI/TUI/config/replay adapters; density_workflow.py
  nonlocal-identity lock. Fifteen profiles, no hybrid/HFX/ADMM or xTB implementation.
- Reference: Multiwfn 2026.10.1, cp2kmate.f90, outCP2Kinp; actual rechecked SHA-256
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
  Menu/mapping 933-1056, native/Libxc XC 1991-2150, nonlocal/dispersion 2329-2392.
  Actual use: PADE/BP shortcut meanings; exact TPSS/revTPSS/SCAN/r2SCAN/MN15-L/
  HLE17/B97M component names; B97M-rV RVV10 b/C=6.0/0.01 and kernel;
  BEEFVDW + LMKLL/kernel; retain original parametrized-PBE/RPBE definitions.
- Independently checked supplied CP2K tree `/home/xwp/soft/cp2k-2026.2`,
  REVISION git:c92cc08. Directory identity is not binary-version certification.
  input_cp2k_xc.F verifies keywords/nesting/units; input_cp2k_check.F 207-233
  expands BEEFVDW into BEEF exchange, 0.3998335231 PBEc + 0.6001664769
  **Libxc LDA_C_PW**, and LMKLL. The native shortcut therefore requires a
  Libxc-build assertion. Its raw SHA-256
  `e1f26b06bbc6121a31f9c50c4056dbe43f08a328425c46010566b4e6555ccb5d`
  also matches fetched tagged v2026.2 bytes; reference URL/hash is in data_catalog.py.
  Existing catalog hashes match the inspected input/XC wrapper/D3/GTH files.
- Read-only GTH_POTENTIALS header/payload checks derive PADE/BP coverage; hash
  `5a9bfbc3b37a55917ade4fb704b80546d210d843759b94e3915e74acfc3fafb2`.
  At unchanged fixed-q policy: 71 PADE and 41 BP matches. BP86 -> GTH-BP is an
  explicit mapping, not a new potential. Absent matches require explicit PBE
  approval. UZH-PBE remains PBE-only; no q/model change or implicit fallback.
- Local Libxc 7.0.0 source under CP2K tools/toolchain/build: src/mgga_xc_b97mv.c
  confirms b=6.0/C=0.01 and tau dependence, hash
  `7e3e897a94bd2b15e34d34924275954836d35a6f58d0979b71f017c88426d673`;
  src/mgga_xc_hle17.c confirms the combined 1.25/0.5 TPSS definition, hash
  `e333f01d054adc1521320b509ceb7898a83bd76e64b034b73ad23cded55e6035`.
  No Libxc C implementation or numerical parameter arrays are bundled.
- Inspected local kernel hashes: rVV10_kernel_table.dat
  `7468a396e8f4dd3ff6492db92f200f174df73305c7a3baa85c2117c4122dddb4`;
  vdW_kernel_table.dat
  `d26887fb29a104edd03fa85a1d073a380a56fa1680b76eacf7b2c0e86d53a6fd`.
  Runtime users' bytes are hashed separately; neither matching hash nor readable
  source bytes establish numerical kernel fitness. No kernel is distributed.
- Differences: curated dispersion whitelist follows the actual CP2K zero/BJ
  tables, not every upstream menu combination. No automatic SCAN grid/potential,
  solver, spin or basis resets. Meta-GGA/nonlocal initial scope is GPW Gamma
  ENERGY/ENERGY_FORCE/GEO_OPT without +U; GAPW/non-Gamma/CELL_OPT/+U await
  separate validation. Preserve 400/55 Ry defaults with convergence warnings.
  No extra DFT-D on intrinsic nonlocal methods; none means no extra pair term.
  Kernel/source protection and whole/A/B identity checks reuse local writers.
- Existing 2012/2024 citations remain in input/JSON and notices; custom
  [terms](TERMS.md), absent separate permission and licensing limits are unchanged.
  Reference-based Python assembly is not a clean-room or whole-port claim.
- Validation: synthetic XC/coefficient/nesting, alias/build/potential gates,
  capability/dispersion matrix, CLI/TUI/config/replay, CDD identity and protected
  publication tests; source/data parsing and hashes only. Actual-data, in-memory
  water assemblies covered all 15 profiles (neutral, multiplicity 1, GPW,
  DZVP-MOLOPT-SR-GTH, fixed q; matched or explicitly approved PBE potentials,
  no additional pair dispersion). Nonlocal kernels were read/hashed only.
  This initial implementation audit did not execute CP2K/Multiwfn; it established
  no native acceptance, convergence, forces/stress accuracy or property validation.

### User-authorized generator comparison follow-up

- Actual executable `/home/xwp/soft/multiwfn/Multiwfn` reported **2026.8.31**
  in all 95 paired runs; this is not execution of the 2026.10.1 reference source.
  cp2kkit 0.3.0 was invoked through the configured Python module entry point;
  both generators exited 0 for every paired case, at one Multiwfn thread each.
- All 15 profiles: ENERGY, ENERGY_FORCE and GEO_OPT input generation, charge +1 /
  multiplicity 2 / UKS, and XYZ periodic water; 20 additional allowed D3/D3(BJ)
  combinations. H/O DZVP-MOLOPT-SR-GTH, q1/q6, neutral singlet or charged doublet,
  Gamma/OT, CUTOFF/REL_CUTOFF 400/55 Ry. No electronic calculation was executed.
- 95/95 final semantic comparisons and 79/79 negative CLI checks passed;
  selected H/O basis/potential numerical payloads matched across POTENTIAL and
  GTH_POTENTIALS despite generic versus explicit-q aliases. B97M-rV b/C and
  required nonlocal kernels matched. Ordinary ENERGY EPS_SCF differs by retained
  policy (cp2kkit 1e-6 vs this binary's 5e-6), not an input-assembly defect.
- Local ignored evidence directory:
  `test-workspace/pure-functional-0.3.0-20261020-155629-SwFpIH/`.
  identity.json records actual binary/source/settings/data hashes;
  summary-v4.json/csv and negative-summary.json/csv are final results.
  Original generated inputs, stdin, full logs, exit/timing records, earlier
  scratch-parser corrections and final file hashes are retained, not distributed.
- No production source or original generated input needed modification. Corrected
  only the scratch comparator's .inp dispatch, ORB role and lone-UKS semantics;
  reanalysis reused the same preserved inputs. Full regression: 430 passed,
  none skipped. This checks generators and selected data, not CP2K acceptance,
  numerical kernel evaluation, convergence or property correctness. No new grant,
  clean-room, version-equivalence or whole-project license claim.

## Functional and GFN-xTB planning reinspection (planning-stage 0.3.x)

- Historical planning inspection: [functional/method proposal](../../docs/functional-roadmap-0.3.md).
  This historical planning-stage note predates the implemented non-hybrid/xTB
  and first three direct-HFX features registered above.
  This planning note itself adds no copied Fortran or calculation result.
- Reinspected local Multiwfn 2026.10.1, `cp2kmate.f90`, `outCP2Kinp`;
  development locator `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`.
  Actual SHA-256 recheck matches the original baseline:
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Actual reference scope: method menu/mapping (approximately 933-1056),
  xTB selection (1815-1841), ADMM/XC (1964-2150), HF/RI (2168-2240),
  dispersion/name mapping/nonlocal kernels (2329-2392). File/hash/subroutine
  identify the source; these line locators are auxiliary.
- Use upstream coverage and complete XC/HF/dispersion definitions as the primary
  development reference, not a new independent functional shortlist. The inspected
  menu has 21 DFT selections excluding double hybrids/correlated methods and
  ADMM variants; PBEh is one configurable family. GFN0/1
  native and GFN2/tblite agree with the user's requested series mapping.
- Planned differences: preserve local stable IDs, semantic APIs, explicit
  compatibility/data checks, non-destructive writers and retained defaults.
  Target-version syntax, coefficients/units, basis/potential pairing, auxiliary
  data and correction combinations still require individual audits. No blanket
  migration of restart/sanity-check/solver/resource policies is authorized.
- MP2/RPA/GW, double hybrids, PM6/DFTB/FIST remain later scopes, despite appearing
  in the same upstream menu. Static inspection is not runtime equivalence,
  convergence or scientific validation. Multiwfn/CP2K were not executed here.
- Existing custom terms, both required papers and unknown authorization boundaries
  remain unchanged. No clean-room, relicensing or separate-permission claim.

## Numbered cube selector and CDD linkage (retained 0.2.9)

- Inspected Multiwfn 2026.9.20 `cp2kmate.f90`, -3 selection branch at lines
  816-841; SHA-256:
  `1a4bfe0a49df6ac4950e48e35b4efef00aa489f2469a917830fb47f746dd4d18`.
- Reference: numbered cube-output selection, specifically 0 None and 1 electron
  density with spin density for unrestricted calculations. Local Python menu
  implements only these existing output types; other upstream types are omitted.
  No new Fortran implementation or CP2K keyword template was copied.
- CDD auto-enable/disable guard is local UI orchestration using existing density
  generation. Existing citations/terms apply; no new permission is claimed and
  no CP2K runtime validation is implied.

## Categorized menus and two-fragment density inputs (0.2.9)

- Local modules: menu_registry.py, input_editor.py, input_tui.py,
  density_workflow.py, inputgen.py and shared bounded selections in constraints.py.
- Function-category/full-ID allocation and compact main-menu design follow the
  user-discussed local plan, not a VASPKIT code port or copied menu registry.
  Common corresponding Multiwfn-style shortcuts remain; historical local 100+
  extension IDs undergo an explicit migration. Immutable basis registry v1 and
  atom indices are independent namespaces. This is menu layout v1.
- No new upstream Fortran/keyword template or parameter payload is bundled.
  Existing generation and density-print references/citations below remain in use;
  category navigation and bundle orchestration reuse those existing generators.
  No newly inspected external algorithm/source or new permission is claimed.
- 602 defines complementary whole-system atom subsets with explicit fragment
  charges/multiplicities, source/frame mapping, charge conservation and parity
  checks. Resolve whole geometry once; preserve subsets without centering or
  ghosts, map explicit magnetic atom seeds, and inherit corresponding element
  basis/potential/U settings. Selected data-source identities must match.
- The common NGRIDS lock is a local workflow policy: if whole-system effective
  basis policy selects five grids, fragments inherit five even where their subset
  alone would omit the keyword. Ordinary generation policy is unchanged. Requested
  matching grid controls do not certify actual produced CUBE grids.
- Reuse exclusive staged publication for three inputs and an atom-map CSV, optional
  combined JSON, without extending ordinary single-input replacement permission.
  No CP2K/Multiwfn execution, automatic subtraction, spin-density workflow,
  convergence or physical-reference validation. Synthetic tests are not native
  acceptance evidence.
- Existing required 2012/2024 papers remain in generated headers/manifests and
  notices. Authorization status and custom terms are unchanged; this work grants
  no separate relicensing or paid-distribution permission.

## CP2K input generation

### Location and fixed source

- Local module: `src/cp2kkit/inputgen.py`
- Interfaces: InputSettings, generate_input, write_input
- CLI: `src/cp2kkit/cli.py`, generate-input
- Upstream: Multiwfn 2026.10.1
- Package: Multiwfn_2026.10.1_src_Linux
- User-provided local path: `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`
  (development locator, not runtime dependency)
- File: cp2kmate.f90
- Main subroutine: outCP2Kinp, lines 68-3448
- Related inspection: outCP2Kinp_wrapper, determine_vacuumsize
- SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`
- Provenance/hash review (UTC): 2026-10-13
- Applicable terms: [TERMS.md](TERMS.md)

### Actual references

- Tasks and GLOBAL/FORCE_EVAL/DFT/SUBSYS/MOTION organization.
- MOLOPT-GTH names and selected Nval valence-count entries.
- PBE/BLYP GTH potentials and D3/D3(BJ) configuration.
- Some grid/SCF/optimization defaults; not every default is identical.
- Density extension inspected E_DENSITY_CUBE/STRIDE 1 branches, lines 2599-2641,
  retaining both citations. Spin applicability, final-step frequencies, and file
  behavior were separately checked against CP2K 2024.1-2026.2 documentation/source:
  [cube guide](../../docs/cube.md). cube.py streaming/difference logic was not ported
  from Multiwfn's cube implementation.

### Implementation and differences

- Python GPW subset, not a line-by-line port or strict clean-room implementation.
  Original Fortran is not distributed.
- Only ENERGY/ENERGY_FORCE/GEO_OPT/CELL_OPT, PBE/BLYP, restricted MOLOPT presets.
- Element/basis/potential names separately checked against CP2K headers; optional
  local data verification/hashing.
- Conservative PBC/electron/combination checks; exclusive creation/JSON provenance.
- OT inner/outer limits follow upstream's enabled-outer branch, 25/20, enabled by
  default locally. Smearing empty-orbital auto uses max(30,NINT(ncenter/2)), not fixed 20.
  Optimization steps, low-dimensional Poisson, and cell construction still differ.
- Restart settings are not inherited; rebuild KIND by element.
- Detailed differences belong in development conversation, not a separate comparison
  document. Actual scope: [generation guide](../../docs/input-generation.md).

### Citations and authorization

- Required papers: [notices](../../THIRD_PARTY_NOTICES.md).
- Preserved in module docstrings, generated inputs, and JSON.
- No separate header copyright/license statement was found in the inspected
  cp2kmate.f90; absence is not evidence of no copyright.
- No separate integration permission; relicensing/paid-distribution boundaries unconfirmed.
- Python implementation does not automatically remove upstream conditions.

### Validation boundary

- Synthetic unit/CLI smoke checks, no CP2K execution.
- Comparison is static inspection of identified source, not equivalent output/
  calculation testing between Multiwfn and cp2kkit.

## Input-generation editor

### Location and fixed source

- Local: `src/cp2kkit/input_tui.py`, run_interactive/Menu/GROUPS.
- CLI: generate-input --tui/--interactive; original arguments retained.
- Upstream: Multiwfn 2026.10.1, Multiwfn_2026.10.1_src_Linux/cp2kmate.f90.
- outCP2Kinp: main numbered menu approximately lines 194-375; return/other settings 389-445.
- Development locator: `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`, not runtime dependency.
- SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Hash recheck (UTC): 2026-10-14; terms: [TERMS.md](TERMS.md).

### References and differences

- Repeated current-settings display, numbered editing, return, and final generation.
- Reimplemented using standard-library line interaction, not copied/distributed
  Fortran UI; no clean-room claim.
- Eight local groups with different numbering; only implemented GPW parameters.
- Retain local defaults, CLI seeds, source restrictions, scientific checks. Do not
  port all upstream options/session persistence/magnetic inference/automatic repairs/direct writes.
- Add previews, quoted replay commands, and default-no confirmation; no shell/CP2K execution.

### Citations, permission, validation

- Both papers remain in input_tui.py/shared input/JSON/notices.
- Original custom terms apply; no extra grant or confirmed relicensing boundary.
- Synthetic unit/CLI/PTY cases; no Multiwfn/CP2K execution or menu/result equivalence claim.

## Default entry and SCF/empty-orbital automatic values

### Location and source

- Local: cli.py, main_tui.py, input_tui.py, inputgen.py.
- Same Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp;
  actually rechecked hash: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Lines 2437-2440: diag 128, enabled-outer OT inner 25; lines 2487-2492: outer 20.
- Lines 1124-1134: smearing on assigns nADDED_MOS=nint(ncenter/2D0), minimum 30;
  turning it off assigns 0.
- Terms/citations/authorization unchanged: [TERMS.md](TERMS.md).

### Use and differences

- Use these formulas; Python (natoms+1)//2 implements Fortran positive half-integer rounding.
- Reference load-then-numbered-menu organization; application dispatch is locally
  implemented for existing functions.
- Not a complete menu/reader port. GJF/CIF/POSCAR are local strict standard-library
  readers, without referencing/distributing Multiwfn reader source.
- UKS dual-spin organization from lines 2525-2529 also used; ADDED_MOS integer-array/
  per-spin meaning separately checked in CP2K 2026.2 SCF documentation linked in the guide.
- Auto applies only to diag+smearing without explicit override. OT rejects smearing/
  nonzero empty orbitals instead of switching to diag. Auto follows current structures,
  not upstream session assignments.
- 400/55 Ry is the user's request, not claimed upstream provenance or system convergence.
- Application/dynamic hiding/auto checks are synthetic; no Multiwfn/CP2K run or full
  behavior-equivalence/scientific-sufficiency claim. Shared generator retains both citations.

## Local scrolling workflow redesign (0.2.4)

- Local: main_tui.py, input_tui.py, input_editor.py, presentation.py.
- This round reorganizes existing local actions, field definitions, and shared
  generator/writer calls into grouped application actions and one complete numbered
  generation menu with stable field numbers. Existing local visibility rules filter
  inapplicable fields without resetting values. The temporary step-based layout was
  replaced at the user's request, retaining version 0.2.4.
- Numbering refinement: re-inspected the same Multiwfn 2026.10.1 cp2kmate.f90,
  outCP2Kinp main menu (lines 200-365) and Other settings (lines 390-435).
  Rechecked SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
  Reuse main IDs -10 return, -7 PBC, -3 cube, -1 task, 0 generate, 1 method,
  2 basis, 3 dispersion, 4 SCF, 6 smearing, 8 k-points, 10 optimizer and 12 pressure
  for their implemented counterparts. Local prompts/capability limits still differ.
  Charge, spin, grids, padding and empty orbitals originate in upstream submenus;
  flattened local controls use explicitly separate 100+ IDs instead of claiming
  upstream main-menu numbers. Unsupported entries are omitted, not reassigned.
- Source/frame now appear in the header; output/project/target-version settings
  rows are removed. Generation still requires explicit confirmation; no physical
  defaults, original citations, or terms were changed. No Fortran source is copied
  or distributed; this is not a full UI or menu-choice equivalence claim.
- Optional Rich is terminal presentation only; batch serialization and the
  standard-library chemistry core do not depend on it.
- Navigation/menu numbers change from earlier cp2kkit releases; correspondence is
  limited to the inspected main-menu IDs above, not all upstream menus/choices.
  Synthetic/PTY checks do not establish upstream UI equivalence or scientific validity.
- Separate authorization remains unrecorded; no new permission or licensing claim.

## Explicit Hubbard U and collinear magnetic initialization (0.2.4)

### Sources and local implementation

- Local: inputgen.py, spin_settings.py, input_tui.py, input_editor.py, cli.py.
- Re-inspected the same user-provided Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp:
  Other settings 8/9, setup around lines 535-612, DFT_PLUS_U/MAGNETIZATION output
  at 1577-1601, UKS at 1739, and PLUS_U_METHOD at 1763.
- Rechecked SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Reference organization: element/atom selection splits atomic kinds, each kind
  carries its magnetic initial guess, DFT+U is KIND-local and uses U_MINUS_J/eV,
  and MULLIKEN projectors are selected in DFT. Original Fortran is not distributed.
- Independently checked exact keyword nesting/units against CP2K 2026.2:
  [DFT_PLUS_U](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/SUBSYS/KIND/DFT_PLUS_U.html),
  [KIND/MAGNETIZATION](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/SUBSYS/KIND.html),
  [DFT/UKS and PLUS_U_METHOD](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT.html).

### Differences and validation limits

- Local menu extensions 124/125 replace cell/data rows; those old controls remain
  CLI/API settings. These are not upstream main-menu IDs for Hubbard/magnetic settings.
- No default U=2 eV or inferred L is copied. Explicit nonnegative Ueff/L is required
  per element; one channel per element and MULLIKEN only. It applies to all split
  kinds of that element. No U/J separation, ramping, LOWDIN switch or occupation constraints.
- Element seeds plus individual 1-based atom overrides are locally parsed and split
  deterministically; atom order/coordinates are retained. Initial spin difference
  is not a local-moment constraint. UKS can be explicitly requested even for a singlet.
- Unlike upstream's magnetic-menu exit, total multiplicity is NOT recomputed from
  the sum of local initial moments. Charge/multiplicity conflicts are errors or
  warnings for explicit correction, never implicit physical-model repairs.
- New requests require target 2026.2. Synthetic input/round-trip/UI/CLI/provenance
  tests are not CP2K execution, shell/projector suitability, magnetic-state or U validation.
- Existing two Multiwfn citations and custom [terms](TERMS.md) remain applicable.
  No extra grant, full-port, clean-room, license-compatibility or release claim.

## GGA and basis profile extension (0.2.6)

- Local: method_profiles.py, data_catalog.py, inputgen.py and the shared CLI/editor.
- Re-inspected the same Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp, SHA-256
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`:
  basis names around 137-147, functional selection 939-999, q suffixes/potential
  policy around 1535-1575, Libxc RPBE 2015-2020, native parametrized PBE 2086-2092,
  and dispersion reference normalization around 2335-2349.
- Actual references: PBEsol/revPBE use PBE PARAMETRIZATION; RPBE separates exchange
  GGA_X_RPBE and correlation GGA_C_PBE; explicit basis q suffixes; RPBE D3 reference
  removes the upstream _LIBXC implementation suffix. Local canonical name is RPBE.
- Independent official CP2K v2026.2 checks: native XC parametrization, Libxc
  registration/name lookup, both D3 damping reference branches, repeated basis-file
  keyword, and exact basis/potential headers. data_catalog.py records all eight
  version-fixed URLs/raw-byte SHA-256 hashes; no upstream Fortran or coefficients
  are distributed. Header aliases/element/q/file metadata are derived, not inferred.
- TZV2PX matches an inspected upstream family; UCL triple-zeta SR and new element
  coverage were derived from official data, not claimed to be Multiwfn dropdown ports.
  Preserve the existing 71-element valence policy; do not substitute q2 for Mg-q10.
- Differences: explicit per-element mixed bases; no missing-family fallback. Prefer
  matched potentials (including B GTH-PBESOL-q3), and require approval for unmatched
  GTH-PBE approximations rather than reproducing upstream's unconditional fallback.
  RPBE requires a user target-build Libxc assertion. Gate new profiles to 2026.2;
  assertions/header checks are not native execution or scientific suitability.
- Supplied modc.py was read-only design reference for future UZH protocol migration,
  not executed/copied/redistributed. Its established hash and UZH source checks are
  recorded in [the roadmap](../../docs/roadmap.md#uzh-protocol-follow-up-modcpy-reference).
  Preserve data-library identity, not just shared aliases/q. In-place overwrites,
  forced numerical resets and regex migration are not implemented.
- The original two citations and custom [terms](TERMS.md) remain applicable.
  No new grant, full-port, clean-room or license-compatibility claim. Synthetic
  generation/round trips do not validate energies, forces/stress, magnetic states,
  convergence, projector-dependent U, or Libxc/runtime library availability.

## Permanent ORB registry follow-up (software 0.2.6, registry v1)

- Local: basis_registry.py, basis_resolution.py, cp2k_data.py, basis_ui.py and
  existing method_profiles/inputgen/CLI/editor adapters. Explicit numbers and
  stable IDs follow the user's requested contract, not an additional Multiwfn
  menu/table port. Existing earlier references/citations/custom terms are retained;
  no new Multiwfn source inspection or authorization is claimed for this follow-up.
- Primary evidence: actual tagged CP2K v2026.2 BASIS_MOLOPT (including SZV non-SR),
  BASIS_MOLOPT_UCL, BASIS_MOLOPT_UZH_2026.2 and POTENTIAL_UZH_2026.2. Versioned URLs
  and raw hashes are recorded in data_catalog.py and [the basis guide](../../docs/basis-selection.md).
  The UZH hashes match the established earlier read-only reference checks.
- New implementation indexes real aliases/headers, checks selected numerical
  payload structure and q, rejects ambiguous content/cross-KIND lookup shadowing,
  and records requested/real paths without inferring versions from filenames.
  The input_cp2k_dft.F reference confirms repeated basis files versus one potential
  file. No coefficients, potential parameters, Fortran routines or user modc.py
  code are copied/distributed. No in-place conversion or numerical resets.
- Read-only actual-data checks: 213 UZH-PBE pairs across the existing 71-element
  fixed-q policy, plus original SZV entries. PBE0 header presence is not method
  support: literal malformed element header at UZH basis line 5614 is not repaired,
  and PBE NA placeholders are not numerical potentials. Synthetic custom fixtures
  are invented parser data, not production scientific parameters.
- Version remains 0.2.6 by explicit request. Registry v1 separates new IDs from the
  earlier 0.2.6 positional menu; older names stay accepted and numeric migration
  is explicit. Validation is unit/interface/real-data parsing only, not native
  CP2K execution, convergence, physical suitability or upstream menu equivalence.
  No separate grant, clean-room, full-port or license-compatibility certification.

## All-electron GAPW and explicit OT algorithm (0.2.7)

- Local: gapw.py, all_electron_catalog.py, basis_registry/resolution, cp2k_data,
  inputgen and shared CLI/editor. Re-inspected Multiwfn 2026.10.1 cp2kmate.f90,
  outCP2Kinp, SHA-256
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Actual references: AE family names 151-158, GAPW selection 1078-1082, no-q AE
  orbital/nuclear ALL output 1536-1575, library mapping 1695-1700, GAPW method
  1860-1861, FULL_ALL for GAPW 2468-2471 and pob IRAC/other STRICT 2478-2483.
  User-requested basis numbers 50-59 and OT menu 110 are local allocations.
- Independent local CP2K evidence: user-supplied tree
  `/home/xwp/soft/cp2k-2026.2`, REVISION git:c92cc08. Exact data, keyword and
  GAPW example hashes are in all_electron_catalog.py. The local revision is not
  asserted equivalent to the named upstream release or an installed binary.
  input_cp2k_scf.F 583-592 verifies OT ALGORITHM STRICT/IRAC and native STRICT.
- Differences: explicit electron model and Z counting, no heavy/ECP or mixed
  model inference; whitelisted AE coverage; strict ALL payload/occupation checks;
  auto profile adds 110/80 atomic grids from the local water example and explicit
  native split tolerances. This is not the example's full numerical setup and
  does not inherit any upstream claim of convergence. PP defaults stay unchanged;
  explicit OT choices override profile suggestions, hidden diag values persist.
- Only header metadata/hashes and independently implemented validation/derivation
  are bundled, not upstream Fortran or production basis/potential parameters.
  Read-only actual data checks: 332 AE basis/nuclear pairs; unit/UI/CLI tests do
  not establish native acceptance, convergence or scientific fitness.
- Existing two papers/citations and custom [terms](TERMS.md) remain applicable;
  no separate grant, clean-room, full-port or license-compatibility claim.

## D3 whole-line filename serialization fix (0.2.7)

- Local: cp2k_data.cp2k_long_path and inputgen.py; no new Multiwfn port/reference.
  Preserve existing citations/custom terms and unconfirmed licensing boundaries.
- Actual failure evidence: user supplied a CP2K ABORT from common/cp_files.F:376
  and a generated `PARAMETER_FILE_NAME "dftd3.dat"` line with no literal internal
  leading whitespace. Running binary version/full output were not supplied.
- Inspected the same local CP2K tree, REVISION git:c92cc08:
  input_cp2k_xc.F defines PARAMETER_FILE_NAME with default_lc_val;
  input/input_parsing.F 526-584 and input/cp_parser_methods.F 535-559 use
  fixed-size chunks, including a quote-only first chunk; input/input_val_types.F
  398-413 joins chunks without left-stripping. common/cp_files.F 373-377 rejects
  a leading blank. This explains the observed failure path by static inspection,
  not execution of the user's binary.
- Exact inspected parser hashes: input/input_parsing.F
  `7a61a8ad06610de89a0b71dc907343655c29160ee8c30ee6d39e804e69bd0299`;
  input/cp_parser_methods.F
  `5bf3ae764d72d89a4a14d56db148883030c42bd84d92e2fc47bdf2ec2a5a98c3`;
  input/input_val_types.F
  `06587067b3ed6623d2f0fbcf81cde1fec4350129a975c26759bc6f3c4ff51e36`.
- Fix: literal whole-line path with shared injection validation and explicit
  rejection of ambiguous whitespace/comment edges; no global quote removal,
  physical setting changes, source/output overwrite or native-validation claim.

## Input-writing policy and library filenames (0.2.7 follow-up)

- Explicit user requests: unquoted basis/potential filenames, JSON off by default,
  and permission to replace generated .inp. These override the historical
  input-writer defaults recorded above, not protections on expensive results.
- Local keyword evidence: the same supplied CP2K tree, REVISION git:c92cc08,
  src/input_cp2k_dft.F 134-147 defines BASIS_SET_FILE_NAME and POTENTIAL_FILE_NAME
  as whole-line strings. Inspected raw SHA-256:
  `93887178d0208020a96826b794459bac9937a66cec8ff6a69b7d4e1d393d5648`.
  The shared literal serializer now covers all three library filename keywords;
  no native execution/all-version parser acceptance is inferred.
- Local write_input stages before replacing only regular .inp; structure/data
  sources (including hardlink aliases), symlinks and non-input results remain
  protected. Optional JSON retains exclusive creation and pre-publication failure
  leaves old input intact. Menu 132/--write-json is opt-in; stale JSON is retained
  and warned, never silently deleted. Analysis/export/plot/cube I/O is unchanged.
- No new Multiwfn algorithm or production parameters are incorporated. Existing
  citations/custom terms/unknown licensing boundaries remain unchanged.

## Universal NGRIDS and omitted GAPW controls (0.2.7 latest follow-up)

- Explicit user request supersedes earlier local profile-v1/v2 descriptions:
  NGRIDS=5 for every PP/AE and SR/non-SR basis; no EPSFIT/EPSRHO0/EPSSVD or
  LEBEDEV_GRID/RADIAL_GRID output in either profile. Numerical profile v3 retains
  GAPW/ALL and basis-aware/manual OT selection but leaves those controls to CP2K.
- This removes the local 110/80 example-derived override, rather than claiming
  it was a Multiwfn default. No new upstream source or numerical coefficients
  are incorporated. Omission resembles the inspected ordinary Multiwfn AE output
  style, not proof of convergence or runtime equivalence. Existing citations,
  terms, source hashes and authorization limits remain unchanged.

## Restart hints, trust radius and motion print (0.2.7 follow-up)

- Local implementation: inputgen.py generate_input/InputSettings; input_tui.py
  shared fields/review/replay; input_editor.py -5/133; cli.py argument dispatch.
- Reference: supplied Multiwfn_2026.10.1_src_Linux/cp2kmate.f90, outCP2Kinp;
  unchanged raw SHA-256
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
  Inspected lines 2414 (NGRIDS), 2453-2456 (SCF guess), 1727-1735
  (restart filename extension/comments), 3107-3120 and 3205-3212
  (optimization radii), 3360-3365 and 3392-3393 (MOTION print).
- Actual use: reference-based Python rendering of commented non-HFX restart hints,
  0.2 angstrom BFGS/LBFGS radius, trajectory and restart-backup templates.
  No original Fortran is distributed or required at runtime.
- Differences: all supported methods use inactive hints (hybrids remain unsupported);
  name derives from resolved PROJECT. Non-Gamma uses .kp, not a falsely named .wfn.
  XYZ is the default for both optimization tasks without task-switching resets;
  EXTXYZ is a local extension checked only for target 2026.2. Radius editing is
  local ID 133; CG hides/retains but does not emit it. The inspected CELL_OPT
  LBFGS branch does not explicitly set radius; this implementation extends the
  same explicit 0.2 value using the shared CP2K optimizer keyword definition.
  MOTION restart backup count is 0; SCF wavefunction backup defaults are unchanged.
- Grid comparison: upstream emits NGRIDS 5 only for ibas 3/4/5 (non-SR MOLOPT);
  other branches omit it. Local universal NGRIDS 5 is the explicit user policy,
  not exact upstream default equivalence. No other grid controls are added.
- CP2K static evidence: supplied local tree REVISION git:c92cc08, not assumed
  equivalent to an official release/binary from its directory name:
  - src/start/input_cp2k_motion.F 1323-1327 and 1569-1573 define BFGS/LBFGS
    TRUST_RADIUS in angstrom (defaults 0.25 and -1, respectively);
    SHA-256 `9371421ff8ace52ba452288647328d34b73cdc30fe421b052474c62734b5963b`.
  - src/input_cp2k_motion_print.F 250-260 / 319-323 define restart backups
    and trajectory XYZ/PDB/EXTXYZ;
    SHA-256 `33b63bf95fe3062f1865d3c6cb9ef54b174a8effe7dd196b897fcbe3ccb2b138`.
  - src/input_cp2k_scf.F 207-213 / 307-318 define ATOMIC guess default,
    restart filename RESTART and separate SCF backup controls;
    SHA-256 `23f7fdd4abfdf64904f0c95ed6dd672f6ca645c0abb7f91b60347ab6693bacf1`.
  - src/qs_mo_io.F 155 / 494-499 use .wfn/.kp; SHA-256
    `c257c64e756a61e1a4d00d9c80779b78a1f445d7bfc367c1746b47e5646449cc`.
  - src/kpoint_io.F 110 writes .kp; SHA-256
    `aea666edd4ea27f4fc8e14bc4567a1b20da1503e01c6d212e29184caf5c03a32`.
- Existing required 2012/2024 papers remain in generated inputs/manifests and notices.
  Multiwfn custom terms still apply; no separate permission or licensing
  compatibility is inferred from Python rewriting or source inspection.
- Validation: synthetic CLI/menu/config/replay/nesting/unit/boundary regressions.
  No CP2K/Multiwfn calculation or acceptance/convergence certification.

## Fixed atoms (0.2.8)

- Local modules: constraints.py parse_fixed_atoms/resolve_fixed_atoms;
  inputgen.py InputSettings/generate_input; input_editor.py menu 9 and atom table;
  input_tui.py shared field/review/replay; cli.py --fixed-atoms.
- Same supplied Multiwfn_2026.10.1_src_Linux/cp2kmate.f90, outCP2Kinp;
  SHA-256 `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
  Actual references: menu 9 at 295-302, index/range prompt at 1150-1173,
  MOTION/CONSTRAINT/FIXED_ATOMS with fractional XYZ and LIST at 3347-3354.
- Reference-based Python workflow/rendering, not a Fortran/str2arr port.
  Local parsing rejects malformed, duplicate/overlapping and active out-of-range
  selections before range expansion. Input is explicit 1-based indices/ranges;
  optH/element shortcuts and partial components are outside this first subset.
  Defaults remain unconstrained. Repeated LIST lines contain at most 20 indices.
- Differences: limited to GEO_OPT/CELL_OPT (not upstream MD/TS); source/frame
  changes retain indices with warnings, never silently clear/remap them.
  ENERGY/ENERGY_FORCE retain but do not emit hidden selections. Constraints
  from source/restart/POSCAR files are not inherited.
- CP2K evidence: supplied tree REVISION git:c92cc08, not inferred official/binary
  equivalence. src/input_cp2k_constraints.F create_fixed_atom_section, 334-377,
  defines fractional positions, COMPONENTS_TO_FIX XYZ and repeatable integer LIST;
  SHA-256 `2761dd6df4a1ab7200d50de32481aea2942dabbb92ab5562c722713b73bb360f`.
  Active selections are currently gated to target 2026.2. In CELL_OPT frozen
  fractional coordinates can move with the cell; this is not Cartesian pinning.
- Existing 2012/2024 papers and custom terms remain in force; generated
  inputs/manifests retain citations. No separate permission, whole-project
  license compatibility or clean-room exemption is inferred.
- Validation: synthetic index/range/bounds/nesting tests, CLI/menu/config/replay,
  selected frame/expanded CIF/KIND-order checks and non-destructive write checks.
  No CP2K/Multiwfn execution or scientific/convergence certification.

## Grid/OT/SCF backup/comment policy (retained 0.2.8 follow-up)

- Local gapw.py resolve_ngrids/resolve_gapw, inputgen.py generate_input, and shared
  CLI/menu/review/config/replay. Existing fixed-atom work is retained.
- Same supplied cp2kmate.f90/outCP2Kinp, SHA-256
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`:
  lines 145-147 identify ibas 3/4/5 as classic non-SR TZVP/TZV2P/TZV2PX;
  2414 emits NGRIDS 5 only for those choices; 2478-2483 select explicit OT
  IRAC for pob/CDFT, STRICT otherwise. This replaces the historical local
  universal-five-grid policy. Effective per-element overrides use any matching
  family; custom alias names do not establish a registry-family identity.
- Explicit user extension: all AE families now default to emitted IRAC, not just
  pob, in both legacy auto/native profiles. PP emits STRICT; manual choices win.
  Profile v4 omits NGRIDS for AE and keeps native QS/KIND numerical controls.
  This does not claim exact upstream algorithm/default equivalence.
- SCF restart backup evidence: supplied local CP2K REVISION git:c92cc08,
  src/input_cp2k_scf.F 307-318 defines SCF/PRINT/RESTART and BACKUP_COPIES;
  SHA-256 `23f7fdd4abfdf64904f0c95ed6dd672f6ca645c0abb7f91b60347ab6693bacf1`.
  New output explicitly sets zero backups without RESTART OFF; .wfn/.kp
  extensions follow the previously recorded writer evidence. No cadence or
  restart filename override is added. Generation never touches wavefunctions.
- Header-only comment policy is the user's formatting request. Inactive restart
  hints are removed, not activated. Suggestions remain metadata/review only,
  with emitted=false and runtime_verified=false. Safety/units stay in review,
  manifest and docs, rather than inline generated comments.
- Existing source/terms/citations and unknown authorization boundaries remain
  unchanged. No original Fortran, numerical payload or new licensing grant.
- Validation: synthetic family/override/OT/nesting/comment/config/replay checks.
  No CP2K/Multiwfn execution, installed-version equivalence or convergence proof.

## Uniform EPS_SCF (retained 0.2.8 follow-up)

- Explicit user request changes ordinary ENERGY default from the previously
  referenced Multiwfn 5e-6 to 1e-6, matching other supported task defaults.
  Same supplied cp2kmate.f90/hash above; lines 1778-1794 distinguish ordinary
  ground-state ENERGY (5e-6) from derivative tasks (1e-6) and tighter tasks.
- inputgen.py now uses 1e-6 only when eps_scf is unset; explicit CLI/API/config
  values are preserved. OT inner/outer share it; diag emits it once. EPS_DEFAULT
  and other physical/numerical requests are unchanged. Old inputs are not rewritten.
- This is a local policy override, not exact Multiwfn equivalence or an energy
  error bound in hartree. Existing terms/citations/authorization limits remain.
  Synthetic task/SCF/default/override regressions only; no native calculation.

## Template for future features

Copy this structure for each referenced feature and supply evidenced facts.
Register other authors' code separately and preserve notices.

```markdown
## <Feature>

### Location and fixed source
- Local module/function:
- Upstream version/package:
- Upstream file/subroutine:
- Source SHA-256 or an actual upstream commit:
- Registration/recheck date:
- Applicable terms:

### Actual references
- <Algorithm, workflow, tables, defaults, or code portions actually used>

### Implementation and differences
- <Reference-based implementation, rewrite, or direct port; no automatic exemption>
- <Behavior differences and verification sources>

### Citations and authorization
- <Citation/copyright preservation locations>
- <Additional method papers>
- <Separate grants, actual evidence/scope, or explicitly unknown>

### Validation boundary
- <Tests/unverified items; requested outcomes are not verified results>
```
