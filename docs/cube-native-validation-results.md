# Native CUBE format regression coverage (0.4.1)

This public record describes format coverage, not a private execution environment
or a certification of any installed CP2K build. Hostnames, accounts, local paths,
scheduler records and installation-specific diagnostics are not distributed.

## Included evidence

The small [native excerpts](../tests/fixtures/cube-native-041/README.md) cover
CP2K 2025.2 Development and 2026.2 output formatting for the three water cases in
the [preparation protocol](cube-native-validation.md). Older output samples do
not expand the generator's target-version support, which remains 2026.2 for the
new potential/orbital requests.

Eleven source records contain six selected stdout excerpts and five CUBE headers.
Only version, SCF/virtual-solver formatting, energy/warning records and header
geometry are included. Execution timestamps and private stdout sections are
omitted. Source paths are explicit non-filesystem aliases; original full-source
hashes, sizes and selected line numbers are retained for provenance. They do not
authenticate a public downloadable dataset or establish successful process exit.

The headers exercise exact UKS `SUM OF ALPHA AND BETA DENSITY` recognition,
unknown potential/orbital scalar semantics, orbital/spin labels, and differences
in raw atom auxiliary fields. Such auxiliary fields are not pseudopotential
valences and do not define geometry/grid identity.

## Separate acceptance levels

The [offline audit example](../examples/cube-validation/README.md) independently
checks preparation/data/input identities, main SCF, each requested OT virtual spin,
complete CUBE contents, grid/geometry and supplied exit evidence. Synthetic
regressions exercise failed and missing exit records independently of convergence.

Header-only excerpts cannot pass full CUBE EOF validation. Selected stdout is not
a complete run and does not establish clean execution. A printed version, SCF
convergence or PROGRAM ENDED marker is not installation/scientific certification.
No compiler, runtime-library or upstream defect is inferred from these fixtures.

Raw inputs, outputs, wavefunctions, full grids, execution receipts and environment
diagnostics remain private and outside the Git distribution. Their exclusion does
not convert unavailable or failed evidence into a passing result. See the
[closeout boundaries](closeout-0.4.1.md) for the software validation scope.
