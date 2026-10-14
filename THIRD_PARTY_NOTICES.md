# Third-party sources and authorization

This document summarizes third-party material used or referenced by cp2kkit.
It is not a license for the whole project, grants no rights beyond upstream
authorization, and does not establish license compatibility.
Register provenance for future implementations, rather than merely adding software names.

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

Registered modules include `src/cp2kkit/inputgen.py` (generation) and
`src/cp2kkit/input_tui.py` (numbered interaction, not a Fortran UI port).
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
This repository does not distribute basis coefficients, potential parameters,
or dftd3.dat. User-supplied --data-dir files are checked read-only and hashed;
their actual use/distribution must follow the applicable terms.
