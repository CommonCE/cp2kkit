# ADMM / ADMMS / RI-HFX native validation preparation (0.3.6)

## Status and authority

This is an input-preparation protocol, not native validation evidence. Preparation
runs only Python file generation and static checks. Do not run CP2K (including
native input-check modes), MPI, Multiwfn or a scheduler until execution is explicitly
authorized, a binary/build and resource budget are agreed, and new run paths exist.
Software stays **0.3.6**, schema **0.1.0**. Existing calculations are not modified.

The preparation script is `examples/admm-ri-validation/prepare.py` in the checkout.
From the repository root, with the verified project interpreter:

```bash
PYTHONPATH=src /path/to/python examples/admm-ri-validation/prepare.py \
  --data-dir /path/to/cp2k-2026.2/data \
  --output /path/to/entirely-new-preparation-directory
```

The output directory must not exist; its parent must exist. Missing data fails
before directory creation. Other failures may leave a partial new directory for
inspection; never rerun into it or remove it automatically. This helper is not a
new public CLI command, scheduler tool or chemistry renderer: it uses the shared
generator and exclusive staged publication.

## System and fixed setup

- A constructed neutral water molecule: O (0,0,0), H (+0.757,0,0.586),
  H (-0.757,0,0.586), rigidly translated by (+8,+8,+8) angstrom before writing
  water.xyz, so all atoms lie well inside the explicit cell for WAVELET Poisson.
  This is an illustrative smoke geometry, not an optimized or literature reference.
- CP2K **target 2026.2**; actual executable version/build/features remain unknown.
  A nearby source tree or REVISION is reference identity, not binary verification.
- PBE0, HF fraction 0.25, full Coulomb exchange; GPW, Gamma, PERIODIC NONE,
  16 x 16 x 16 angstrom cell, WAVELET Poisson. Coordinates are already translated;
  the generator retains them unchanged with the explicit cell in every case.
- Charge 0, multiplicity 1, RKS, 8 pseudopotential valence electrons
  (O q6, two H q1); no magnetism, dispersion, +U, smearing, density/CDD or forces.
- ORB `molopt-sr-dzvp` / DZVP-MOLOPT-SR-GTH with checked H/O q; GTH-PBE
  potentials as resolved by the generator. This is the existing GTH-PBE
  approximation for PBE0, not a bespoke hybrid pseudopotential validation.
- CUTOFF 400 Ry, REL_CUTOFF 55 Ry; no grid/basis/cell convergence claim.
- OT, STRICT, FULL_ALL, DIIS; MAX_SCF 25 and outer MAX_SCF 20.
  Both EPS_SCF values are explicitly 1e-8 instead of the generator default 1e-6;
  HF EPS_SCHWARZ is explicitly 1e-8 instead of 1e-6. These common tighter settings
  are preparation choices, not certified energy-error bounds. QS EPS_DEFAULT
  and all other native-default/derived thresholds remain generator-resolved;
  consult each sidecar for their exact full-path identities and selection origins.
- When active, AUX_FIT is `admm-dzp`; RI uses MEDIUM, metric HFX,
  EPS_FILTER 1e-9 and MEMORY_CUT 3. MEMORY_CUT is batching, not a memory cap.
  Four-center cases retain MAX_MEMORY 512 MiB per MPI process; RI cases omit
  HF/MEMORY and record the corresponding direct-resource quantities as null.
  Actual aggregate job memory and RI tensor memory are unknown.
- All cases use PROJECT water but separate directories. Do not combine their
  restarts. No restart input or shared wavefunction is provided; preserve new
  wavefunctions if execution is later authorized. Repeated timings need fresh
  run directories and controlled cold-start conditions.

## Six-case matrix

| ID | ADMM model / purification / scaling | HFX backend | RI parent |
|---|---|---|---|
| 01-direct | off | four-center | not applicable |
| 02-admm | BASIS_PROJECTION / MO_DIAG / NONE | four-center | not applicable |
| 03-admms | CHARGE_CONSTRAINED_PROJECTION / NONE / MERLOT | four-center | not applicable |
| 04-ri | off | RI | ORB |
| 05-admm-ri | BASIS_PROJECTION / MO_DIAG / NONE | RI | AUX_FIT |
| 06-admms-ri | CHARGE_CONSTRAINED_PROJECTION / NONE / MERLOT | RI | AUX_FIT |

All ADMM paths retain EXCH_CORRECTION_FUNC DEFAULT; ADMMS is explicitly selected,
not implied by RI. The ordinary-to-ADMMS comparison changes projection,
purification and scaling together; it does not isolate a single mechanism.

Each case contains water.inp and its full water.inp.json provenance sidecar.
Shared data/ contains byte copies of BASIS_MOLOPT, GTH_POTENTIALS,
BASIS_ADMM_UZH and t_c_g.dat, with original source paths/hashes in case-matrix.json.
Relative case-local symlinks point to these copies, allowing runtime basename
lookup without the original absolute data path. Preserve the whole directory tree
and symlinks during transfer. Staged data copies are local preparation artifacts,
not newly bundled project payloads or a license/redistribution grant. Check data
terms before sharing them. Do not transfer only the .inp files.

Before a later run, rehash the staged data and inputs against the matrix/sidecars;
record a separate transfer-verification report. Sidecar absolute paths identify
preparation provenance and are not automatically rewritten to cluster paths.
case-matrix.json also records generator source-file hashes for this dirty checkout.
Keep the matching checkout/source diff separately when archiving for reproduction.

## Acceptance checklist: preserve separate validation levels

1. **Prepared:** six inputs/sidecars exist; input hashes match; geometry, cell,
   charge/spin, ORB/potential, HF/XC and common numerical settings agree. Only
   the declared approximation/backend/resource differences are allowed. Synthetic
   tests and static section checks establish no native compatibility.
2. **Binary/build and data identity (pending):** record actual executable path,
   hash, reported version/revision and linked/build features. Match the intended
   2026.2 keyword contract. Record exact MPI implementation, rank/thread counts,
   library/thread environment, host, memory allocation and job identity. Verify
   staged data byte hashes and case-local lookup, including t_c_g.dat for RI
   initialization. No binary has been probed by this preparation step.
3. **Native syntax acceptance (pending):** in separately authorized new run
   directories, use a documented target-build check if available. Verify actual
   effective ADMM method/purification/scaling/correction and RI parent/metric,
   not merely balanced sections or a successful parser return. Do not invent
   a check-mode flag or interpret it as SCF convergence.
4. **Bounded execution (pending):** agree rank/thread/memory and per-case wall-time
   limits before running. Capture stdout and stderr separately, launcher/process
   exit status and scheduler status (when applicable). Preserve complete inputs,
   outputs, wavefunctions and hashes. Never infer success from PROGRAM ENDED
   alone: a late SIGSEGV, nonzero exit, timeout or unknown process status fails
   clean-exit acceptance. Missing metrics stay null, not zero.
5. **SCF convergence (pending):** verify the final relevant SCF/outer-SCF outcome,
   finite final ENERGY in hartree, absence of fatal diagnostics and clean process
   exit for every member of a comparison pair. An energy from a failed or
   unconverged run may be retained as evidence but must not pass comparison.
6. **Numerical comparisons (pending):** use Delta E = E(test) - E(reference),
   hartree, preserving signed and absolute differences. Compare 04-ri vs
   01-direct for independent RI; 05-admm-ri vs 02-admm and 06-admms-ri vs
   03-admms for RI increments at fixed ADMM variant. Compare every accelerated
   path with 01-direct for total approximation differences. No error tolerance
   is approved yet: record an application-specific tolerance before deciding
   accuracy acceptance; closeness alone is not proof of a correct model.
7. **Convergence studies (not prepared):** use new cases to vary RI size/filter
   at fixed ADMM, AUX_FIT size at fixed RI, and common basis/grid/cell/screening
   settings consistently. Recompute paired references where needed. This
   six-case smoke matrix alone cannot establish convergence of either approximation.
8. **Performance and broader claims (pending/out of scope):** only compare clean,
   converged runs with identical controlled resources and repeated cold starts.
   Keep SCF iterations, setup/SCF/total timing and measured peak memory separate;
   unknown memory is not MAX_MEMORY. Tiny water does not establish scalable
   speedup. ENERGY-only RKS/NONE data does not validate forces, optimization,
   periodic/UKS/HSE06 paths or support expansion.

Do not fill pending result fields from requests, suggested defaults or source
expectations. Keep result collection in new reports, not by overwriting the
preparation matrix. Failures require the project's error-diagnosis workflow;
do not change the cell, screening, solver or physical model to hide them.
