# GEO_OPT observation contract (software 0.4.2)

This batch stabilizes observations and their provenance, not a final-state or
scientific-validation API. New regressions use tiny hand-written strings in
`tests/test_geo_opt_contract.py` and `tests/test_output_settings.py`, not real
calculation outputs. This generic contract serves independent downstream
consumers through the public Python API and CLI; it is not a private workflow
model. It does not require a consumer repository, database, credentials or scheduler.
See the [producer/consumer responsibilities](architecture.md#producer-and-consumer-responsibilities).

## Baseline scope and status

The implemented 0.4.2 observation semantics below are the compatibility baseline:
legacy field meanings are retained; new evidence/settings fields are optional for
readers of older exports. The public
[synthetic example](../examples/geo-opt-contract/README.md) provides a tested
selected-field expectation and Python/CLI parity checks. It is not native output
validation or a complete machine-readable schema.

The [0.4.2 closeout](closeout-0.4.2.md) completes the observation-contract stage,
including isolated sdist/wheel and core-only installed API/CLI checks on Python
3.12.16. This is not an immutable release checkpoint or a promise that final-state
capabilities exist. A reproducible downstream dependency needs an explicitly
identified code revision or artifact hash, not only a version string. Publication,
commit/tag creation and broader Python/OS compatibility require separate checks
and authorization.

The contract covers documented field meanings/types, units, indices, null/status
semantics and evidence provenance. It does not freeze exact diagnostic prose,
dictionary key order or a closed list of fields. Supported text-quality fixes can
change positive judgments and must be documented; they do not authorize silently
changing observations into final results. Downstream compatibility tests belong
to downstream consumers, not this producer's test suite.

## Public calls

```bash
cp2kkit --version
cp2kkit parse /absolute/path/run.out --format json
cp2kkit report /absolute/path/run.out --strict
```

Source-tree equivalent: `PYTHONPATH=src python -m cp2kkit ...`.
Parse command success means export succeeded, not calculation convergence.
`report --strict` returns 7 when supported text-quality checks do not pass.

```python
from cp2kkit.parser import parse_output
from cp2kkit.quality import quality_report

run = parse_output('/absolute/path/run.out')
data = run.to_dict()
quality = quality_report(run)  # CLI parse embeds this as data['quality']
for segment in run.segments:
    observation = segment.last_observed_energy  # Energy or None
    # observation.quantity is the legacy segment.final_energy Quantity.
```

The following is a selected-field illustration, not a complete JSON document or
real result. Read the actual source/hash/evidence fields from the export; do not
substitute example values:

```json
{
  "schema_version": "0.1.0",
  "parser": {"name": "cp2kkit", "version": "0.4.2"},
  "software": "CP2K",
  "software_version": "synthetic",
  "exit_status": null,
  "segments": [{
    "id": 0,
    "completed": true,
    "scf_converged": true,
    "geometry_converged": true,
    "last_observed_energy": {
      "segment": 0,
      "index": 1,
      "step": 1,
      "scf_converged": true,
      "scf_association": "preceding_summary"
    },
    "unparsed_energy_records": [],
    "unparsed_energy_context": []
  }]
}
```

## Versions and compatibility

- Tool version: `cp2kkit --version`, Python `cp2kkit.__version__`, and parse JSON
  `parser.version`. Software 0.4.1 -> 0.4.2 follows the user's explicit version
  assignment for this round (superseding the unpublished 0.5.0 proposal).
  It is not publication or native CP2K certification.
- Exchange version: `schema_version`, still 0.1.0. Additive optional fields follow
  the existing schema convention; consumers must ignore unknown fields and
  tolerate their absence from earlier producers.
- `software_version` is the parsed CP2K version string, not the toolkit version;
  it can be null or an unverified synthetic label.
- Renames, removals or incompatible field meanings require a separate schema
  version decision, documented migration and compatibility tests, not a silent
  reuse of 0.1.0. Software version is assessed independently (major changes
  require the user's explicit decision). No such breaking change is made here.
- Old fields and CSV columns are retained. Conservative bug fixes can reduce
  positive quality: ambiguous summaries now block energy_usable; SCF evidence
  consumed by a damaged record is not reused; damaged records after termination
  belong to a new incomplete segment.

## Selected field types and index conventions

This table describes actual exports, not a requirement that older producers emit
newer optional fields. `Evidence` is an object with path (string), line (1-based
integer) and text (string). `Quantity` has value (finite number), unit (string) and
source (Evidence). JSON booleans are not numeric flags.

| Field | JSON type / convention |
|---|---|
| parser | Object with name/version strings; added in 0.4.2 |
| software_version, project | String or null |
| exit_status | Null in current parser; no process outcome inferred |
| source | Object with resolved path string, sha256 string and size_bytes integer |
| segments | Array in file order; id is a zero-based integer |
| started, completed | Boolean marker observations |
| scf_converged, geometry_converged | Boolean or null |
| energies | Array of Energy objects; index is one-based within a segment |
| Energy.step | Explicit integer step or null; not derived from index |
| Energy.step_source, Energy.scf_source | Evidence or null |
| Energy.scf_evidence | Array of Evidence |
| Energy.scf_association | preceding_summary, ambiguous or unknown string |
| last_observed_energy | Energy object or null; same observation as energies[-1] when present |
| final_energy | Quantity or null; legacy last parsed observation |
| settings_records, unparsed_energy_context | Arrays of objects described below |
| normalized_settings | Object of independent field objects; value/unit/status/sources as described below |

Dictionary key order and whitespace are not semantic. Evidence paths are producer
file locations, not downstream object IDs or portable file-access grants. Consumers
must preserve units and must not infer a continuous time/step axis across segments.

## Unknown, absent, false and empty

- Missing field: producer may predate the addition; not proof of a negative.
- `null`: unknown/unavailable value or unavailable unique association, never zero.
- Numeric zero: an observed value, including zero energy; do not test truthiness.
- `scf_converged=false` and `geometry_converged=false`: explicit failure evidence.
  Null is unknown; geometry null is not a geometry pass.
- `started/completed=false`: marker not observed, not a known process failure.
  True means the corresponding marker was observed, not a process exit code.
- Empty evidence/record lists: no such records recognized, not proof none occurred.
- Empty raw settings dictionaries: no settings captured in that scope, not defaults.
  Normalized fields use status=missing/value=null/sources=[] for absent evidence.
- `quality.*.energy_usable=false`: supported text checks did not all pass, not
  proof that the numerical observation is absent or scientifically incorrect.

## Energy and line evidence

`source` retains absolute resolved path, raw-byte SHA-256 and size_bytes. Evidence
retains path, 1-based line and original text. Segments are 0-based; parsed energy
indices are 1-based within each segment. Non-increasing step numbers/start markers
split segments without inferred restart continuity. No segments are joined.

- `energies`: every supported finite numeric observation, in file order. Quantity
  contains value, unit=hartree and source. Only explicit a.u./hartree labels are
  supported. Index is not an optimization step or elapsed time.
- `step`: explicit most recent step marker in this segment, or null. It is a text
  association, not proof of a particular optimizer's evaluation ordering.
  `step_source`: that marker or null. No increment or implicit step zero.
- Legacy `scf_converged`: last pending SCF summary flag consumed by this energy,
  or null; retained for compatibility. It alone is insufficient when association
  is ambiguous. Each step/segment boundary clears pending summaries.
- `scf_evidence`: summaries after the previous energy record or current boundary,
  before this energy. `scf_source` is the sole summary only when exactly one was
  observed. `scf_association` is preceding_summary for one, ambiguous for several,
  unknown for none. This is lexical evidence, not certification of all CP2K SCF,
  outer-loop, line-search or FORCE_EVAL layouts. No engine identity is invented.
- `last_observed_energy`: full last parsed Energy, or null; the Python object
  refers to the same observation in energies. It includes segment/step/SCF context.
- Legacy `final_energy`: that observation's Quantity, or null. The name is retained
  without changing its meaning. It is NOT necessarily final optimized energy.
- `unparsed_energy_records`: unchanged raw evidence for damaged/unsupported lines.
  `unparsed_energy_context`: parallel ordered records with segment, nullable step,
  nullable step_source, source, scf_evidence and reason=unsupported_or_malformed.
  Pending SCF summaries are consumed even by these records. Warnings retain line
  locators. No invalid value becomes zero or replaces the last good observation.
- Numeric overflow such as 1e999 retains the existing hard ParseError / CLI exit 4
  behavior (no partial JSON export), rather than serializing Infinity. Malformed
  tokens including NaN/Inf remain unparsed evidence under the existing matcher.

No final_candidate_energy is implemented. Completion + the last number, even with
positive text quality, does not establish a final energy. Truncation, a damaged tail,
unknown step/evaluation ordering or ambiguous SCF must not be promoted downstream.
Final-candidate criteria and optimizer-specific ordering support remain follow-up.

## State axes

Keep segment.completed (end marker), segment.scf_converged (latest summary or
step/reset unknown), per-energy SCF association, segment.geometry_converged,
observation availability and quality.energy_usable separate. Step exhaustion
records geometry=false even if a generic completion line also appears. Historical
SCF failures remain visible and block positive quality. No energy => observation
null, independent of termination/convergence markers.

Quality `passed` means only the supported text rules passed; it does not certify
final-state ordering, method choice, physical model, numerical convergence studies
or chemical correctness. Process `exit_status` remains null. Neither PROGRAM ENDED
nor absence of fatal diagnostics establishes a process exit or restart continuity.

## Normalized settings

Raw segment.settings retain strings, nullable units and source lines, without
cross-segment inheritance. Top-level settings is the existing empty placeholder.
New settings_records preserves every setting recognized by the existing matcher,
including repeated keys; legacy settings still has its existing last-write behavior.
The software_version entry remains separate, not a synthetic setting record.

`segments[].normalized_settings` provides independent fields, each with value,
unit, status and sources. No input defaults are used. For example, selected fields
for explicit charge=0 and a printed UKS branch could be:

```json
{
  "charge": {"value": 0, "unit": "elementary_charge", "status": "parsed"},
  "multiplicity": {"value": null, "unit": "dimensionless", "status": "missing"},
  "spin_treatment": {"value": "UKS", "unit": null, "status": "parsed"},
  "uks": {"value": true, "unit": null, "status": "parsed"},
  "qs_method": {"value": null, "unit": null, "status": "missing"}
}
```

This illustration omits sources. Actual exports contain source arrays with path,
line and original text; missing fields have sources=[]. Python access is
`run.segments[0].normalized_settings['charge']['value']`.

Supported mappings are deliberately narrow:

| Printed label/value | Normalized field | Meaning |
|---|---|---|
| DFT\| Charge / integer | charge | Total printed charge, in elementary positive charges; +1 means one electron removed |
| DFT\| Multiplicity / positive integer | multiplicity | Printed multiplicity; not measured magnetization or electron-number difference |
| DFT\| Spin unrestricted (spin-polarized) Kohn-Sham calculation / UKS | spin_treatment=UKS, uks=true | Explicit unrestricted branch |
| DFT\| Spin restricted Kohn-Sham (RKS) calculation / RKS | spin_treatment=RKS, uks=false | Explicit restricted branch |
| DFT\| Spin restricted open Kohn-Sham calculation / ROKS | spin_treatment=ROKS, uks=false | Restricted-open branch; false does not mean RKS |
| QS\| Method: / GPW or GAPW | qs_method | QS representation only, not functional/complete method |

Labels and tokens must match the supported spelling; no case, alias, numeric-prefix
or unit guesses. Charge accepts signed integer tokens (not 0.0); multiplicity must
be positive. Other tokens/representations remain unsupported, including NaN/Inf.

Per-field status:
- missing: no recognized matching records; value=null. This does not prove the
  output supplied no setting in an unrecognized format.
- parsed: all matching records are valid and agree; repeated agreeing sources
  are retained. Actual zero and false remain meaningful values.
- conflicting: more than one distinct supported value; value=null, all sources
  retained, no last-write choice.
- unsupported: some matching value cannot be interpreted, without a known-value
  conflict; value=null even if another matching record is valid.

uks uses the same explicit spin-branch evidence/status as spin_treatment, never
multiplicity, number of spin states, magnetization or electron counts. Label/value
mismatches are unsupported. Different spin branches conflict even if both would
imply uks=false. Unsupported/conflicting fields generate line-located warnings.
Normalized settings are segment observations, not a proof they apply uniformly to
every energy or FORCE_EVAL. Multiple distinct blocks are not merged into a global
physical identity. Settings after an end marker start a new incomplete segment.

No complete method, XC assembly, dispersion/HFX model, magnetization or electron
number difference is normalized here. A single XC label stays raw. Setting conflicts
do not change existing quality.passed rules: those assess termination/convergence
text, not model identity or scientific fitness. Consumers must examine the independent
setting statuses before using them as method/state identifiers.

### Source-format reference and test boundary

Labels and meaning were checked against tagged
[CP2K v2026.2 cp_control_utils.F](https://github.com/cp2k/cp2k/blob/v2026.2/src/cp_control_utils.F):
write_dft_control lines 2333-2350 (explicit uks/roks/else branch, multiplicity, charge)
and write_qs_control lines 2844-2858 (QS METHOD enumeration and printing).
Retrieved raw source SHA-256:
`da04a34bb800c6ccc9314a9e434abca7b0f1482a250f1672bb0cd27adff6aa39`.
The source was inspected, not copied into fixtures or deployed as a dependency.

`tests/test_output_settings.py` uses hand-written short lines with matching printed
labels/spacing. This is tagged-source-informed format regression, not native output
execution, complete legacy-version support, or scientific certification. Older
fixtures' illustrative version strings do not expand the checked source scope.
Broader mappings require separately evidenced formats/tests.

## Structure association: explicit follow-up

The existing public `structure.read_structure(path, frame=...)` / `read_xyz`
interface is suitable for explicitly selected XYZ/extXYZ candidate geometry:
source path/hash/size and selected line range, zero-based frame, angstrom positions,
cell and PBC are exported independently. Plain XYZ cell/PBC can be null. A frame
index is not an optimization step. Current readers do not expose CP2K trajectory
comment step/energy semantics or output-to-frame association evidence. Selecting
frame=-1 or matching a filename does NOT establish final optimized structure.

No structure argument, automatic neighbor-file discovery, linked/final structure
field or generic association framework is added. Consumers may retain an explicitly
selected independent candidate via the existing interface but must label its output
relationship as unestablished. Follow-up must preserve comment/step/unit evidence,
segment identity and matching criteria before claiming final structure. Existing
structure parsing is not changed merely to satisfy a field checklist.

## Consumer migration checklist

1. Keep existing CLI calls. Read tool identity separately from CP2K/schema versions.
2. Prefer last_observed_energy when available; for 0.4.1 derive only an observation
   from energies[-1]/final_energy, with new evidence fields unknown. Do not relabel
   historical final_energy as a final optimized result.
3. Inspect segment/step/evidence and scf_association, damaged records and warnings;
   keep each segment independent. Never use only the last number or end marker.
4. Persist convergence axes independently; quality is a conservative text judgment,
   not scientific correctness. Preserve null and actual zero.
5. Read normalized settings only when each field has status=parsed. Treat fields
   absent from older producers as unknown; preserve unsupported/conflicting status
   and source evidence. Do not use qs_method as a full method identifier or assume
   quality.passed establishes setting/model identity.
6. Keep persistence, internal run/artifact links, import policies and private-model
   mappings on the consumer side. cp2kkit adds no consumer-specific database fields,
   primary keys, ledger dependencies or business states.
