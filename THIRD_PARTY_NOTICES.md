# Third-party sources and authorization

This document summarizes third-party material used or referenced by cp2kkit.
It is not a license for the whole project, grants no rights beyond upstream
authorization, and does not establish license compatibility.
Register provenance for future implementations, rather than merely adding software names.

## Local CP2K all-electron reference audit (0.2.7)

`all_electron_catalog.py` records header-only family/element coverage and exact
local file hashes from the supplied CP2K tree, REVISION git:c92cc08. Its identity
is not inferred to be an official release or binary from the directory name.
No coefficients, nuclear potential parameters or upstream Fortran are bundled.
GAPW atomic grids/default tolerances, OT keyword definitions, restart naming,
optimizer radii and MOTION output controls were inspected;
see [the basis guide](docs/basis-selection.md#all-electron-automatic-setup-027)
and [feature provenance](third_party/multiwfn/PROVENANCE.md).
Existing CP2K references and upstream method/basis citations still apply; this
notice does not assign a whole-project license or certify compatibility.

## Multiwfn

### Upstream information

- Software: Multiwfn
- Author: Tian Lu
- Website: http://sobereva.com/multiwfn/
- Official custom terms: http://sobereva.com/multiwfn/download.html

### Use and provenance

Some modules were developed with reference to Multiwfn organization, numerical
workflows, parameter tables, defaults, or rewritten code. Record actual use honestly per module.

- [Terms](third_party/multiwfn/TERMS.md): inspected official excerpts, sources, dates.
- [Provenance](third_party/multiwfn/PROVENANCE.md): local modules, upstream version/
  file/subroutine/hash, use, differences, permission, and a future-entry template.

Registered modules include `src/cp2kkit/inputgen.py` (generation),
`src/cp2kkit/spin_settings.py` (explicit Ueff/L and initial-spin KIND organization),
`src/cp2kkit/method_profiles.py` (inspected parametrized-PBE/Libxc RPBE/q/reference branches),
`src/cp2kkit/functional_registry.py` (0.3.0 non-hybrid XC/component/nonlocal
assembly, including Libxc-backed meta-GGAs and BEEFVDW's internal PW92 requirement;
0.3.2 native PBE0/HSE06/B3LYP XC composition; 0.3.3 BHandHLYP/M06-2X
Libxc definitions and explicit-fraction PBEh assembly),
`src/cp2kkit/hybrid.py` (0.3.2 direct-HFX operator/fraction/radius/resource assembly,
including explicit VWN3; no RI-HFX or numerical table payload),
`src/cp2kkit/admm.py` and `src/cp2kkit/auxiliary_basis.py` (0.3.4 bounded
PBE0/HSE06 projection, solver-dependent purification and checked AUX_FIT
family/q organization; reference-based Multiwfn/CP2K assembly, no coefficients),
`src/cp2kkit/xtb.py` (0.3.1 GFN-xTB chooser/model/backend assembly, CP2K model
reference counts and file-byte identities, no numerical parameter payload),
`src/cp2kkit/xtb_versions.py` (tagged 2024.2-2026.2 source hashes/capability checks,
not bundled upstream code or a claim of native runtime validation),
and `src/cp2kkit/input_tui.py` / `src/cp2kkit/input_editor.py` (numbered interaction
and selected inspected upstream main-menu IDs, not a full Fortran UI port).
Menu 9 fixed atoms references the inspected index/range workflow and
MOTION/CONSTRAINT/FIXED_ATOMS templates; local constraints.py is a bounded Python
parser, not a port of upstream str2arr. Fractional-coordinate semantics and LIST
repetition were checked against the supplied local CP2K source. No Fortran or
new numerical payload is bundled; authorization/citation limits are unchanged.
The historical local 124/125 U/magnetism extensions (now 112/103) are not upstream main-menu IDs;
they require explicit parameters and do not reproduce upstream's automatic
multiplicity-from-local-moments change.
Software 0.2.9 adds local menu_registry.py category/direct routing and
density_workflow.py bundle orchestration, reusing the existing generator and
density-print references. No VASPKIT code, new upstream keyword template or
numerical payload is bundled. See the feature provenance for the common-grid
lock, explicit atom mapping and validation boundaries.
Not distributing original Fortran or requiring the Multiwfn binary does not
establish strict clean-room implementation or exemption from upstream conditions.

### Authorization status

Multiwfn uses custom terms, not MIT/BSD/GPL. See the recorded originals; recheck
for changes before distribution.

No separate author permission has been obtained for this integration. Unless
provenance records an actual grant, do not assume relicensing, paid distribution,
or combination with other licenses is settled. Citations/provenance do not replace
necessary permission; a future project license cannot override upstream terms.

For other authors' code inside upstream files, check/register/preserve separate
copyright and terms instead of assigning everything to Multiwfn's custom terms.

### Papers required by the official terms

1. Tian Lu, Feiwu Chen, **Multiwfn: A multifunctional wavefunction analyzer**,
   *Journal of Computational Chemistry*, **33**, 580–592 (2012).
   DOI: https://doi.org/10.1002/jcc.22885
2. Tian Lu, **A comprehensive electron wavefunction analysis toolbox for chemists, Multiwfn**,
   *Journal of Chemical Physics*, **161**, 082503 (2024).
   DOI: https://doi.org/10.1063/5.0216272

The generator and its input/JSON retain both citations. Related research must
cite them appropriately in the main text under the official terms; code citations
do not replace paper citations. Register additional method/upstream references per feature.

## CP2K input specification and data

The generator checks keywords/nesting and basis/potential names using official
input references and database headers; sources are in [input generation](docs/input-generation.md).
src/cp2kkit/data_catalog.py derives header-only name/element/q/file metadata from
CP2K v2026.2 BASIS_MOLOPT, BASIS_MOLOPT_UCL, GTH_POTENTIALS,
BASIS_MOLOPT_UZH_2026.2 and POTENTIAL_UZH_2026.2; versioned URLs/hashes
also identify inspected XC/D3/input definitions. No Fortran/Libxc C implementations, basis
coefficients, potential parameters, dftd3.dat or nonlocal kernel tables are distributed. These metadata do
not establish whole-project license compatibility or native-runtime certification.
The UCL library header credits Sanliang Ling and Ben Slater; MOLOPT references
VandeVondele and Hutter, J. Chem. Phys. 127, 114105 (2007), DOI 10.1063/1.2770708. User-supplied --data-dir files are checked read-only and hashed;
their actual use/distribution must follow the applicable terms.

Registry-v1 numbers are the user's explicit contract, not a claim of complete
Multiwfn choice-number equivalence. New registry/resolver/data-reader/basis-editor
modules use local Python logic and CP2K data-format/header evidence; no additional
Fortran or numerical basis/potential payload is bundled. UZH-PBE pairs were parsed
read-only, not executed. PBE0 headers/NA placeholders and unknown source versions
are not promoted to validated methods. See [basis selection](docs/basis-selection.md)
and [provenance](third_party/multiwfn/PROVENANCE.md). No new authorization or
whole-project licensing compatibility claim is made.
