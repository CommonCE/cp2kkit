# Multiwfn module provenance

This records facts, not permission inferred from labels such as "reference-based"
or "rewritten in another language". Prefer version/file/subroutine/SHA-256;
line numbers are auxiliary. Do not invent upstream commits, inspection dates, or grants.

## CP2K input generation

### Location and fixed source

- Local module: `src/cp2kkit/inputgen.py`
- Interfaces: InputSettings, generate_input, write_input
- CLI: `src/cp2kkit/cli.py`, generate-input
- Upstream: Multiwfn 2026.10.1
- Package: Multiwfn_2026.10.1_src_Linux
- User-provided local path: `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`
  (development locator, not runtime dependency)
- File: cp2kmate.f90
- Main subroutine: outCP2Kinp, lines 68-3448
- Related inspection: outCP2Kinp_wrapper, determine_vacuumsize
- SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`
- Provenance/hash review (UTC): 2026-10-13
- Applicable terms: [TERMS.md](TERMS.md)

### Actual references

- Tasks and GLOBAL/FORCE_EVAL/DFT/SUBSYS/MOTION organization.
- MOLOPT-GTH names and selected Nval valence-count entries.
- PBE/BLYP GTH potentials and D3/D3(BJ) configuration.
- Some grid/SCF/optimization defaults; not every default is identical.
- Density extension inspected E_DENSITY_CUBE/STRIDE 1 branches, lines 2599-2641,
  retaining both citations. Spin applicability, final-step frequencies, and file
  behavior were separately checked against CP2K 2024.1-2026.2 documentation/source:
  [cube guide](../../docs/cube.md). cube.py streaming/difference logic was not ported
  from Multiwfn's cube implementation.

### Implementation and differences

- Python GPW subset, not a line-by-line port or strict clean-room implementation.
  Original Fortran is not distributed.
- Only ENERGY/ENERGY_FORCE/GEO_OPT/CELL_OPT, PBE/BLYP, restricted MOLOPT presets.
- Element/basis/potential names separately checked against CP2K headers; optional
  local data verification/hashing.
- Conservative PBC/electron/combination checks; exclusive creation/JSON provenance.
- OT inner/outer limits follow upstream's enabled-outer branch, 25/20, enabled by
  default locally. Smearing empty-orbital auto uses max(30,NINT(ncenter/2)), not fixed 20.
  Optimization steps, low-dimensional Poisson, and cell construction still differ.
- Restart settings are not inherited; rebuild KIND by element.
- Detailed differences belong in development conversation, not a separate comparison
  document. Actual scope: [generation guide](../../docs/input-generation.md).

### Citations and authorization

- Required papers: [notices](../../THIRD_PARTY_NOTICES.md).
- Preserved in module docstrings, generated inputs, and JSON.
- No separate header copyright/license statement was found in the inspected
  cp2kmate.f90; absence is not evidence of no copyright.
- No separate integration permission; relicensing/paid-distribution boundaries unconfirmed.
- Python implementation does not automatically remove upstream conditions.

### Validation boundary

- Synthetic unit/CLI smoke checks, no CP2K execution.
- Comparison is static inspection of identified source, not equivalent output/
  calculation testing between Multiwfn and cp2kkit.

## Input-generation editor

### Location and fixed source

- Local: `src/cp2kkit/input_tui.py`, run_interactive/Menu/GROUPS.
- CLI: generate-input --tui/--interactive; original arguments retained.
- Upstream: Multiwfn 2026.10.1, Multiwfn_2026.10.1_src_Linux/cp2kmate.f90.
- outCP2Kinp: main numbered menu approximately lines 194-375; return/other settings 389-445.
- Development locator: `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`, not runtime dependency.
- SHA-256: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Hash recheck (UTC): 2026-10-14; terms: [TERMS.md](TERMS.md).

### References and differences

- Repeated current-settings display, numbered editing, return, and final generation.
- Reimplemented using standard-library line interaction, not copied/distributed
  Fortran UI; no clean-room claim.
- Eight local groups with different numbering; only implemented GPW parameters.
- Retain local defaults, CLI seeds, source restrictions, scientific checks. Do not
  port all upstream options/session persistence/magnetic inference/automatic repairs/direct writes.
- Add previews, quoted replay commands, and default-no confirmation; no shell/CP2K execution.

### Citations, permission, validation

- Both papers remain in input_tui.py/shared input/JSON/notices.
- Original custom terms apply; no extra grant or confirmed relicensing boundary.
- Synthetic unit/CLI/PTY cases; no Multiwfn/CP2K execution or menu/result equivalence claim.

## Default entry and SCF/empty-orbital automatic values

### Location and source

- Local: cli.py, main_tui.py, input_tui.py, inputgen.py.
- Same Multiwfn 2026.10.1 cp2kmate.f90/outCP2Kinp;
  actually rechecked hash: `f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`.
- Lines 2437-2440: diag 128, enabled-outer OT inner 25; lines 2487-2492: outer 20.
- Lines 1124-1134: smearing on assigns nADDED_MOS=nint(ncenter/2D0), minimum 30;
  turning it off assigns 0.
- Terms/citations/authorization unchanged: [TERMS.md](TERMS.md).

### Use and differences

- Use these formulas; Python (natoms+1)//2 implements Fortran positive half-integer rounding.
- Reference load-then-numbered-menu organization; application dispatch is locally
  implemented for existing functions.
- Not a complete menu/reader port. GJF/CIF/POSCAR are local strict standard-library
  readers, without referencing/distributing Multiwfn reader source.
- UKS dual-spin organization from lines 2525-2529 also used; ADDED_MOS integer-array/
  per-spin meaning separately checked in CP2K 2026.2 SCF documentation linked in the guide.
- Auto applies only to diag+smearing without explicit override. OT rejects smearing/
  nonzero empty orbitals instead of switching to diag. Auto follows current structures,
  not upstream session assignments.
- 400/55 Ry is the user's request, not claimed upstream provenance or system convergence.
- Application/dynamic hiding/auto checks are synthetic; no Multiwfn/CP2K run or full
  behavior-equivalence/scientific-sufficiency claim. Shared generator retains both citations.

## Template for future features

Copy this structure for each referenced feature and supply evidenced facts.
Register other authors' code separately and preserve notices.

```markdown
## <Feature>

### Location and fixed source
- Local module/function:
- Upstream version/package:
- Upstream file/subroutine:
- Source SHA-256 or an actual upstream commit:
- Registration/recheck date:
- Applicable terms:

### Actual references
- <Algorithm, workflow, tables, defaults, or code portions actually used>

### Implementation and differences
- <Reference-based implementation, rewrite, or direct port; no automatic exemption>
- <Behavior differences and verification sources>

### Citations and authorization
- <Citation/copyright preservation locations>
- <Additional method papers>
- <Separate grants, actual evidence/scope, or explicitly unknown>

### Validation boundary
- <Tests/unverified items; requested outcomes are not verified results>
```
