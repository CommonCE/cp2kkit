# Public consumer contracts

These contracts serve independent callers through the existing Python API, CLI
and exchange files. External consumers (including chemops) own adapters, storage,
internal identifiers and execution policies. No consumer repository, database,
scheduler or credentials are required to use or test cp2kkit.

## Contract entry points

| Surface | Authoritative description | Executable baseline |
|---|---|---|
| Exchange conventions and field meanings | [Schema](schema.md) | Feature tests; not a complete JSON Schema validator |
| GEO_OPT observations | [Observation contract](geo-opt-contract.md) | [Synthetic observation example](../examples/geo-opt-contract/README.md) |
| Molecular vibrational input generation, software 0.4.3 | [Generation contract](vibration-contract.md) | [Synthetic generation example](../examples/vibration-contract/README.md) |
| Other generated-input behavior | [Input generation](input-generation.md) and its feature sections | Existing feature tests; no blanket claim of complete consumer-contract coverage |

Use a documented contract plus its referenced feature rules, not an example alone.
A selected-field expectation is neither a full export nor an accepted request.
An input-generation manifest describes a proposed calculation, not observations
from an executed calculation. Do not interchange it with parser output merely
because both use schema_version 0.1.0.

## Shared caller rules

- Toolkit identity, exchange version, target software/version and observed runtime
  software/version are different. A toolkit version alone does not identify an
  immutable worktree; pin an explicit revision or artifact when reproducibility
  requires it. Contract documentation does not create a new runtime version key.
- Output readers tolerate additional fields and absent newer optional fields.
  Missing and null are not zero or false. Booleans are not numeric flags; retain
  units, field meanings and independent validation/status axes.
- Tolerance of unknown output keys is not permission to pass arbitrary options
  to Python constructors, configuration loaders or CLI parsers. Use supported
  request fields; feature contracts describe actual validation limitations.
- Preserve original source identities and distinguish source geometry from
  generated geometry. Producer paths are provenance, not portable access grants
  or downstream artifact IDs. Relocating/rebasing files can require regeneration
  and new fingerprints; never relabel an old hash as identifying edited bytes.
- Exact warning text, JSON key order and CLI progress prose are not machine
  interfaces. Use documented exceptions/exit codes and read the documented JSON
  artifact when one is requested. No structured diagnostic-code API is implied.
- Generation success, keyword checks, native execution, electronic/geometry
  convergence and scientific validity remain separate. Neither an end marker
  nor a generated manifest establishes a process exit or a valid scientific result.
- Filesystem effects and overwrite exceptions are feature-specific: analysis
  exports are exclusive, while ordinary input generation may replace a regular
  .inp under its protection rules. There is no universal atomic multi-file or
  automatic-execution guarantee. See each operation's contract.

## Contract maintenance policy

For a user-visible feature/fix, assess request, response and side-effect changes
before declaring completion. Update the smallest relevant existing contract,
schema section and tests; create a focused new contract/example only when it
provides a useful consumer boundary. Internal-only refactors may require no
contract edit, but should retain behavioral regression coverage.

A useful feature contract states public entry points, supported scope, parameters
and units/defaults, output types/absence/provenance, errors, file effects, replay
and compatibility, and what success does not prove. Prefer links to one maintained
scientific policy over duplicate validation tables. Do not invent a capabilities
endpoint, request schema, output field or workflow feature merely to fill a template.

Evaluate software and exchange versions independently. Optional additive output
fields need not bump the exchange schema; removed/renamed/reinterpreted fields
need an explicit compatibility/migration decision. Defaults and rejection-scope
changes also need behavioral migration notes even if no JSON shape changes.
Do not change the manually controlled software major version without permission.

Use public, tiny synthetic examples with selected-field/type expectations and
actual API/CLI/config/error/file-protection tests where applicable. Tests must be
independent of downstream/private data and never launch scientific calculations.
Consumer adapters need their own compatibility tests; producer tests do not
certify that any particular external consumer has integrated the feature.

The reusable [contract prompt](../.agents/prompts/maintain-contract.md) and
[development rules](../.agents/DEVELOPMENT.md) define the implementation workflow.
Machine-specific diagnostics remain in ignored local notes or outside Git;
scientific runtime checks require separate authorization.
