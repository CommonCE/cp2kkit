# 0.4.4 closeout: molecular vibrational output parsing

The bounded **0.4.4 development stage is complete**. This is a source-tree
acceptance record, not a package release or scientific certification. The
exchange schema remains **0.1.0**.

## Delivered scope and compatibility

- Read-only observation of CP2K 2026.2 molecular Cartesian normal-mode tables.
  Python, `cp2kkit vibration` and application menu 7 share the parser and
  deterministic JSON/CSV export. Signed frequencies, original tokens, units,
  source hash and line evidence are preserved. Incomplete tables retain usable
  observations; multiple candidates require explicit selection.
- The threshold changes reporting categories only, not values or raw negative
  counts. `--strict` checks textual completeness, recognized version/task and
  the selected segment's end marker; explicit exports are exclusive.
- Main entries 1–4 and generator setting 640 are unchanged. Quality moved to
  **5/1**, CUBE checking to **6/1**, and old main-7 density subtraction to **6/2**;
  main **7** now opens vibration directly. Existing batch commands, generation
  defaults and GEO_OPT field meanings are unchanged. Vibrational output is a
  separate exchange operation, not a field in a generator manifest or GEO_OPT run.

Use the [result contract](vibration-results-contract.md),
[synthetic example](../examples/vibration-results/README.md) and
[menu migration](menu-numbering-draft.md#application-workflow-layout-044).

## Acceptance evidence

| Linux interpreter | Focused tests | Full source regression |
|---|---:|---:|
| Python 3.12.16 | 97 passed | 696 passed |
| Python 3.10.22 | 97 passed | 693 passed, 3 optional Matplotlib skips |

Both interpreters passed compileall, CLI version and real-PTY checks (including
narrow and unsized terminals). Maintained-text, local-link and whitespace checks
passed. No CP2K executable or cluster output is needed for the public test suite.

Two existing CP2K 2026.2 water output files from the prior input-generation stage
were retrieved read-only and checked against their source hashes. They cover the
same system and settings with native vibration diagnostics enabled and disabled,
not two independent molecular systems. Both passed strict text checks. The
Python and CLI reports agreed, and all three frequencies agreed with the
respective Molden `[FREQ]` records at the Molden printing precision.

Separate, deliberately modified **local copies** checked error handling:

- Concatenation returned ambiguity (exit 3); explicit selections `1/1` and `2/1`
  both recovered their original tables.
- A threshold equal to the smallest printed frequency classified one mode as
  near-zero while preserving all printed frequency tokens.
- Truncation retained already printed frequencies and returned strict exit 7.
  An overflow placeholder in mode 2 retained modes 1 and 3 without inserting a
  zero, also returning strict exit 7.
- Attempts to overwrite an existing CSV or the source returned exit 5; the
  existing bytes were preserved.

Private outputs, hashes and execution identifiers remain in ignored local
records. No new calculation, scheduler submission or cluster modification was
performed for this validation.

## Outside this closeout

The tests establish parsing and text-report behavior, not force or frequency
convergence, geometry/energy association, stationarity, a clean process exit,
or broader CP2K version/format coverage. The existing native cases are not a
scientific reference spectrum. Thermochemistry, periodic phonons and broader
native-format fixtures remain separate work. Formal packaging and installation
checks are deferred to 0.5; this record does not establish publication, a Git tag
or a specific immutable revision. See the [handoff](development-handoff.md) for
follow-up priorities.
