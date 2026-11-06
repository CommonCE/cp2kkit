# Native CUBE validation preparation (0.4.1)

## Scope and preparation

This protocol prepares inputs, not calculations or scientific acceptance. Use
`examples/cube-validation/prepare.py` from a checkout, with a verified Python >=3.10:

```bash
PYTHONPATH=src /absolute/python examples/cube-validation/prepare.py \
  --data-dir /actual/cp2k/data --output /new/parent/cube-validation
```

The parent must exist; the output must not exist, including as a dangling symlink.
The helper has no executor, MPI launcher, Multiwfn call or scheduler script.
Cluster execution requires separate authorization, core count, time limit and
submission scope. No public cp2kkit CLI/API or physical default changes.

The helper reuses `Structure`, `InputSettings`, `generate_input`, selected-entry
basis/potential checks, `new_file` and `staged_files`. It copies actual
BASIS_MOLOPT/GTH_POTENTIALS bytes and checks their hashes against the originals.
Selected H/O DZVP-MOLOPT-SR-GTH-q1/q6 and GTH-PBE-q1/q6 entries must pass shared
payload/alias/q checks. A data directory name does not certify a release or binary.
No basis parameters are bundled in the repository. Synthetic tests use synthetic
libraries only and cannot establish real-software compatibility.

All three cases share the same constructed, unoptimized geometry in angstrom:
O (8,8,8), H (8.757,8,8.586), H (7.243,8,8.586). They use fixed-geometry ENERGY,
PBE/GPW, no dispersion, isolated PERIODIC NONE, 16 angstrom cubic cell, Gamma,
400/55 Ry cutoff/relative cutoff, EPS_SCF 1e-7, MAX_SCF 128, MAX_OUTER_SCF 20,
no smearing and CUBE STRIDE 1 1 1. These are explicit smoke-test settings, not
converged physical recommendations. MAX_SCF is deliberately common in the suite;
OUTER_SCF applies only to OT. OT retains native EPS_LUMO/MAX_ITER_LUMO controls;
no tolerance relaxation, automatic solver substitution or ADDED_MOS increase.

| Case | State | SCF | ADDED_MOS | NHOMO/NLUMO per spin | Expected frontier indices (1-based) |
| --- | --- | --- | --- | --- | --- |
| 01-rks-ot | H2O, charge 0, multiplicity 1, RKS, 8 PP electrons | OT | 0 | 1/1 | restricted HOMO 4, LUMO 5 |
| 02-rks-diag | same H2O/state | diagonalization | 2, explicit | 2/2 | occupied 3,4; virtual 5,6 |
| 03-uks-ot | H2O+, charge +1, multiplicity 2, UKS, 7 PP electrons | OT | 0 | 1/1 | alpha HOMO 4/LUMO 5; beta HOMO 3/LUMO 4 |

Every case requests electron density, native V_HARTREE_CUBE and signed MO_CUBES;
UKS density additionally requests alpha-minus-beta spin density via the shared
generator. Index predictions follow explicit pseudopotential valence counts,
not all-electron counts or a claim about the ground-state spin. Requested virtual
counts are not proof of basis capacity, actual file counts or convergence.

## Identity, publication and failure policy

`case-matrix.json` records original/staged data path, byte size and SHA-256,
geometry identity, helper/protocol/source-module hashes, generator/target versions,
common and per-case settings, explicit states, requests and frontier predictions.
Actual binary, convergence, process/scheduler status and actual CUBE inventories
remain null; checks remain pending. No predicted file count is recorded as observed.

Each `water.inp.json` is the **unchanged generator manifest**, including original
text/hash and checked absolute data paths. Deployment changes only those two data
rows to case-local filenames linked to `../data`. The matrix separately records
`generator_input_sha256` and the deployed `input_sha256`. Run, if authorized later,
from each case directory; preserve the complete bundle and relative symlinks.
The generator sidecar's text/hash intentionally does not identify the deployed
input. Verify both identities and the sole documented transformation before use.

Directories, copied data, symlinks and geometry can remain after preparation
failure for inspection; an existing partial directory cannot be retried/reused.
Inputs, sidecars, matrix and protocol publish together with exclusive staged
writes; exceptions roll back only owned published inodes and temporary text files.
This is not a crash-atomic directory transaction. No recursive cleanup of user
paths or pre-existing scientific results is attempted. Choose a fresh path after
failure. Do not manually merge bundles or relabel a partial bundle as complete.

## Later evidence checklist (all pending until measured)

Write a **new** result inventory/report beside preserved raw outputs; do not
replace this preparation manifest with success defaults. Record input/data hashes
as actually used, binary path/hash, version/build/banner, exact launch command,
working directory, resources, scheduler job identity and stdout/stderr hashes.

1. **Main SCF:** preserve line-numbered convergence evidence for the final main
   SCF and, for OT, outer convergence. Record iteration limits, warnings and aborts.
   An energy value, generated file or PROGRAM ENDED is not SCF convergence proof.
2. **OT virtual eigensolver:** separately locate post-SCF unoccupied-state
   iterations, convergence messages/residuals and relevant warnings for each spin.
   Record effective EPS_LUMO/MAX_ITER_LUMO from version-matched source/output if
   available; otherwise retain unknown. SCF convergence does not imply virtual
   convergence. Missing independent evidence stays null/pending, not passed.
   Diagonalization uses the explicitly added states, not this OT solver; mark the
   OT-specific check not applicable with a reason, not a fake convergence result.
3. **Orbitals and naming:** enumerate actual filenames, MO indices, spin indices,
   comments/metadata and requested versus observed occupied/virtual sets. Expect
   native project/iteration suffixes and `WFN_<orbital>_<spin>` middle names, with
   spin 1=alpha and 2=beta for UKS; do not hard-code a complete filename template.
   Validate the channel-specific frontier numbering in the table. Include density,
   spin-density and `v_hartree` files separately, detect duplicates/truncation and
   distinguish missing states from a request capped by available basis states.
4. **CUBE integrity:** use the existing read-only `cube-check` without a density
   assertion for potential/orbitals. Record every file's byte SHA-256/size, header,
   atom order/coordinates, origin, signed grid counts/spatial units, voxel vectors,
   grid shape, expected/actual scalar counts and finite-value checks. Compare
   actual grids/origins across channels/cases before any comparison. Do not assume
   shared stride guarantees identical grids. Preserve raw results on parse failure.
   CP2K spatial coordinates are expected in bohr; MO amplitudes in bohr^(-3/2),
   density in e/bohr^3 and native potential in atomic potential units. These are
   source-based expectations: the current checker keeps potential/orbital scalar
   meaning and units unknown. Never force density units into cube-diff/cube-planar.
5. **Potential semantics:** native electrons+ions potential has the opposite sign
   to physical ESP. Preserve original bytes, no automatic negation. GTH ionic
   potential is not all-electron point-nuclear ESP; electrostatic zero depends on
   boundary/reference convention. Isolated Poisson/vacuum and especially charged
   H2O+ require reference/cell checks before interpreting absolute values. No work
   function, vacuum alignment or cross-case absolute-potential accuracy claim.
   Orbital phase is arbitrary; raw signed amplitudes need not match bitwise.
6. **Exit status:** preserve scheduler State/ExitCode/DerivedExitCode, process
   return code/signal, stderr, PROGRAM ENDED and SCF/virtual evidence as separate
   fields. A late SIGSEGV or failed scheduler exit remains failed even with complete
   cubes and converged SCF. Complete diagnostic outputs may be used for data-chain
   testing without blocking development, but this is not clean execution success
   or proof the exit error cannot affect any result. Do not turn unknown into zero.

Cell/basis/grid/state convergence, orbital fidelity and scientific validation are
separate future work. Preparation does not certify a CP2K installation or authorize
execution/environment repair. Existing surface results/submission identities are
not changed by this suite.

## References and boundaries

Keyword/source semantics and Multiwfn references are recorded in the
[input-generation guide](input-generation.md#potential-and-frontier-orbital-cubes-041)
and [provenance](../third_party/multiwfn/PROVENANCE.md). This helper composes the
existing generator, not a second implementation of CP2K or Multiwfn. No new
upstream source port, numerical payload or additional authorization is claimed.
Preserve the [terms](../third_party/multiwfn/TERMS.md) and required citations:
Tian Lu, Feiwu Chen, J. Comput. Chem. 33, 580–592 (2012); Tian Lu,
J. Chem. Phys. 161, 082503 (2024).
