# Synthetic CP2K normal-mode observations

`molecular.txt` is hand-written to exercise the CP2K 2026.2 molecular
normal-mode table grammar. It is not a CP2K calculation, an excerpt of a
private log, a physical reference spectrum or a proof of convergence. It
includes diagnostic lines that must not become frequency records and two mode
output groups with four observed values. `expected-selected.json` checks key
fields without freezing the entire result, parser version or machine-dependent
absolute paths.

```bash
PYTHONPATH=src python -m cp2kkit vibration examples/vibration-results/molecular.txt \
  --zero-threshold-cm-1 0.5 --strict
PYTHONPATH=src python -m cp2kkit vibration examples/vibration-results/molecular.txt \
  --format csv -o molecular-frequencies.csv
```

The first command reports two raw negative values, one threshold-classified
negative, two near-zero values (including `-0.5 cm^-1`), and one positive value.
Strict success is a textual result, not evidence of a stationary point. See the
[result contract](../../docs/vibration-results-contract.md) and
[regressions](../../tests/test_vibration_results.py).
