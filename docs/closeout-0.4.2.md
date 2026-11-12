# 0.4.2 closeout and acceptance boundaries

Software **0.4.2**, exchange schema **0.1.0**. The independent-toolkit positioning
and GEO_OPT observation-contract development stage is complete. This is not a
package-index publication, immutable Git checkpoint or scientific certification.

## Included scope

- Separate toolkit/parser identity from the output-derived CP2K version and schema.
- Preserve legacy final_energy as the last successfully parsed Quantity; expose
  last_observed_energy with segment, step and SCF evidence, without a final-state claim.
- Retain malformed/unsupported energy evidence and context; consume its pending SCF
  summaries. Preserve ambiguous SCF associations and conservative text quality.
- Preserve ordered raw setting records and independently normalize printed charge,
  multiplicity, spin treatment, UKS and bounded GPW/GAPW QS representation. Unknowns,
  unsupported values and conflicts are not replaced by defaults or last values.
- Maintain the public synthetic example, selected-field expectations and API/CLI
  regressions. These do not establish native CP2K layout coverage or compatibility
  of any external consumer.
- Keep private object links, persistence, import decisions and workflow states in
  downstream consumers. No consumer repository, database or credentials are needed.

The [GEO_OPT contract](geo-opt-contract.md), [schema](schema.md),
[architecture boundary](architecture.md#producer-and-consumer-responsibilities)
and [public example](../examples/geo-opt-contract/README.md) define this baseline.
Legacy fields and CSV columns are retained. New optional fields do not require a
schema bump; incompatible field meanings require a separate migration decision.

## Packaging closeout

Initial archive inspection found missing third-party documents and missing sdist
fixtures/examples. The corrected packaging configuration now:

- Includes the existing third-party notices, Multiwfn terms and provenance in both
  sdist and wheel; archive contents were compared byte-for-byte with source files.
- Includes maintained documentation, examples, tests and fixtures in the sdist via
  MANIFEST.in. Private scratch results and scientific binaries are not build inputs.
- Uses project.license-files with setuptools >=77 as a **build-only** requirement.
  Runtime dependencies remain empty and Python >=3.10 remains declared. See the
  [setuptools configuration reference](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html).
- Does not set a license expression or infer redistribution/paid-use authorization.
  See [third-party notices](../THIRD_PARTY_NOTICES.md) for unresolved boundaries.

## Checks completed for this stage

- Source-tree and extracted-sdist unittest: **655 passed, none skipped** in each
  run on Python **3.12.16**. The sdist includes repository text-policy inputs needed
  by the tests, including .gitignore.
- The four public-example tests passed, including selected scalar types, legacy
  fields, setting unknown/conflict behavior and API/CLI parity with strict exits.
- sdist and wheel built using the declared isolated build backend. The wheel was
  built from the sdist, not by relying on an adjacent source checkout.
- A fresh temporary environment installed only the wheel, without dependencies,
  Rich or Matplotlib. Import location and installed distribution version were
  checked outside the repository with source-tree import paths disabled.
- Installed Python API, console script and module CLI agreed for the synthetic
  complete and truncated examples; parse returned 0, strict report returned 0/7,
  source fingerprints matched and input bytes remained unchanged.
- Installed generator assembly smoke passed without publishing inputs or running
  calculations. This is not exhaustive installed-feature or optional-extra coverage.

Final delivery separately records compileall, local-link/whitespace checks and
artifact fingerprints. Raw logs, disposable environments and build artifacts stay
outside the repository; no commit, tag, push or package-index upload is implied.

## Deferred work and downstream use

No final-candidate energy, complete physical-method identity, magnetization/electron
number-difference normalization or output-to-structure association is introduced.
End markers, SCF convergence, geometry convergence, observation availability,
process exits and scientific validity remain separate. No process exit or restart
continuity is inferred from stdout.

Downstream consumers can use this observation baseline, preserving sources,
nullable values, status fields and segment boundaries, and tolerating unknown keys
or absent newer optional fields. They must not map the last observation to a
confirmed final optimized result. A reproducible dependency still needs an explicit
code revision or artifact hash; a version string alone does not identify a worktree.

Additional Python/OS versions, editable installation, isolated optional-extra
installation, CI and scientific/native validation remain separate future gates.
Publication and third-party authorization decisions remain with the owner.
