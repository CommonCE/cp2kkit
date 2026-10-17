# Orbital basis registry (0.2.6, registry v1)

The registry establishes the numbering contract **toward 1.0.0**; it does not
release 1.0.0 or certify calculations. The main editor still has one scrolling
settings list. Selecting its field **2** opens one grouped basis-value list,
not a category-selection page. No full-screen UI is used.

## Permanent number contract

Display number, display order, stable string ID and actual library alias are
separate. Assigned numbers never change meaning and are never recycled, even if
an entry becomes unavailable or retired. New families use unallocated numbers
within their intended range; tombstones retain their IDs/numbers. Sorting and
`/text` filtering never renumber entries. Number **0** returns without changing
the basis; Enter keeps it. This differs from main-editor 0 (review/generate).
CLI/config/replay use semantic string IDs, not menu positions. Legacy family
names remain accepted on input. The default remains DZVP-MOLOPT-SR-GTH.

| Number | Stable ID | Family / status |
|---:|---|---|
| 1 | molopt-sr-szv | SZV-MOLOPT-SR-GTH |
| 2 | molopt-sr-dzvp | DZVP-MOLOPT-SR-GTH (default) |
| 3 | molopt-tzvp | TZVP-MOLOPT-GTH |
| 4 | molopt-tzv2p | TZV2P-MOLOPT-GTH |
| 5 | molopt-tzv2px | TZV2PX-MOLOPT-GTH |
| 6 | molopt-szv | SZV-MOLOPT-GTH |
| 7 | molopt-dzvp | DZVP-MOLOPT-GTH |
| 8 | molopt-sr-tzvp | TZVP-MOLOPT-SR-GTH, UCL extension |
| 9 | molopt-sr-tzv2p | TZV2P-MOLOPT-SR-GTH, UCL extension |
| 10-19 | Unallocated | Reserved, not selectable |
| 20 | uzh-pbe-dzvp | DZVP-MOLOPT-PBE-GTH, paired UZH-PBE |
| 21 | uzh-pbe-tzvp | TZVP-MOLOPT-PBE-GTH, paired UZH-PBE |
| 22 | uzh-pbe-tzv2p | TZV2P-MOLOPT-PBE-GTH, paired UZH-PBE |
| 23-29 | Unallocated | Reserved, not selectable |
| 30 | uzh-pbe0-dzvp | DZVP-MOLOPT-PBE0-GTH, unavailable |
| 31 | uzh-pbe0-tzvp | TZVP-MOLOPT-PBE0-GTH, unavailable |
| 32 | uzh-pbe0-tzv2p | TZV2P-MOLOPT-PBE0-GTH, unavailable |
| 33-39 | Unallocated | Reserved, not selectable |
| 40-59 | Unallocated | Traditional GTH, reserved |
| 60-79 | Unallocated | ccGRB / cc, reserved |
| 80-99 | Unallocated | Other pseudopotential bases, reserved |
| 100-199 | Unallocated | All-electron bases, reserved |
| 900 | custom-orbital | Explicit pseudopotential ORB file and real name |

Numbers outside these entries are not selectable. Disabled PBE0 entries are
shown with an explicit UNAVAILABLE reason, not advertised as working templates.
ORB, AUX_FIT and RI_AUX are distinct roles in the model; only ORB is selectable.
No auxiliary basis, hybrid/HF/ADMM, RI or all-electron method template is added.

## Data and coverage

Default target is CP2K 2026.2. New families/protocols require this target; original
PBE/BLYP/core-family requests retain their older target profiles. The 71-element
fixed-valence policy is unchanged: no arbitrary elements, q changes, inferred spin,
or numerical resets. A basis family is not a universal accuracy ranking.

| Families | Matching current fixed-q elements | Sources |
|---|---:|---|
| SZV-SR / DZVP-SR | 71 each | BASIS_MOLOPT; UCL adds other elements/q, not automatic preset extensions |
| SZV non-SR | 9 | BASIS_MOLOPT |
| DZVP non-SR | 11 | BASIS_MOLOPT + UCL Cu/Br |
| TZVP/TZV2P/TZV2PX non-SR | 10 each | BASIS_MOLOPT + UCL Br |
| TZVP-SR / TZV2P-SR | 54 each | BASIS_MOLOPT_UCL; no H/C/N/O; Mg-q2 is not Mg-q10 |
| UZH-PBE DZVP/TZVP/TZV2P | 71 each | BASIS_MOLOPT_UZH_2026.2 + POTENTIAL_UZH_2026.2 |

UZH-PBE is restricted to **PBE** and selects the paired UZH potential, not classic
GTH_POTENTIALS merely because names/q match. Real `*-MOLOPT-GGA-GTH-qN` aliases
are accepted when present. Reference hashes recognize a known incompatible classic
potential source and reject it for UZH. Unrecognized explicit UZH file bytes have
unverified physical pairing, even when selected-entry structural/q checks pass.
Classic/UCL and UZH potential libraries are not silently exchanged.

PBE0-family headers exist, including HYB aliases, but no hybrid calculation
template exists. The pinned UZH basis file has the literal anomalous header
`a TZV2P-MOLOPT-PBE0-GTH-q10 TZV2P-MOLOPT-HYB-GTH-q10` at line **5614**.
Do not infer/repair Ca from the preceding comment; this family has only 70 current
preset-element headers rather than 71. POTENTIAL_UZH also has 30 PBE `NA`
placeholder entries (for other q variants); these are not numerical potentials
and are excluded from enabled PBE catalog coverage. All 71 requested PBE q pairs
were separately parsed successfully for each of the three enabled families.
PBE0 numbering stays allocated but unavailable; header presence is not validation.

Source bytes inspected, not bundled coefficients/parameters:

- [UZH basis](https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/BASIS_MOLOPT_UZH_2026.2):
  SHA-256 `8ca617142cc73b02e47d5806d97e91d2c3312444c411c5a093f4dfe8fb9355c4`.
- [UZH potential](https://raw.githubusercontent.com/cp2k/cp2k/v2026.2/data/POTENTIAL_UZH_2026.2):
  SHA-256 `8ab49093391f67f2705679f0b3bfc5b84bbeb4003955b556ded322e9d1d6093d`.
- Classic/UCL and keyword source URLs/hashes remain in `data_catalog.py`.
  v2026.2 `input_cp2k_dft.F` lines 134-147 allow repeated BASIS_SET_FILE_NAME
  but only one POTENTIAL_FILE_NAME. Mixed requests requiring different potential
  files are rejected; no synthetic merged library is silently written.

## Source selection, checks and ambiguity

Explicit `--basis-file` / `--potential-file` options select authoritative files;
repeat them for multiple sources. Otherwise use `--data-dir`, then the actual
`CP2K_DATA_DIR` environment directory if set. With neither, pinned catalog
metadata can produce an **unverified template**, not an installed-data-checked input.
No data are downloaded and CP2K is never invoked by generation.

```bash
cp2kkit generate-input solid.extxyz -o new.inp --basis uzh-pbe-tzvp \
  --data-dir /path/to/cp2k/data
# File names may differ from library defaults; select their actual content explicitly.
cp2kkit generate-input water.xyz -o new-checked.inp --periodic NONE \
  --basis molopt-sr-dzvp --basis-file '/path with spaces/orbital.dat' \
  --potential-file /path/to/potentials.dat
```

Versioned and generic UZH library filenames are searched within a directory;
symlinks resolve to real targets. Names, aliases, q suffixes, potential occupations,
selected basis exponent/contraction blocks and supported GTH channel/matrix
structure are parsed from actual bytes. Header-only, partial, non-finite,
conflicting-q and selected NA payloads are errors. Unused blocks are indexed, not
claimed to be fully validated. Unrecognized unused headers are recorded without
repair and warned about. For q-less custom bases, q is **unknown**, never inferred
from the element or selected potential; the output remains an unverified template.

Differing entries sharing an applicable alias are ambiguous (exit 3), not resolved
by path order. Identical entries can be treated as equivalent, and real-path file
references are deduplicated. The final union of emitted libraries is checked for
cross-KIND alias shadowing, including generic aliases that would select a different
q variant. Select one source explicitly, or a real unambiguous q-qualified alias.
Missing items list elements/KIND groups, required q, files and catalog alternatives;
alternatives still require file checks and are **never applied automatically**.
Element overrides accept stable IDs or legacy names and apply to all split KINDs.

The basis-value editor has `d` (data directory), `b` (one explicit basis file),
`v` (one explicit potential file); `auto` clears that override. CLI/API support
multiple files. These source edits are retained without changing the selected
family or physical settings. They do not add numbered basis choices.

## Custom 900

Choose 900 and enter an ORB file and an **existing literal name/alias**. Optionally
enter both a potential file and real name; `auto` uses the matched default
potential policy. Abandoning the custom prompts preserves the previous draft.
The same parser, alias/q checks, ambiguity errors and protected writer are used.

```bash
cp2kkit generate-input water.xyz -o custom-new.inp --periodic NONE \
  --basis custom-orbital --custom-basis-file /path/to/orbital.dat \
  --custom-basis-name MY-ORB \
  --custom-potential-file /path/to/potential.dat --custom-potential-name MY-POT
```

Each requested element needs the real aliases in those files. There are no wildcard
renames or template `-qN` inventions. Custom 900 is a user assertion of a
**pseudopotential ORB** role; generic names do not prove functional/physical
compatibility. Recognized all-electron/auxiliary requests are rejected, unknown
basis q remains unverified, and all custom physical pairing remains user-specified.
An orbital file name alone cannot establish its role or methodological suitability.

## Configuration migration and provenance

Old JSON/settings used family **names** and remain accepted. `settings.basis` and
basis-override values now serialize stable IDs; basis_selection adds registry
version/number/ID, and each KIND records its final real names, number/ID, role/type,
q and origin. Existing analysis JSON/CSV contracts are unchanged; schema remains
0.1.0. Consumers of generator settings must accept the documented new ID values.

**Old list positions are not registry numbers.** In the earlier pre-registry
0.2.6 editor (commit `229d09d`), UI 3 meant DZVP non-SR,
4 TZVP, 5 TZV2P, 6 TZVP-SR, 7 TZV2P-SR and 8 TZV2PX. Those positions were not a
persisted numeric config contract. Never interpret an old saved integer silently:

```python
from cp2kkit.inputgen import InputSettings
old = InputSettings.from_config({'basis': 3, 'periodic': 'NONE'}, source_version='0.2.6')
assert old.basis == 'molopt-dzvp'       # New registry 7, NOT new registry 3.
# Old names need no version hint. Generator sidecars can also be loaded directly.
settings = InputSettings.from_config({'basis': 'TZVP-MOLOPT-GTH'})
```

This feature stays in software **0.2.6** at the user's request. Registry version
**1**, not software 0.2.6 alone, identifies the new contract. Registry-v1 sidecars
must contain string IDs; numeric values are rejected even with a legacy version hint.
Explicit numeric migration supports inspected legacy 0.2.4/0.2.5/0.2.6 tables; absent or
unsupported numeric versions are errors. CLI `--basis 3` is rejected; use an ID
or legacy name. New JSON/replay never depends on display positions.

Before interactive write confirmation, review shows every KIND, final basis and
potential, basis/occupation-derived potential q, source path/line/hash/version,
approximation and pairing status. Source evidence includes requested paths,
resolved real paths, raw-byte SHA-256/size and entry fingerprint. A data version is
identified only by exact pinned reference bytes, **not a filename or symlink name**;
otherwise it is null/unknown. Provenance stays in JSON/review, not verbose input comments.

`basis_validation.status` is `data_checked` only when both selected files and q
matching have been checked, otherwise `unverified_template`. This covers selected
entry structure/alias/q/bytes only, not whole-library validity or physical pairing.
`protocol_pairing` distinguishes a recognized UZH reference pair, unknown UZH
pairing, classic-family selection and custom user assertions. Runtime/build and
`runnable_verified` flags remain false: **only actual authorized CP2K execution can
establish native acceptance**, and even that would not establish convergence or
scientific suitability. No such execution was performed for this feature.
