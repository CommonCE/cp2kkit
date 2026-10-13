# Fixture provenance

All files in this directory are hand-written, synthetic format fixtures.
They are not calculation results and do not certify compatibility with any CP2K release.
The illustrative version string is metadata only, not a verified software version.
No energies here may be used as scientific results.
The CUBE cases in tests/test_cube.py are also hand-written synthetic fields,
created only in temporary test directories. Their expectations are derived from
constant-field determinant quadrature and manual pointwise subtraction, not
CP2K calculations. No real CP2K cube regression was available for this stage.
Replace/extend these with licensed, anonymized real CP2K outputs before claiming version support.
