# Synthetic GEO_OPT observation baseline

`observation.txt` is a hand-written public format fixture, not a CP2K output or a
calculation. Its zero energy is deliberate: zero must survive parsing and must not
be treated as missing. The printed version is explicitly synthetic. No coordinates,
physical system, native compatibility or scientific result is established.

From the repository root:

```bash
PYTHONPATH=src python -m cp2kkit parse examples/geo-opt-contract/observation.txt --format json
PYTHONPATH=src python -m cp2kkit report examples/geo-opt-contract/observation.txt --strict
```

With an installed package, use `cp2kkit` in place of
`PYTHONPATH=src python -m cp2kkit`.
The parse command exports to stdout and the strict report returns 0 for this
fixture because supported text checks pass, not because any calculation ran.
Removing the geometry/end markers keeps parse export successful but makes the
strict report return 7. Neither command modifies the input.

`expected-fields.json` is a manually specified **selected-field expectation**, not
a complete export, a JSON Schema or an import format. Tests recursively compare
these fields with actual API output while allowing additional dictionary keys.
Array lengths and scalar types are checked, including false versus zero. Absolute
paths, byte hashes and parser version are checked separately at runtime rather
than replaced with invented provenance in the example. Actual exports include
source paths and original text; omitted fields here are not absent from exports.

`tests/test_contract_example.py` checks this baseline, legacy-field presence,
missing/conflicting settings, Python/CLI agreement and strict-report exit codes.
Additional boundary cases remain in `tests/test_geo_opt_contract.py`,
`tests/test_output_settings.py` and `tests/test_parser_boundaries.py`.
These tests validate producer behavior, not any external consumer's compatibility.

See the [observation contract](../../docs/geo-opt-contract.md) for semantics and
migration. This baseline does not freeze exact warning prose or a closed set of
JSON keys; consumers must tolerate unknown keys and the absence of newer optional
fields in older exports. No consumer adapter, database or scheduler is required.
