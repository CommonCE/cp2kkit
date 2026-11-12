# Synthetic vibrational-generation baseline

`water.xyz` is hand-written geometry, not an optimized structure or calculation
result. `settings.json` is a supported InputSettings mapping. The example is
catalog-only: unset CP2K_DATA_DIR and do not supply libraries when comparing with
`expected-fields.json`. It checks template assembly, not data availability,
CP2K execution, stationarity or frequency accuracy.

From the repository root, read/generate without publishing files:

```python
import json
from pathlib import Path
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.structure import read_structure

root = Path('examples/vibration-contract')
settings = InputSettings.from_config(json.loads((root/'settings.json').read_text()))
structure = read_structure(root/'water.xyz', frame=0)
text, manifest = generate_input(structure, settings)
replayed = InputSettings.from_config(manifest)
assert generate_input(structure, replayed)[0] == text
```

Use an installed package or set PYTHONPATH=src for source-tree Python execution.
For CLI publication choose a new output directory; this command never runs CP2K:

```bash
mkdir -p test-workspace
run_dir=$(mktemp -d test-workspace/vibration-example.XXXXXX)
PYTHONPATH=src python -m cp2kkit generate-input examples/vibration-contract/water.xyz \
  --frame 0 -o "$run_dir/water.inp" --project vibration-contract \
  --run-type VIBRATIONAL_ANALYSIS --cp2k-version 2026.2 \
  --method DFT --functional PBE --basis molopt-sr-dzvp \
  --periodic NONE --charge 0 --scf ot --ot-algorithm STRICT --write-json
```

Keep generated files in a local/ignored workspace, not this maintained example.
The CLI takes explicit settings, not settings.json as a --config argument.
Warnings/progress go to stderr, not a JSON stdout stream. Read water.inp.json
for the manifest. Do not repeat into an occupied directory without considering
the regular-.inp replacement and exclusive-sidecar rules.

`expected-fields.json` is a manually specified selected-field expectation, not a
complete manifest, JSON Schema or request. Missing entries here are not absent
from real exports. Additional dictionary keys are allowed; selected scalar types
(including false versus zero), list lengths and values are checked. Toolkit
version, actual source byte hash/path and generated UTF-8 hash are verified
separately at test time rather than replaced with fabricated provenance.

`tests/test_vibration_contract.py` checks this baseline through public API and
noninteractive CLI, sidecar replay, auto/explicit origins, absence/extra metadata,
source protection, stale-sidecar handling and failure exit codes. Tests create
only disposable files, run no scientific software and need no downstream repo,
real data directory, cluster or optional plotting/UI packages. Full task/scope
checks remain in `tests/test_vibration.py`.

See the [consumer contract](../../docs/vibration-contract.md). Generation flags
are configuration, not observations; in particular false runtime/stationarity
verification must not be imported as either a completed or failed calculation.
