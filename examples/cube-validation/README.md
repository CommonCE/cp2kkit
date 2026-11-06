# CUBE preparation and offline audit (0.4.1)

These checkout examples use the existing generator/parser/CUBE checker. Neither
runs CP2K, MPI, Multiwfn, SSH, sacct or sbatch. No new public cp2kkit CLI/API,
physical setting, field type or legacy-target support is introduced.

## Prepare inputs only

```bash
PYTHONPATH=src /absolute/python prepare.py --data-dir /actual/cp2k/data \
  --output /new/parent/bundle
```

Use the script path `examples/cube-validation/prepare.py` from the repository
root. Output must be entirely new, with an existing parent. See the
[preparation protocol](../../docs/cube-native-validation.md) for the common water
geometry, explicit states, numerical settings and staged-publication boundaries.
Actual execution needs separate authorization and a fresh calculation directory.
Preparing or auditing never changes that authorization boundary.

## Audit returned files without executing anything

Run from the repository root with a verified Python >=3.10 and `PYTHONPATH=src`:

```bash
PYTHONPATH=src /absolute/python examples/cube-validation/audit.py \
  --plan /path/to/audit-plan.json --output /new/parent/audit
```

The example-local JSON plan is explicit; it does not search for the newest job,
infer a submission identity or merge restart segments. Paths are absolute or
relative to the plan file, not the current directory. For example:

```json
{
  "format": "cube-audit-plan-v1",
  "cases": [
    {
      "id": "2026.2-rks-ot",
      "preparation_matrix": "bundle/case-matrix.json",
      "preparation_case": "01-rks-ot",
      "input": "runs/01-rks-ot/water.inp",
      "data_directory": "runs/01-rks-ot",
      "stdout": "returned/01-rks-ot/water.out",
      "stderr": "returned/01-rks-ot/water.err",
      "cube_directory": "returned/01-rks-ot",
      "scheduler": "accounting.psv",
      "job_id": "123456",
      "process_status": null,
      "checksums": {}
    }
  ]
}
```

`preparation_matrix` is produced by this example's `prepare.py`; its selected case
provides the deployed/generator input hashes, original generator sidecar, requested
settings, expected channels and per-spin MO indices. Do not relabel/rewrite old
manifests. The sidecar remains beside the preparation matrix, even when the input
was copied to a different run directory. The helper compares the **actual run
input** against the matrix's deployed hash, not against the generator text hash.
Only single-segment fixed-geometry ENERGY/GPW cases are supported here.

`data_directory` points to the deployed basis/potential filenames (case-local
symlinks are supported). These bytes are compared against preparation source
hashes; recorded absolute source paths are provenance, not deployment paths.

All eight fields through `cube_directory` are required; missing evidence files
or null optional stdout/stderr paths are reported explicitly, not treated as
successful empty output. Case IDs must be nonempty/unique; unknown case keys and
ambiguous/missing preparation cases are rejected. `scheduler`, `job_id`,
`process_status` and `checksums` are optional. There is no shell expansion.

### Scheduler/process evidence

`scheduler` is an existing saved **sacct -P / --parsable2** text snapshot, never a
command to execute. It requires one `JobID|...` header containing State/ExitCode,
plus exact job and `.batch` rows for a positive clean scheduler assessment.
Additional columns, including DerivedExitCode, are preserved. A preamble such as
SSH warnings is retained separately; malformed/duplicate rows are rejected.
Non-array numeric job IDs only are supported in this bounded example.

- FAILED/11:0 remains failed even if DerivedExitCode=0:0.
- PENDING/RUNNING 0:0 is not a measured exit and remains unknown.
- Missing batch rows or empty exit codes cannot establish clean exit.
- An absent scheduler file remains unknown; the helper never contacts a cluster.

Optional `process_status` is an existing JSON file containing an independently
captured `returncode` (integer or null). Zero is preserved, negative values retain
subprocess signal convention, and null/missing values stay unknown. Booleans,
non-finite numbers and strings are rejected. The helper records its source hash;
it does not prove that an externally supplied status belongs to a process.
Scheduler ExitCode, DerivedExitCode, captured returncode and stderr rank signals
are separate records. No process returncode is manufactured from stdout or Slurm.

### Hash evidence

`checksums` optionally maps **filenames** (for example `water.out` or a complete
native CUBE filename) to expected lowercase SHA-256 values recorded at transfer
or collection. Include every stdout/stderr/CUBE filename when checking full
transfer coverage. Unknown/missing expected filenames make the provided-checksum
assessment false. Without a supplied checksum for a file, its comparison remains
null while its observed byte identity is still recorded. A true
`provided_checksums_match` means all **provided** checksums matched, not that every
file had an external checksum. Full identity coverage is visible in
`source_identities`; filenames must be unambiguous within each case.

### Report and safety behavior

The output directory must not exist, including as a file or dangling symlink.
`results.json` publishes exclusively via `io.staged_files`; failed publication
cleans only its own staging/published inode. A failed audit can leave an empty
new directory for inspection; choose a fresh directory rather than retrying into
it. No original input, data, output, CUBE, wavefunction, log or preparation identity
is modified. There is no overwrite flag or automatic cleanup of input directories.

Exit 0 means **a report was written**, not that calculations passed. Existing
project error conventions are used: usage/I/O 2, ambiguity 3, parsing 4 and output
collision 5. The example has no overall scientific acceptance/strict-pass mode.

The report independently records:

- Deployed input, generator-text and requested-settings identities; actual deployed
  data comparisons; matrix/sidecar/plan/helper/core-source provenance.
- Output banner, main SCF, outer SCF, PROGRAM ENDED and original line evidence.
  Explicit earlier SCF failure remains false even if later steps converge.
- OT virtual convergence per requested spin, independently of SCF. Missing,
  duplicate or unassigned spin blocks cannot pass. Diagonalization is explicitly
  not applicable to the post-SCF OT check, not a fabricated successful iteration.
- CUBE byte identities, complete/finite EOF parsing, actual count, exact requested
  MO/spin multiset and header labels, native density channels, grids/origins and
  atom elements/coordinates versus generated geometry (1e-6 bohr tolerance).
  CUBE directories are flat; all `*.cube` files are considered, so stale/extra
  cubes cannot be silently selected away. Missing directories are unknown;
  present empty directories have actual count zero and unmatched requests.
- Raw atom auxiliary fields remain preserved; they are not pseudopotential
  valences and are excluded from geometry/grid comparisons. No interpolation,
  density reinterpretation, orbital phase alignment or potential negation occurs.
- `clean_exit` is three-valued and independent of convergence and CUBE integrity.
  A failed available exit record or fatal evidence makes it false. True requires
  PROGRAM ENDED, known empty stderr, and positive exit evidence; unknown available
  exit evidence cannot be overridden by a different successful record.
- Potential reference alignment and scientific validation remain null, regardless
  of clean exit or file completeness. Potential/orbital scalar types/units remain
  unknown in shared CUBE reports. Raw integrals are not electron counts.

No inference of method accuracy, physical reference fitness, cell/grid/basis
convergence, authenticity of supplied metadata, or harmlessness of late SIGSEGV
is made. This is an example-local audit format, not a new package data contract.

## Evidence and regression boundaries

The [native-format record](../../docs/cube-native-validation-results.md) describes
privacy-filtered regression coverage without private execution details.
Excerpts in `tests/fixtures/cube-native-041/` contain selected real lines/header
rows, original full-source hashes and original line numbers; source paths are
non-filesystem aliases and timestamp/private diagnostic sections are omitted.
They are not complete calculation outputs or CUBEs and cannot pass EOF integrity
on their own. Synthetic tests exercise complete tiny fields, incomplete evidence,
identity mismatches, status conflicts, missing/duplicate orbitals and collisions.
No unit test executes a quantum calculation or depends on local `test-workspace/`.
