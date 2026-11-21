# Molecular thermochemistry with external Shermo 2.6.2

cp2kkit 0.4.5 can explicitly invoke a separately installed **Shermo 2.6.2**.
It does not bundle or compile Shermo, implement its equations, launch it during
ordinary `vibration` inspection, run CP2K, or submit a job. A later internal
implementation is a separate backend and is not available in this release.

## Usage

```bash
cp2kkit thermochemistry vibration.out --shermo /path/to/Shermo \
  --energy-output larger-basis-single-point.out \
  --geometry optimized.xyz --frame 0 --masses-amu 15.994915 1.007825 1.007825 \
  --multiplicity 1 --confirm-reference --temperature-k 298.15 --pressure-atm 1 \
  --low-frequency grimme --frequency-scale 1 -o thermo.json

cp2kkit shermo-read existing-shermo-stdout.txt -o imported.json
```

The example masses are explicit isotope masses for an O/H/H atom order; use the
masses corresponding to the actual calculation, not these numbers blindly.
Provide the actual reference XYZ frame (0-based), masses in XYZ order and spin
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
TUI main **7** opens the observation directly; choose **s**, optionally provide
the single-point output, and confirm explicitly to run Shermo. The application's currently loaded structure
is not reused implicitly. The TUI refuses a CP2K source changed since inspection.

Python exposes `cp2kkit.thermochemistry.run_shermo(output_path, geometry_path, *,
executable, frame, masses_amu, multiplicity, temperature=298.15, pressure=1.0,
scale=1.0, low_frequency='grimme', confirm_reference=False, segment=None,
block=None, timeout=30, expected_source_sha256=None, energy_output=None,
energy_segment=None)` and
`read_shermo(path)`. Both return a report dictionary; neither writes public result
files. `expected_source_sha256` optionally pins the selected CP2K bytes.

## Supported scope and provenance

- One isolated unconstrained molecular minimum model, strictly positive CP2K
  Cartesian frequencies and a strict CP2K 2026.2 vibration report. Explicit SCF
  nonconvergence text in its pre-table segment rejects the run. Text checks do
  not certify convergence, an actual minimum, geometry match or numerical accuracy.
- An explicitly supplied single-point output must have a selected `ENERGY` or
  `ENERGY_FORCE` segment with one total energy in Hartree, a unique associated
  converged SCF summary and text quality passing (including a program-end
  marker and no damaged energy records). Printed multiplicity, when available,
  must agree. This route does not require the frequency output to print a
  reference energy, and does not fall back to the frequency output on failure.
  If no single-point output is supplied, use the unique reference electronic
  energy in the vibration block's adjacent native footer. Its printed `kJ/mol`
  value is converted with the CP2K v2026.2 `physcon.F` convention. Ordinary
  force-evaluation energies from the vibration run are never substituted.
- Printed multiplicity from the vibration segment must also match the request.
  If both selected segments report charge, the values must agree. Conflicting
  or unsupported printed charge/multiplicity records are rejected before Shermo
  launches. Missing records are not inferred; the caller still asserts that
  both sources describe the same molecular state.
- Atom indices/elements in the displacement table must match the complete XYZ
  frame in order. A periodic frame is rejected. The observed count must match
  the linear or nonlinear molecule and Shermo's reported linearity; geometry
  correspondence beyond atom order and identity remains caller-asserted.
- The `.shm` has coordinates in angstrom, masses in amu, signed wavenumbers in
  cm^-1 (all positive for this scope), reference energy in Hartree, and one
  electronic level at 0 eV with degeneracy equal to the supplied multiplicity.
  No excited levels, mode deletion or imaginary-frequency reinterpretation.
- Single positive temperature (default 298.15 K), pressure (default 1 atm),
  and a shared positive scale for ZPE, thermal vibration, entropy and CV
  (default 1). The low-frequency choices are harmonic or Grimme's entropy
  interpolation (default, Shermo 2.6.2 threshold 100 cm^-1). Shermo determines
  point group and rotational symmetry; its printed values are retained. Review
  those values, especially for nearly symmetric geometries and isotopes.
  No pressure/temperature scans, solution standard-state conversion, ensembles,
  periodic systems or transition-state thermochemistry.
- Invocation is local, without a shell, in a new temporary directory with
  stdin closed and a timeout (default 30 s). Only use a trusted executable;
  the working directory is not an OS sandbox. `-noset` isolates calculations
  from local/external `settings.ini`; no arbitrary native arguments are accepted.
  The exchange and scratch files are removed on return. Zero exit alone is
  insufficient: require the version banner, settings, molecular summary and
  complete numeric totals; check managed settings and composition-derived mode
  count against the request. `shermo-read` parses the same supported output format
  without asserting a CP2K association or process exit. It reports the pressure-
  state totals, not any supplemental concentration-corrected line.

## Result and errors

JSON `operation: "shermo_thermochemistry"` is independent of CP2K's observation
and generator manifest. `electronic_energy`, `zero_point_energy`,
`thermal_corrections` and `corrected_totals` (`U`, `H`, `G`) are distinct printed
Hartree quantities carrying line evidence, checked at Shermo's display precision.
Temperature, pressure, standard-state model, four printed scales, low-frequency
treatment/cutoff (null for harmonic), point group, rotational symmetry number,
linearity, mode count, tool version and citation are included. `source` has the
stdout hash and bytes, and either the actual import path or a captured-stdout
label. A managed result additionally has `cp2k_reference` (source, selected block,
geometry frame, explicit masses and multiplicity, normalized vibrational
`reference_state` evidence, exchange energy and scratch exchange hash) and `external_run` (executable path, argv, timeout, exit status
and optional bounded stderr excerpt). Import omits those two managed-only fields.
`cp2k_reference.selected_electronic_energy` identifies the source actually used:
`cp2k_single_point` includes the independent file hash, 1-based segment, energy
and SCF evidence; `cp2k_vibration_footer` includes its printed quantity.
`printed_electronic_energy` preserves the vibration footer quantity when present,
even when not selected; it is null when no usable footer energy was observed.

CLI defaults to stdout; `-o` creates a new file, never overwrites. Usage,
invalid reference choices, timeout or nonzero tool exit return 2; CP2K ambiguity
returns 3; unsupported or incomplete output returns 4; collision returns 5.
Failure publishes no result JSON. Neither a report nor a zero exit certifies
scientific validity. Automated tests use source-format synthetic records and a
mocked Shermo process. The [0.4.5 handoff](development-handoff.md#historical-handoff-045)
separately records the bounded native water comparisons and their limitations.
See the [third-party notice](../THIRD_PARTY_NOTICES.md#shermo) for the reviewed source and terms.
