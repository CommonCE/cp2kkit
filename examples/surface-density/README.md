# Fixed-geometry surface density smoke models (0.4.0)

```bash
PYTHONPATH=src /path/to/python prepare.py \
  --data-dir /path/to/cp2k-2026.2/data --output /new/parent/surface-density
```

Run with `PYTHONPATH` pointing at the checkout's `src` directory, or use an
installed cp2kkit. The output parent must exist and the output directory must not
exist (symlinks also refused). No ASE/dependency installation is needed.
**Preparation never executes CP2K, probes a binary, or submits a job.**

## Constructed models

Three deterministic, unoptimized poses: H2O, NH3 and CO2 on a 3x3 primitive h-BN
monolayer (9 B + 9 N, lattice a=2.50 angstrom). The skew in-plane cell has vectors
(7.50,0,0), (3.75,6.49519053,0) angstrom; the normal cell length is 18 angstrom.
The layer is at z=6.0 angstrom, molecular heavy-atom reference at z=9.2 angstrom.
This is a repeated monolayer model, not a thick bulk surface or relaxed adsorption
geometry. Charge and multiplicity are explicitly 0 and 1 for whole/A/B.

- PBE/GPW, DZVP-MOLOPT-SR-GTH, matched GTH-PBE; checked actual data staged once.
- Gamma, PERIODIC XYZ with periodic Poisson, OT/DIIS/STRICT without smearing.
- CUTOFF 400 Ry, REL_CUTOFF 55 Ry, EPS_SCF 1e-7, inner/outer maxima 25/20.
- ENERGY only, STRIDE 1 1 1, same whole-system geometry/cell for fragments.
- Fragment A=atoms 1-18 (h-BN); B=complement (molecule). No ghosts.
- No dispersion, dipole correction, geometry relaxation, adsorption energies or
  convergence study is implied. These are workflow test choices, not recommended
  production settings. Metal surfaces are not covered by these gapped models.

Each model has the original whole/A/B bundle, source EXTXYZ, atom-map CSV and
complete generation JSON. Independent `whole/`, `fragment_a/`, `fragment_b/`
run directories contain `density.inp` and relative `data/` symlinks to the staged
library directory. Deployment changes **only** the two checked data-reference
lines, rebasing them to `data/BASIS_MOLOPT` and `data/GTH_POTENTIALS`. The case
matrix records original generated and deployed input hashes separately. Original
source manifests are not relabeled as deployed manifests; local absolute source
paths describe preparation evidence, not remote file locations.

## Authorized execution and post-processing

Obtain explicit resource/submission authorization separately. Use entirely new
run directories and preserve stdout, stderr, scheduler IDs/status, actual binary
version, data/input identities and cube hashes. Inspect SCF convergence and final
termination **and** process/scheduler status. Never treat `PROGRAM ENDED` alone
as a clean exit. The [first trial](../../docs/surface-density-validation.md) failed
at process exit despite having SCF convergence and usable diagnostic cubes.

Use exact cube names from each run, not globs that can select stale/multiple frames:

```bash
cp2kkit cube-check /exact/whole.cube -o whole-check.json
cp2kkit cube-check /exact/surface.cube -o surface-check.json
cp2kkit cube-check /exact/molecule.cube -o molecule-check.json
cp2kkit cube-diff /exact/whole.cube /exact/surface.cube /exact/molecule.cube \
  -o delta-density.cube
cp2kkit cube-planar delta-density.cube --axis z -o delta-planar.csv
```

All post-processing outputs must be new. Match actual grids, confirm electron
integrals, and compare the final cumulative profile integral with the 3D integral.
Accumulation/depletion and cumulative integrals are not automatically atom- or
fragment-resolved net charge transfer. See [cube conventions](../../docs/cube.md).
