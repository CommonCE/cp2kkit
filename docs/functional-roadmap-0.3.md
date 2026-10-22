# Multiwfn-referenced functional and xTB plan for 0.3.x

## Status and direction

**Partially implemented: 0.3.0 delivers 15 non-hybrid DFT profiles; 0.3.1 adds
all three GFN-xTB models; 0.3.2 adds PBE0, HSE06 and B3LYP direct-HFX input
generation within the bounded initial scope.** BHandHLYP, M06-2X and configurable
PBEh remain deferred. See the [implemented capability matrix](input-generation.md#non-hybrid-xc-profiles-030).
This plan alone authorizes no calculations, installation, further version/default
changes, commit or push. Later release assignments remain to be agreed.

Use **Multiwfn's CP2K input generator as the primary functional coverage and
input-assembly reference**, rather than inventing an independent short list.
Inspect its method selection, XC components, HF, ADMM/RI-HFX, basis/potential
handling and dispersion branches together. Adapt checked definitions into the
shared Python generator, with explicit CP2K-version and data/model restrictions.
This is reference-based development, not a claim of a full port or clean-room work.

The source baseline below exposes **21 DFT selections** across LDA/GGA,
meta-GGA, nonlocal and hybrid methods, counting configurable PBEh as one profile
and B97M-rV/BEEF-vdW
as complete named methods. This count excludes ADMM variants, dispersion
variants, double hybrids and correlated wavefunction methods. Five of the 21
were implemented before this expansion; all 15 non-hybrid selections are now
implemented within the 0.3.0 generator limits. OLYP is no longer a core target merely because
it appeared in the earlier independently selected plan.

Also retain the user-requested **GFN-xTB series: GFN0, GFN1 and GFN2**, counted
separately from XC functionals. Initial target is **CP2K 2026.2**; GPW/PP is the
initial DFT branch, while xTB uses its own model/backend/parameter path. Older
targets and additional GAPW/AE combinations require separate checks.

## 1. Fixed source and evidence boundary

- Multiwfn **2026.10.1**, local package `Multiwfn_2026.10.1_src_Linux`.
- Development locator: `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`,
  subroutine `outCP2Kinp`; not a runtime dependency or a bundled source file.
- Rechecked SHA-256:
  `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Inspected method menu/mapping around lines 933-1056, xTB around 1815-1841,
  ADMM/XC around 1964-2150, HF/RI around 2168-2240, and dispersion around
  2329-2392. Hash/file/subroutine establish identity; line numbers are auxiliary.
- Terms/citations and planning reinspection are recorded in
  [provenance](../third_party/multiwfn/PROVENANCE.md) and
  [terms](../third_party/multiwfn/TERMS.md). No new license or separate grant is inferred.

This is static source inspection. It does not verify CP2K acceptance,
convergence, scientific suitability, or equivalent outputs from the two programs.
The upstream menu also contains non-XC methods; it is not an instruction to enable
all of them or every combination in 0.3.0.

## 2. DFT coverage taken from the upstream menu

Names below are public planning labels, not interchangeable CP2K shortcut keywords.
Keep existing stable settings/aliases such as PBESOL and REVPBE compatible.

| Group | Target profiles | Reference/implementation boundary |
|---|---|---|
| LDA (1) | Pade / LDA | Use the specific PADE definition, not an unspecified LDA correlation variant |
| GGA (6) | PBE, revPBE, PBEsol, BP86, BLYP, RPBE | Upstream BP maps to BP86; RPBE uses Libxc; retain the five existing local profiles |
| Meta-GGA (6) | TPSS, revTPSS, SCAN, r2SCAN, MN15L, HLE17 | Reference upstream Libxc component definitions; audit spin, grids and derivative support |
| Meta-GGA plus nonlocal correlation (1) | B97M-rV | Complete upstream XC plus rVV10 definition; not B97M-V without its required nonlocal term |
| Nonlocal vdW functional (1) | BEEF-vdW | Complete upstream base XC plus nonlocal kernel; ensemble/error-estimation workflows are separate |
| Global hybrid (3) | PBE0, B3LYP, BHandHLYP | Complete XC/HF composition; preserve the explicitly identified B3LYP correlation variant |
| Screened hybrid (1) | HSE06 | Full short-range exchange setup; not HSE03 |
| Hybrid meta-GGA (1) | M06-2X | Complete Libxc/XC/HF definition, not a standalone Libxc subsection |
| Configurable hybrid family (1) | PBEh | Explicit HF fraction with complementary semilocal exchange; bounds/units and reproducible settings required |

**Target: 21 upstream-referenced DFT profiles + 3 GFN-xTB methods.** This replaces
the earlier 14-profile proposal. It is a coverage objective for the series, not a
claim of 24 XC functionals, unrestricted element coverage or immediate availability.

### Related numerical options

- Reference upstream direct HFX, optional ADMM and RI-HFX as distinct controls,
  not extra functionals. Deliver them only with audited auxiliary bases and
  backend/solver compatibility; enabling a hybrid does not imply all accelerators.
- Reference the upstream none/D3/D3(BJ)/D4/rVV10 menu and functional-name mappings.
  Add only verified functional/correction pairs; D4 build support and nonlocal
  kernel identities need independent checks. No universal cross-product promise.
- Treat B97M-rV/BEEF-vdW as complete definitions. Do not add pair dispersion again
  or substitute generic rVV10 parameters when a method requires specific values.
- Other vdW-DF variants, OLYP, rSCAN and arbitrary Libxc mixtures are outside this
  baseline unless separately requested or introduced by a reviewed source update.

## 3. GFN-xTB as one series

Use one family selector with three model choices, not three XC functional entries.

| Model | Agreed initial backend | Important distinction |
|---|---|---|
| GFN0-xTB | CP2K-native | Non-self-consistent; no SCC iteration/mixer assumptions |
| GFN1-xTB | CP2K-native | Self-consistent; native charge/SCC and solver controls |
| GFN2-xTB | tblite linked into CP2K | Require build/API compatibility evidence; never fall back to GFN0/1 |

This agrees with the inspected Multiwfn branches. GFN1/tblite is not an additional
backend in this initial scope. Do not invoke an external xtb executable or install
tblite automatically. Preserve each model's intrinsic dispersion; no extra DFT-D
correction. The CP2K documentation identifies D4/GFN0, D3(BJ)/GFN1 and D4/GFN2.

xTB uses parameterized bases, reference occupations and interactions, not MOLOPT/
GTH selection or the current PP valence-count table. Audit element coverage,
electron counting, charge/spin and applicable convergence controls per model.
Implemented target checks span 2024.2-2026.2 for GFN1, >=2025.1 for GFN0,
and >=2025.2 for GFN2/tblite; unavailable upstream interfaces cannot be supplied
by the generator. GFN1 supports default OT and explicit diag. GFN2 OT generation
is enabled only for target 2026.2; legacy 2025.2/2026.1 requires explicit diag after
the native 2026.1 crash investigation (2025.2 remains conservatively restricted,
not runtime validated). No automatic solver fallback is allowed. Do not equate
tblite ACCURACY (exposed only on 2026.2) with CP2K EPS_SCF. Keep explicit incompatible
DFT requests out of xTB output; do not silently disable intrinsic model terms.

Start with nonperiodic Gamma ENERGY, then add ENERGY_FORCE/GEO_OPT after derivative
checks. Open-shell, periodic/non-Gamma and cell-stress paths need separate audits.
These are generator staging limits, not blanket CP2K limitations. GPW density
CUBE/CDD, +U, HF/ADMM, MD/NEB, solvation, custom parameter refits and IPEA1 are
outside the initial xTB subset. Intended uses include preoptimization/screening,
not automatic substitution for DFT adsorption/reaction energetics.

## 4. Staged delivery

Stages 1-3 are delivered as the bounded 0.3.0 generator subset, not as runtime
or scientific validation. Stage 5 is delivered in 0.3.1 for isolated closed-shell
ENERGY/ENERGY_FORCE/GEO_OPT only. Stage 4 is partially delivered in 0.3.2:
PBE0/HSE06/B3LYP, direct HFX, target 2026.2, GPW classic MOLOPT/UCL Gamma
NONE/XYZ ENERGY/ENERGY_FORCE/GEO_OPT without +U or smearing. Broader xTB scope,
remaining hybrids, ADMM/RI-HFX and stage 6 expansion remain future work; the initial capability
matrix is already documented. The list retains the series-level audit goals.

1. **Inventory and registry:** use the fixed upstream menu as the acceptance
   checklist; mark each branch existing, partial, missing or version-inapplicable.
   Extend the current small profile model for actual semantic requirements, not
   a parallel chemistry generator. Keep functional 110, dispersion 111, planned
   hybrid controls 120-122 and planned semiempirical 140 distinct. Existing
   CLI/config/replay and immutable basis numbers remain compatible.
2. **LDA/GGA and meta-GGA:** add PADE/BP86, retain the existing five GGAs, then
   implement Libxc definitions with r2SCAN/SCAN/TPSS first, followed by revTPSS,
   MN15L/HLE17. Audit potential availability, spin and derivative paths per profile.
3. **Complete nonlocal methods:** implement B97M-rV and BEEF-vdW with their
   required XC/nonlocal terms, parameters and kernel identity together. Do not
   ship an incomplete named method while describing it as supported.
4. **Hybrids:** PBE0, HSE06 and B3LYP first; then BHandHLYP, M06-2X and PBEh.
   Audit direct-HFX first, ADMM/RI-HFX separately. Reuse allocated UZH-PBE0
   numbers 30-32 only after actual orbital/potential/element/q audits, not by
   relabeling UZH-PBE. Initial Gamma-only generator scope can expand after checks.
5. **GFN-xTB:** proceed in parallel after method dispatch exists; implement the
   shared series with native GFN0/1 and tblite GFN2, model-specific controls and
   conflicts. Do not wait for all hybrid work to finish.
6. **Consolidation:** publish a capability matrix for task, spin, PBC, k-points,
   SCF, PP/AE, +U, density/CDD, dispersion and backend/build restrictions. Update
   tests, source provenance, documentation and version once per agreed delivery.

## 5. What must not be copied blindly

- Upstream defaults are starting choices, not universal convergence settings.
  Verify exact keyword spelling/nesting, units, HF coefficients/screening and
  dispersion parameters against the target CP2K source/manual before coding.
- Upstream generic GTH-PBE choices or SCAN/PBE0 data suggestions are not evidence
  of matched potentials or complete basis coverage. Preserve actual file/q/hash
  identity; unmatched approximations require explicit approval, not silent repair.
- Do not adopt automatic solver/basis/spin changes, restart-dependent screening,
  disabled charge-sanity checks or resource assumptions without an explicit local
  policy and evidence. Preserve the project's non-destructive writer and current
  comment/restart rules, not upstream direct-output/comment behavior.
- Preserve charge/multiplicity and source PBC. Grid/SCF defaults such as 400/55 Ry
  or 1e-6 do not establish convergence for new methods. Admit forces/optimization
  and cell stress only with the appropriate derivative evidence.
- CLI/TUI/config/replay share one implementation; record complete effective XC,
  HF/model/backend, units, data/kernel sources and hashes where available.
  Build assertions and unchecked templates must not become runtime-validated.

## 6. Acceptance and deferred methods

Required tests: XC/HF coefficients and section structure, complete nonlocal terms,
missing Libxc/tblite/auxiliary/kernel data, bad combinations/states, deterministic
CLI/TUI/config/replay, old-profile regressions, and collision/rollback protection.
Distinguish source checks, synthetic generation, actual acceptance, convergence
and property validation. Native checks require separate user approval and a new
run directory; exact system, charge/spin, software/backend versions and data/
parameters must be specified before execution. No such run is authorized here;
0.3.0 validation is synthetic generation and read-only source/data inspection.

The upstream menu's RI-MP2, RI-SCS-MP2, RI-(EXX+RPA), GW and double hybrids
(B2PLYP, B2GP-PLYP, DSD-BLYP, revDSD-PBEP86) remain **separate later scopes**.
Their XC/HF pieces alone do not implement their correlation energy. PM6,
SCC-DFTB and FIST also remain separate. Referencing Multiwfn does not make all
menu entries, arbitrary q changes, external execution or submission in scope.

### 0.3.2 hybrid implementation boundary

The first three hybrid profiles are now enabled in CLI/API/TUI/config/replay,
including ordered native XC definitions, direct four-center HF and source/hash
metadata. See the [hybrid capability matrix](input-generation.md#direct-hfx-hybrids-032).
No Libxc assertion is needed for these native definitions; a suitable Libint
build is still required and not detected. PBE0/HSE06 use 25% HF; B3LYP uses 20%
and explicit VWN3. Isolated global hybrids use COULOMB; XYZ global hybrids use
TRUNCATED with a face-spacing-bounded radius; HSE06 uses SHORTRANGE omega=0.11
bohr^-1. EPS_SCHWARZ/memory/radius have explicit controls at menu 120.
121/122, UZH-PBE0 30-32 and auxiliary bases remain unavailable, not implicitly
enabled by this feature. Default pure-DFT input text is unchanged. No CP2K
calculation, syntax acceptance, convergence or property validation in this round.

## 7. Additional references

- Local implementation: `functional_registry.py`, `method_profiles.py`, `basis_registry.py`,
  `basis_resolution.py`, `inputgen.py`, and current profile tests.
- [CP2K 2026.2 XC_FUNCTIONAL](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/XC/XC_FUNCTIONAL.html):
  component/backend definitions and hybrid/TPSS restrictions.
- [CP2K 2026.2 NON_LOCAL](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/XC/VDW_POTENTIAL/NON_LOCAL.html):
  target-version kernels/parameters/nesting; 0.3.0 uses the method-specific values.
- [CP2K 2026.2 xTB tutorial](https://manual.cp2k.org/cp2k-2026_2-branch/methods/semiempiricals/xtb.html),
  [XTB](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/QS/XTB.html)
  and [TBLITE](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/QS/XTB/TBLITE.html):
  model/backend mapping, intrinsic dispersion and self-consistency controls;
  not a probe of the installed build.

See [implemented xTB scope](input-generation.md#gfn-xtb-methods-031).
Unimplemented branches remain plans, not enabled methods or validated calculations.
