# Prompt: implement GEO_OPT/CELL_OPT convergence criteria and trajectory-step association for 0.4.9

Work in the `cp2kkit` repository (`/home/xwp/git/cp2kkit`). Implement the bounded
**0.4.9** stage covering (1) read-only CP2K `GEO_OPT` / `CELL_OPT` convergence
criteria observation and (2) explicit, evidence-based association between parsed
optimization steps and trajectory structure frames.

Use English for maintained development text, code, CLI/TUI messages, comments,
and tests unless the user explicitly requests another communication language.
Preserve original scientific keywords, source quotations, units, paths, and user
data verbatim.

## 1. Establish the actual baseline first

Before editing any file, read:

- [AGENTS.md](../../AGENTS.md) and [DEVELOPMENT.md](../DEVELOPMENT.md)
- [README.md](../../README.md), [pyproject.toml](../../pyproject.toml), and
  [docs/architecture.md](../../docs/architecture.md)
- [docs/contracts.md](../../docs/contracts.md), [docs/schema.md](../../docs/schema.md),
  and [docs/geo-opt-contract.md](../../docs/geo-opt-contract.md)
- [docs/roadmap.md](../../docs/roadmap.md) (especially 0.4.2 and 0.4.8 sections)
- [maintain-contract.md](maintain-contract.md) and
  [update-version-docs.md](update-version-docs.md)

Inspect current Git status and the relevant implementation/tests:

- `src/cp2kkit/parser.py`, `src/cp2kkit/models.py`, `src/cp2kkit/quality.py`
- `src/cp2kkit/structure.py`, `src/cp2kkit/export.py`, `src/cp2kkit/plot.py`
- `src/cp2kkit/cli.py`, `src/cp2kkit/main_tui.py`, `src/cp2kkit/viewer.py`
- `tests/test_geo_opt_contract.py`, `tests/test_output_settings.py`,
  `tests/test_project_text.py`, and existing parser/structure/plot/CLI tests

Repository state wins over this prompt if anything has moved on. Do not modify
or delete any unrelated user changes.

## 2. Scope and explicit boundaries for 0.4.9

- **Target software version**: **0.4.9** (bump once at the end of the round per
  [update-version-docs.md](update-version-docs.md)).
- **Exchange schema**: keep **0.1.0** by making all JSON additions strictly
  optional and additive; retain all existing legacy fields (`final_energy`,
  `last_observed_energy`, `geometry_converged`, `energies`, `settings`,
  `normalized_settings`, existing long-form CSV columns, and exit codes
  `0/2/3/4/5/6/7`).
- **Explicit non-goals (out of scope for 0.4.9)**:
  - No `0.5.0` packaging/CI/PyPI/MCP (`AGENT-1`) work or README/roadmap
    restructuring (`DOC-1`).
  - No `cp2kkit-viewer` Rust code changes (viewer image export is tracked
    separately in the standalone `cp2kkit-viewer` repository).
  - No running CP2K, submitting scheduler jobs, modifying existing outputs, or
    automatic Git commit/push without explicit authorization.
  - No silent inference of a "final optimized structure" from filenames,
    modification times, or taking the last XYZ frame without step evidence.

## 3. Deliverable A: GEO_OPT / CELL_OPT convergence criteria observation

### 3.1 Verify native CP2K 2026.2 output syntax first

Before writing regexes or field schemas, verify the exact printed CP2K 2026.2
optimization convergence block layout from tagged CP2K v2026.2 source or
existing read-only local `.out` files (do not run CP2K). Confirm:

1. Exact labels, units, numeric formats, and YES/NO flags for the four
   Cartesian geometry convergence criteria:
   - `Max. step size` (and its printed `Limit` and `Converged` status)
   - `RMS step size` (and its printed `Limit` and `Converged` status)
   - `Max. gradient` (and its printed `Limit` and `Converged` status)
   - `RMS gradient` (and its printed `Limit` and `Converged` status)
2. Exact printed `CELL_OPT` pressure criterion line(s), unit (`bar`), tolerance,
   and convergence flag when present.
3. Exact placement relative to `OPTIMIZATION STEP:` markers, SCF summaries,
   `ENERGY| Total FORCE_EVAL`, and `GEOMETRY OPTIMIZATION COMPLETED` /
   `MAXIMUM NUMBER OF OPTIMIZATION STEPS` across `BFGS`, `LBFGS`, and `CG`
   (including step 0 / initial step where step-size criteria may be absent or
   printed differently).

### 3.2 Data model and parser rules

- Extend `models.py` / `parser.py` with additive per-step optimization criteria
  records (e.g., `OptimizationStep` / `ConvergenceCriterion` on `Segment`)
  carrying:
  - `segment`, explicit `step` (`int | None`, never synthesized from index),
    `step_source` (`Evidence | None`);
  - per-criterion structured observations (`max_step`, `rms_step`,
    `max_gradient`, `rms_gradient`, plus optional `pressure` for `CELL_OPT`),
    each with `value`, `limit`, explicit `unit` (e.g., `bohr`, `hartree/bohr`,
    `bar` as actually verified), `converged` (`bool | None`), and `source`
    (`Evidence` with path, 1-based line, raw text);
  - overall step-level criteria observation (`all_cartesian_converged: bool | None`,
    `all_observed_converged: bool | None`) strictly reflecting observed flags
    (`null` when any required criterion is missing/unobserved).
- Preserve all conservative parser invariants:
  - Missing criteria remain `null` (distinct from numerical `0.0` or `false`).
  - Actual zero values (e.g., `0.000000`) are preserved faithfully.
  - Non-finite tokens or nonzero values underflowing to zero follow existing
    `number()` / `ParseError` semantics; malformed/damaged criterion lines are
    recorded explicitly with line evidence and warnings rather than silently
    ignored or defaulted.
  - Step resets (`new_step <= step`) and lines after `PROGRAM ENDED` continue
    to split segments cleanly without merging restarts.
  - Keep `quality.py` conservative: do not promote a segment to `passed`
    merely because one step's criteria were `YES` when completion/convergence
    markers are missing; conversely, if explicit criteria exist on a step or
    contradict a claim, surface them clearly in the quality report without
    silently weakening existing failure gates.

## 4. Deliverable B: Explicit trajectory-step association

### 4.1 Verify native CP2K trajectory comment-line syntax first

Verify the exact CP2K 2026.2 `-pos-1.xyz` (and `.extxyz` when emitted via
`EXTXYZ`) header/comment formats from tagged CP2K source or read-only local
outputs (e.g., `i = <int>, E = <float>` and/or `i = <int>, time = ..., E = ...`).
Do not guess or assume arbitrary comment formats.

### 4.2 Association semantics and safety rules

Implement a dedicated, reusable read-only association API (for example in a new
focused module `src/cp2kkit/trajectory.py` or cohesive helpers reused by
`cli.py` and `main_tui.py`):

1. **Explicit inputs only**:
   - Accept an explicit parsed `Run` (or `.out` path + explicit segment
     selection when multiple segments exist) and an explicit trajectory path
     (`.xyz` / `.extxyz`; optionally compare against an explicit `.restart`
     only if clearly scoped and evidenced).
   - Never auto-select a trajectory file by mtime or silently concatenate
     restarts.
2. **Evidence-based frame-to-step matching**:
   - Read all trajectory frames read-only while retaining per-frame provenance
     (`frame_index` 0-based, `line_start`, `line_end`, file `path` and raw-byte
     `sha256`, raw comment line, parsed `trajectory_step` `i`, parsed
     `trajectory_energy_hartree` `E` when present, `atom_count`, `cell`/`pbc`
     presence).
   - Match frames to the selected `.out` segment's steps explicitly using
     observed step numbers (`i == step`) and, when both `.out` energy and
     trajectory `E` are present, verify numerical agreement within an explicit,
     documented tolerance matching CP2K's printed precision (recording exact
     `energy_diff_hartree` and flagging mismatches).
   - Classify every pair/outcome explicitly instead of guessing:
     - exact matched step(s) with energy consistency status (`matched`,
       `energy_mismatch`, `energy_unavailable_in_trajectory`,
       `energy_unavailable_in_output`);
     - unmatched output steps, unmatched trajectory frames, duplicate step
       numbers in trajectory, or missing `i =` comment metadata.
   - Expose an explicit matched-step lookup (e.g., selecting a specific step or
     the last matched converged step **only** when the selected segment passed
     supported geometry/electronic checks and the step-to-frame match is
     unambiguous and consistent; otherwise report `status` and `reasons`
     without silently substituting `frames[-1]`).
3. **Preserve existing `structure.py` behavior**:
   - Keep `read_xyz` / `read_structure` backward-compatible for all existing
     callers and tests.

## 5. CLI, TUI, plotting, and viewer integration

Keep CLI focused on argument parsing and dispatch, reusing shared core APIs:

- **CLI**:
  - `cp2kkit parse` / `cp2kkit report`: include additive optimization criteria
    observations in JSON/summary output without breaking existing keys or CSV
    columns.
  - Add an explicit read-only CLI entry point or option for trajectory-step
    association (for example `cp2kkit match-trajectory` or an explicit
    `--trajectory PATH` option on `parse`/`report`/`export-structure` — pick
    the cleanest, least disruptive surface after inspecting `src/cp2kkit/cli.py`
    and document it clearly).
  - Optionally extend `cp2kkit plot` (`src/cp2kkit/plot.py`) with a convergence
    criteria plot mode (e.g., `--kind convergence` plotting the four criteria
    against their printed limits on a log scale, preserving exclusive
    PNG + CSV + JSON manifest publication and rollback).
  - When `--view` is requested with a verified matched trajectory frame, pass
    only the explicitly matched frame/geometry to `cp2kkit-viewer` via
    `viewer.py`; refuse silently opening an ambiguous/mismatched frame.
- **TUI (`src/cp2kkit/main_tui.py`)**:
  - Preserve main-menu numbering `1-7` and existing structure state.
  - Surface optimization criteria summary and optional trajectory-matching
    inspection inside main **5 Output analysis** (`5/1`, `5/2`, `5/3`) without
    breaking existing prompts or PTY tests.

## 6. Contracts, documentation, and verification gates

Follow the Public Contract Completion Gate in `.agents/DEVELOPMENT.md`:

1. Update:
   - [docs/geo-opt-contract.md](../../docs/geo-opt-contract.md) (additive
     criteria and trajectory-association semantics, units, null/status rules,
     and what matching does **not** prove);
   - [docs/schema.md](../../docs/schema.md) and
     [docs/contracts.md](../../docs/contracts.md);
   - [examples/geo-opt-contract/README.md](../../examples/geo-opt-contract/README.md)
     (if selected-field expectations gain new additive examples);
   - `src/cp2kkit/__init__.py`, `pyproject.toml`, `README.md`, `CHANGELOG.md`,
     `docs/architecture.md`, `docs/roadmap.md`, and `docs/development-handoff.md`
     for version **0.4.9**.
2. Add comprehensive synthetic unit & CLI tests covering:
   - `GEO_OPT` four criteria parsing (step 0 / subsequent steps, converged YES,
     unconverged NO, missing/partial blocks, damaged tokens, non-finite /
     underflow rejection, `CELL_OPT` with pressure criterion, multi-segment
     step reset);
   - Trajectory-step association (exact match, energy mismatch, duplicate `i`,
     missing comment metadata, missing frames, extra frames, multi-segment
     ambiguity refusal, exclusive export / overwrite protection);
   - Optional convergence plot (with Matplotlib available and graceful skip/code
     6 when unavailable) and TUI/CLI parity;
   - All existing `0.4.2`–`0.4.8` regression tests remain green.
3. Run checks using the verified Python environment (redirecting logs to a
   temporary directory under `/tmp` and using temporary `PYTHONPYCACHEPREFIX` if
   needed):
   - Focused new tests + full `PYTHONPATH=src "$PYTHON" -m unittest discover -s tests -v`
   - `tests/test_project_text.py` (strictly no literal CJK in maintained files,
     all local Markdown links resolve, prompt rules pass)
   - `PYTHONPATH=src "$PYTHON" -m compileall -q src tests`
   - `cp2kkit --version` (`0.4.9`) and CLI subprocess smoke checks
   - `git diff --check`
4. Report changed files, public contract impacts, exact checks run with exit
   statuses, and remaining limitations. Do not commit, tag, or push unless the
   user explicitly asks.
