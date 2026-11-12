# 0.4.3 closeout and acceptance boundaries

Software **0.4.3**, exchange schema **0.1.0**. The bounded molecular vibrational
**input-generation development stage is complete**. This is not a complete
frequency-analysis platform, package publication or scientific certification.

## Included scope

- CP2K target 2026.2, isolated Gamma PBE/classic MOLOPT-UCL GPW, closed-shell
  RKS and OT/STRICT; unsupported combinations are rejected, not repaired.
- Central finite differences of forces with explicit DX in bohr (auto 0.01),
  EPS_SCF task preset 1e-8 and QS EPS_DEFAULT 1e-14. Explicit EPS_SCF must be no
  looser than 1e-8. Existing basis/grid choices are not silently changed.
- Explicit MT/PERIODIC NONE task preset for positive axis-aligned orthorhombic
  cells. Supplied cells and coordinates are not resized, rotated or recentered.
  The displaced-atom envelope check is necessary but cannot establish that
  the box contains twice the electronic-density extent.
- Explicit NPROC_REP 1, FULLY_PERIODIC F, INTENSITIES F and THERMOCHEMISTRY F.
  Native PROGRAM_RUN_INFO diagnostics are enabled to stdout at global LOW
  verbosity. The native Minimum Structure heading is not optimization evidence.
- Reject isolated single atoms and DX values that round away at generated
  bohr-coordinate precision. Representability does not imply an accurate DX.
- Shared API/CLI/TUI/config/replay validation and generation, optional effective
  values/origins/source identities, and existing protected staged publication.
  Geometry is explicitly supplied; filenames and frames never prove convergence.

The [task contract](input-generation.md#molecular-vibrational-inputs-043),
[schema](schema.md#generated-vibrational-inputs-software-043),
[architecture](architecture.md#vibrational-input-task-043) and
[third-party provenance](../third_party/multiwfn/PROVENANCE.md#molecular-vibrational-inputs-043)
define this subset and its reference/authorization boundaries.

## Checks and acceptance

- Focused generation/interface/writer/version regression: **109 passed**.
- Source-tree full regression: **673 passed, none skipped**, on Python 3.12.16.
  Tests use synthetic structures/data or separately documented format fixtures;
  they never launch CP2K or contact a scheduler.
- Two legacy-task matrices, **96 cases each**, retain identical input text
  fingerprints or rejection messages against the pre-feature baseline.
- The final generated input completed a separately authorized small H2O native
  smoke case with clean process/scheduler exit, empty stderr and no reported
  CP2K warnings. Displaced/reference energy and force tables and Hessian
  diagnostics were present. Each replica recorded SCF convergence; the three
  printed mode frequencies matched the prior diagnostic-disabled case exactly
  at printed precision. Only the diagnostic print section changed between those
  inputs; this was not a new scientific method or parameter-convergence study.
- Compileall, version/schema consistency, maintained English/local-link tests
  and whitespace checks passed. These do not certify scientific accuracy.

Native execution records, scheduler identities, machine-specific diagnostics,
inputs and full outputs are local-only, not public fixtures or test dependencies.
The package remains a generator with no execution/submission feature. A single
native case cannot certify all allowed elements, bases, geometries or builds.

## Consumer-contract completion addendum

The same 0.4.3 stage now includes a [public contract index](contracts.md), a
[consumer-facing vibrational generation contract](vibration-contract.md) and a
[synthetic public example](../examples/vibration-contract/README.md). Seven new
contract tests check selected fields/types, actual provenance, API/CLI publication,
auto/explicit origins, metadata absence/addition and replay, validation/error
codes, source protection, sidecar collisions and input-only stale-sidecar behavior.
They use only public interfaces and disposable files, not downstream models or
private native outputs. from_config's request-validation/version-negotiation
limits are documented rather than strengthened or hidden by a new schema.

After this addendum, focused contract/feature/example/text/version checks passed
**36 tests**, and the full source suite passed **680 tests, none skipped**.
Compileall, CLI version and whitespace checks passed. The earlier 109/673 counts
above describe the initial closeout, not the updated total. Runtime generation
interfaces and scientific settings did not change; no new native calculation was
needed or executed for this documentation/example/test round. Native evidence
above remains a separate, limited acceptance check.

The new synthetic XYZ is explicitly included by MANIFEST.in rules. At the
contract-addendum stage, package rebuild/install checks had not yet run; the
subsequent final-verification section below records their results. Development rules and
feature/review/version prompts now require proportionate public-contract impact
assessment and applicable executable checks, without requiring a new spec or
schema version for every internal change. Producer tests still do not certify
integration of a particular consumer such as chemops.

## Final packaging and installed-core verification

- Built the 0.4.3 sdist in an isolated environment using the declared build
  backend, then built the wheel from that sdist rather than directly from the
  checkout. The runtime dependency set remains empty; extras remain optional.
- Required source modules, tests/fixtures, contract examples, maintained docs and
  prompt guidance were present in the sdist and matched snapshot bytes. Wheel
  modules matched the sdist. Third-party notices, terms and provenance matched
  source bytes in both archives. The new synthetic XYZ is included.
- Archive checks found no ignored local-note/manual-workspace directories,
  scientific binaries, bytecode or scanned private execution identifiers.
  Metadata, Requires-Python, console entry point and optional-only dependencies
  were checked. No whole-project license expression was added or inferred.
- Full source and extracted-sdist regression each passed **680 tests, none
  skipped**, on Python **3.12.16** in the development test environment. Version,
  compileall and maintained-text/link/whitespace checks passed.
- A fresh isolated environment installed only the wheel, without dependencies,
  Rich or Matplotlib. From outside the checkout with source import paths disabled,
  installed module location and distribution version, module/console CLI, public
  vibration selected fields, API/CLI publication, source/input fingerprints,
  replay and error codes were checked. GEO_OPT API/CLI parity and strict-report
  success/truncation behavior were retained. No CP2K calculation was launched.
- The official Multiwfn terms page was rechecked; the observed wording and limits
  are recorded in [terms](../third_party/multiwfn/TERMS.md). Preserving notices
  and citations does not grant extra permissions or establish license compatibility.

Artifact hashes and detailed build/install logs remain local operational records.
These checks establish package/install acceptance on the tested platform, not
publication or an immutable Git revision. Final verification does not substitute
for a release-owner decision about distribution terms and scope.

## Compatibility and remaining boundaries

Software remains the user-assigned 0.4.3; schema remains 0.1.0. Existing task
text defaults and parser-observation meanings are retained. New settings and
manifest keys are optional; absent displacement means auto. Non-null DX outside
the vibrational task must be explicitly reset. Earlier unreleased vibration
sidecars regenerate with the corrected MT/diagnostic presets rather than the
initial WAVELET text. No existing result is automatically repaired or replaced.

Not included: other functionals/open shells/SCF solvers, periodic phonons,
IR/Raman, thermochemistry, frequency parsing, imaginary-mode interpretation,
isotope controls, automatic optimization chains, scheduling or execution.
Stationarity, force/Hessian accuracy and basis/grid/DX/box convergence remain
system-specific scientific work. A generated manifest's validation flags remain
false; this is not an observed scientific result contract.

The declared minimum Python remains 3.10. After the initial grammar-only check,
a separately authorized controlled follow-up used Python 3.10.22 to install the
same wheel without dependencies. Installed core API/CLI, vibration contracts,
publication/replay/error checks and GEO_OPT parity passed. However, source and
original extracted-sdist suites each ran 680 tests with **one failure and three
skips**: the PTY preview test failed, while three Matplotlib tests skipped because
that optional dependency was deliberately not installed. This is not a passing
minimum-version full regression.

The PTY failure exposed a real presentation assumption: Python 3.10 can return
zero columns from shutil.get_terminal_size even with a fallback supplied; the
presenter then wrapped each character separately. A bounded standard-library
probe confirmed that behavior versus the positive fallback on Python 3.12.
That failed candidate remains historical evidence, not a passing regression.

A separately authorized minimal correction now falls back to 80 columns for
nonpositive presentation width. Positive detected/explicit widths, including a
one-column width, are preserved. A deterministic subtest matrix reproduces the
failure independently of interpreter version; the original real-PTY generation
test is unchanged. The nine focused presentation/interactive checks pass on both
Python 3.10.22 and 3.12.16. Full source regression runs **681 tests**: no failures
on either interpreter, with **three optional Matplotlib skips on core-only 3.10**
and **no skips on the 3.12 development environment**. No dependency was installed
to bypass a failure. Request validation, generated input, JSON/observation
contracts, exit codes, filesystem protection and schema 0.1.0 are unchanged;
this only corrects human-readable terminal presentation within user-assigned 0.4.3.

A fresh sdist and wheel built from that sdist also passed archive content/metadata/
privacy checks. Extracted-sdist regression matched the source results on both
interpreters (681 tests; three optional plotting skips on 3.10, none on 3.12).
Two fresh core-only environments installed the new wheel without dependencies;
from outside the checkout, installed API/CLI/contracts/replay/errors and all nine
presentation/interactive checks, including the real PTY, passed on each runtime.
Builds reused cached build requirements offline. Earlier candidate artifacts and
failure logs were preserved, not overwritten. This closes the observed Python
3.10 terminal-width runtime blocker within the tested core-only scope.

Isolated optional-extra installation and broader Python/OS combinations remain
unchecked. The earlier 0.4.2 packaging checks remain historical, not universal
compatibility or scientific validation.
No commit, tag, push, package-index upload or third-party licensing decision is
implied. Local notes and manual test workspaces stay Git-ignored; maintained
regressions, source references and required notices remain versioned.
