# Fixture provenance

Files directly in this directory are hand-written, synthetic format fixtures.
The separately documented [cube-native-041 excerpts](cube-native-041/README.md)
are selected real evidence with original source hashes and line locators, not
complete logs/CUBEs or scientific validation. Do not classify that subdirectory
as synthetic, or confuse its header-only excerpts with complete native datasets.
They are not calculation results and do not certify compatibility with any CP2K release.
The illustrative version string is metadata only, not a verified software version.
No energies here may be used as scientific results.
The CUBE cases in tests/test_cube.py are also hand-written synthetic fields,
created only in temporary test directories. Their expectations are derived from
constant-field determinant quadrature and manual pointwise subtraction, not
CP2K calculations. No real CP2K cube regression was available at that original implementation stage.
The 0.4.1 excerpt regressions add real native formatting/evidence coverage, but
remain distinct from full retained CUBE audits and general version certification.
