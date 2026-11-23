# Molecular and surface-mode thermochemistry with external Shermo 2.6.2

cp2kkit 0.4.5–0.4.7 can explicitly invoke a separately installed **Shermo 2.6.2**.
It does not bundle or compile Shermo, implement its equations, launch it during
ordinary `vibration` inspection, run CP2K, or submit a job. A later internal
implementation is a separate backend and is not available in this release.
Version **0.4.7** adds explicit `--thermo-model vibrational-only` (`imode=1`) for
periodic surface partial-Hessian modes alongside the unchanged `ideal-gas`
(`imode=0`) default.

## Usage

```bash
# Isolated molecular ideal-gas model (default, imode=0)
cp2kkit thermochemistry vibration.out --shermo /path/to/Shermo \
  --energy-output larger-basis-single-point.out \
  --geometry optimized.xyz --frame 0 --masses-amu 15.994915 1.007825 1.007825 \
  --multiplicity 1 --confirm-reference --temperature-k 298.15 --pressure-atm 1 \
  --low-frequency grimme --frequency-scale 1 -o thermo.json

# Surface partial-Hessian vibrational-only model (imode=1; independent SP required)
cp2kkit thermochemistry slab-freq.out --shermo /path/to/Shermo \
  --thermo-model vibrational-only --active-atoms 181-183 \
  --energy-output slab-sp.out --geometry slab-optimized.extxyz --frame 0 \
  --element-masses Ga=69.7230 O=15.9994 H=1.0079 \
  --multiplicity 1 --confirm-reference --temperature-k 298.15 \
  --low-frequency harmonic --frequency-scale 1 -o surface-thermo.json

cp2kkit shermo-read existing-shermo-stdout.txt -o imported.json
```

The example masses are explicit isotope/atomic masses; use the masses
corresponding to the actual calculation, not these numbers blindly. Supply either
`--masses-amu` (one mass per atom in XYZ order) or `--element-masses EL=MASS ...`
(mutually exclusive; every element present in the XYZ frame must be listed, with
no built-in mass table). Provide the actual reference XYZ frame (0-based) and spin
multiplicity; `--confirm-reference` asserts their association rather than proving
it. The normal composite workflow is optimization, followed by vibration and
an independent single-point calculation on the **same** optimized geometry.
`--energy-output` selects the single-point electronic energy (e.g. with a larger
basis), while the vibrational modes and thermal corrections still come from
frequency analysis and Shermo. The supplied charge, spin state and reference
geometry must be consistent across the two calculations; a basis change is
intentional and is not treated as an error. The CLI does not run either CP2K job.
Multiple vibration candidates require `--segment`/`--block` (both 1-based);
a separate energy file with multiple candidates needs `--energy-segment` (1-based).
TUI main **7** opens the observation directly; choose **s**, select `ideal-gas`
(default) or `vibrational-only`, supply the required single-point output (and
active atoms for `vibrational-only`), and confirm explicitly to run Shermo. The
application's currently loaded structure is not reused implicitly. The TUI refuses
a CP2K source changed since inspection.

Python exposes `cp2kkit.thermochemistry.run_shermo(output_path, geometry_path, *,
executable, frame, masses_amu=None, multiplicity, temperature=298.15, pressure=1.0,
scale=1.0, low_frequency=None, confirm_reference=False, segment=None, block=None,
timeout=30, expected_source_sha256=None, energy_output=None, energy_segment=None,
thermo_model='ideal-gas', active_atoms=None, element_masses=None)` and
`read_shermo(path)`. Both return a report dictionary; neither writes public result
files. `expected_source_sha256` optionally pins the selected CP2K bytes.

## Supported scope and provenance

- Two explicit thermal models (never auto-selected from PBC, atom count or filename):
  - **`ideal-gas` (`imode=0`, default):** isolated unconstrained molecular minimum,
    non-periodic XYZ frame, non-`XYZ` CP2K vibration report, `displacement_atoms`
    matching every XYZ atom in order, strictly positive frequencies with mode count
    `3N-5` or `3N-6` matching Shermo's linearity, default `--low-frequency grimme`.
    Uses `--energy-output` when provided, or the unique native vibration footer.
  - **`vibrational-only` (`imode=1`, added in 0.4.7):** selected-mode surface/adsorbate
    correction omitting translational and rotational contributions. Requires an
    explicit 1-based `--active-atoms` list/range matching `displacement_atoms`
    (indices, elements and order) in the full reference XYZ frame (periodic extXYZ
    or plain XYZ), no gas-phase `ROT|` projection, strictly positive modes with
    exact count `3 * active_atom_count`, and an explicit independent full-system
    single-point `--energy-output` (CP2K skips its molecular footer when atoms are
    frozen). Invokes Shermo with `-imode 1 -PGlabel C1` (bypassing molecular SYVA
    point-group detection on periodic slabs) and defaults `--low-frequency` to
    `harmonic`. Explicit `--low-frequency grimme` is permitted with an explicit
    warning that Grimme's free-rotor average moment-of-inertia convention is not
    calibrated to a periodic surface/adsorbate coordinate set; compare against
    `harmonic` independently.
- Both models require a strict CP2K 2026.2 vibration report and reject explicit
  SCF nonconvergence text in the pre-table segment. Text checks do not certify
  convergence, an actual minimum, geometry match or numerical accuracy.
- An explicitly supplied single-point output must have a selected `ENERGY` or
  `ENERGY_FORCE` segment with one total energy in Hartree, a unique associated
  converged SCF summary and text quality passing (including a program-end
  marker and no damaged energy records). Printed multiplicity, when available,
  must agree. Within that selected segment only (unselected segments in
  multi-segment outputs do not interfere):
  - **Electronic entropy / smearing gate:** if the selected segment reports a
    nonzero Fermi-Dirac `Electronic entropic energy` (`-T_e S_e`), a nonzero
    Gaussian/Methfessel-Paxton/Marzari-Vanderbilt `Smearing free energy
    correction` (a numerical smearing correction, kept distinct from physical
    electronic entropy), a `Total energy (extrapolated to T->0)` or `Total
    energy (extrapolated to sigma->0)` differing from `Total FORCE_EVAL` energy,
    or a recognized-but-damaged/unsupported record (including missing colon,
    broken unit bracket, unsupported unit or trailing tokens), `run_shermo`
    rejects the run before launching Shermo. No automatic extrapolation
    substitution or correction subtraction is performed, and raw `ENERGY` parser
    semantics are unchanged. Explicit zero (`0.0` / `-0.0`) is accepted;
    genuinely unprinted records stay `status: "missing", value: null` (never
    rewritten to zero).
  - **Full-system consistency gate:** if the selected segment prints a total
    atom count (`- Atoms:`), it must use the native colon format and equal the
    **full** reference XYZ atom count (not `active_atoms`). If it prints
    `CELL|`/`POISSON| Periodicity`, it must use native whitespace-only
    separation (rejecting non-native punctuation such as `Periodicity: XY`),
    be internally consistent, and agree with the selected vibration segment
    periodicity, the reference XYZ periodicity (when known), and `ideal-gas`
    (`NONE`). Damaged, conflicting or contradicting records are rejected before
    Shermo launches; genuinely unprinted records remain `missing` without
    guessing, and `--confirm-reference` does not bypass or replace these checks.
  This route does not require the frequency output to print a reference energy,
  and does not fall back to the frequency output on failure.
  In `ideal-gas` mode without a single-point output, the unique native vibration
  footer `kJ/mol` value is converted with the CP2K v2026.2 `physcon.F` convention.
  Ordinary force-evaluation energies from the vibration run are never substituted.
- Printed multiplicity from the vibration segment must also match the request.
  If both selected segments report charge, the values must agree. Conflicting
  or unsupported printed charge/multiplicity records are rejected before Shermo
  launches. Missing records are not inferred; the caller still asserts that
  both sources describe the same electronic state.
- The `.shm` has coordinates in angstrom, explicit caller-supplied masses in amu,
  signed wavenumbers in cm^-1 (all positive for this scope), reference energy in
  Hartree, and one electronic level at 0 eV with degeneracy equal to the supplied
  multiplicity. No excited levels, mode deletion or imaginary-frequency
  reinterpretation.
- Single positive temperature (default 298.15 K), pressure (default 1 atm;
  recorded from Shermo's printed running parameters, unused in `imode=1` U/H/G
  because translation and `PV` are omitted), and a shared positive scale for
  ZPE, thermal vibration, entropy and CV (default 1). In `ideal-gas` mode, Shermo
  determines point group and rotational symmetry; review those values for nearly
  symmetric geometries and isotopes. No pressure/temperature scans, solution
  standard-state conversion, ensembles, periodic phonon q-point integration,
  adsorption free-energy subtraction or transition-state thermochemistry.
- Invocation is local, without a shell, in a new temporary directory with
  stdin closed and a timeout (default 30 s). Only use a trusted executable;
  the working directory is not an OS sandbox. `-noset` isolates calculations
  from local/external `settings.ini`; no arbitrary native arguments are accepted.
  The exchange and scratch files are removed on return. Zero exit alone is
  insufficient: require the version banner, settings, mode-specific `imode=0` or
  three `imode=1` markers, complete numeric totals (including `U == H` equality
  for `imode=1`), and check managed settings and mode count against the request.
  `shermo-read` parses both supported `imode=0` and `imode=1` stdout formats
  without asserting a CP2K association or process exit. It reports the printed
  totals, not any supplemental concentration-corrected line.

## Result and errors

JSON `operation: "shermo_thermochemistry"` is independent of CP2K's observation
and generator manifest. `electronic_energy`, `zero_point_energy`,
`thermal_corrections` and `corrected_totals` (`U`, `H`, `G`) are distinct printed
Hartree quantities carrying line evidence, checked at Shermo's display precision.
Additive fields `thermo_model` (`"ideal-gas"` or `"vibrational-only"`), `imode`
(`0` or `1`) and `warnings` (list of strings) distinguish the thermal model.
`standard_state` is `"ideal_gas_at_reported_pressure"` for `imode=0` and
`"vibrational_only_no_translation_rotation"` for `imode=1`. In `imode=1`,
inapplicable `point_group`, `rotational_symmetry_number` and `linear` are `null`.
Temperature, pressure, four printed scales, low-frequency treatment/cutoff (null
for harmonic), mode count, tool version and citation are included. `source` has
the stdout hash and bytes, and either the actual import path or a captured-stdout
label. A managed result additionally has `cp2k_reference` (source, selected block,
`periodicity`, `thermo_model`, `hessian_atom_scope` (`"full_molecule"` or
`"partial_active_atoms"`), `active_atoms`, geometry frame, explicit masses and
multiplicity, normalized vibrational `reference_state` evidence, exchange energy
and scratch exchange hash) and `external_run` (executable path, argv, timeout,
exit status and optional bounded stderr excerpt). Import omits those two
managed-only fields.
`cp2k_reference.selected_electronic_energy` identifies the source actually used:
`cp2k_single_point` includes the independent file hash, 1-based segment, energy,
SCF evidence, and selected-segment `atom_count`, `periodicity`,
`electronic_entropic_energy`, `smearing_free_energy_correction`,
`extrapolated_t0_energy` and `extrapolated_sigma0_energy` provenance (with
`status: "missing", value: null` when unprinted); `cp2k_vibration_footer`
includes its printed quantity.
`printed_electronic_energy` preserves the vibration footer quantity when present,
even when not selected; it is null when no usable footer energy was observed.

CLI defaults to stdout; `-o` creates a new file, never overwrites. Warnings are
written to stderr. Usage, invalid reference choices, timeout or nonzero tool exit
return 2; CP2K ambiguity returns 3; unsupported or incomplete output returns 4;
collision returns 5. Failure publishes no result JSON. Neither a report nor a zero
exit certifies scientific validity. Automated tests use source-format synthetic
records and a mocked Shermo process. The [development handoff](development-handoff.md)
separately records bounded native adapter comparisons and their limitations.
See the [third-party notice](../THIRD_PARTY_NOTICES.md#shermo) for the reviewed
source and terms.
