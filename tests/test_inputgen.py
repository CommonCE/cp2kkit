"""Synthetic generation tests; none execute CP2K or certify scientific results."""
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path

from cp2kkit.cli import main
from tests.synthetic_cp2k_data import basis_entry, potential_entry
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.inputgen import BASES, CP2K_VERSIONS, MULTIWFN_CITATIONS, VALENCE, InputSettings, generate_input, write_input
from cp2kkit.structure import Structure, read_restart, read_xyz

FIXTURES = Path(__file__).parent / "fixtures"


class InputGenerationTests(unittest.TestCase):
    def setUp(self):
        self.water = Structure(["O", "H", "H"], [[0., 0., 0.], [0.76, 0., 0.58], [-0.76, 0., 0.58]],
                               None, None, {"path": "synthetic"})
        self.settings = InputSettings(periodic="NONE", write_json=True)

    def test_defaults_and_provenance(self):
        text, manifest = generate_input(self.water, self.settings)
        self.assertIn("RUN_TYPE ENERGY", text)
        self.assertIn("METHOD GPW", text)
        self.assertIn("POTENTIAL GTH-PBE-q6", text)
        self.assertIn("BASIS_SET DZVP-MOLOPT-SR-GTH-q1", text)
        self.assertIn("POISSON_SOLVER WAVELET", text)
        self.assertNotIn("VDW_POTENTIAL", text)
        self.assertEqual(manifest["valence_electron_count"], 8)
        self.assertEqual(manifest["effective_eps_scf"], 1e-6)
        self.assertEqual(manifest["input_sha256"], hashlib.sha256(text.encode()).hexdigest())
        self.assertFalse(manifest["runtime_validated"])
        self.assertIsNone(manifest["runtime_version"])
        self.assertTrue(manifest["coordinates_translated"])
        self.assertEqual(self.water.positions[0], [0., 0., 0.])
        self.assertEqual((text, manifest), generate_input(self.water, self.settings))

    def test_readable_eps_formatting_and_custom_precision(self):
        for task, default, eps in (("ENERGY", "1.0E-11", "1.0E-06"),
                                   ("GEO_OPT", "1.0E-12", "1.0E-06")):
            text, _ = generate_input(self.water, replace(self.settings, run_type=task))
            self.assertIn(f"EPS_DEFAULT {default}\n", text)
            self.assertEqual(text.count(f"EPS_SCF {eps}\n"), 2)  # OT inner + outer
        for eps in (1.2345678901234567e-7, 0.125, 1e-100, 5e-324):
            text, m = generate_input(self.water, replace(self.settings, eps_scf=eps))
            tokens = [line.split()[1] for line in text.splitlines() if line.strip().startswith('EPS_SCF ')]
            self.assertEqual(len(tokens), 2)
            for token in tokens:
                self.assertRegex(token, r'^\d+\.\d+E[+-]\d{2,}$')
                self.assertEqual(float(token), eps)
            self.assertEqual(m['effective_eps_scf'], eps)
        text, _ = generate_input(self.water, replace(self.settings, scf='diag', eps_scf=1e-6))
        self.assertEqual(text.count('EPS_SCF 1.0E-06\n'), 1)

    def test_cell_coord_fixed_width_user_example(self):
        zinc = replace(self.water, symbols=['Zn'], positions=[[1.41636598, 4.48472671, 2.14717961]],
                       cell=[[16.1868, 0., 0.], [0., 28.0363, 0.], [0., 0., 40.4441]], pbc=[True]*3)
        text, m = generate_input(zinc, InputSettings())
        expected = ('    &CELL\n'
                    '      A    16.18680000     0.00000000     0.00000000\n'
                    '      B     0.00000000    28.03630000     0.00000000\n'
                    '      C     0.00000000     0.00000000    40.44410000\n'
                    '      PERIODIC XYZ\n'
                    '    &END CELL\n'
                    '    &COORD\n'
                    '      Zn          1.41636598    4.48472671    2.14717961\n'
                    '    &END COORD')
        self.assertIn(expected, text)
        self.assertNotIn('UNIT angstrom', text)
        self.assertEqual(m['units']['coordinates'], 'angstrom')
        self.assertEqual(m['units']['cell'], 'angstrom')

    def test_geometry_rounding_manifest_and_negative_zero(self):
        source = replace(self.water, positions=[[1.123456789123, -0.000000001, -12.123456789123],
                                               self.water.positions[1], self.water.positions[2]],
                         cell=[[10.123456789, 0., 0.], [1.234567891, 11., 0.], [0., 0., 12.]], pbc=[True]*3)
        text, m = generate_input(source, InputSettings())
        self.assertNotIn('-0.00000000', text)
        self.assertEqual(m['source_structure']['positions'], source.positions)
        self.assertEqual(m['source_structure']['cell'], source.cell)
        self.assertEqual(source.positions[0][0], 1.123456789123)
        self.assertEqual(m['generated_structure']['positions'][0], [1.12345679, 0., -12.12345679])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'rounded.restart'
            path.write_text(text)
            got = read_restart(path)
        self.assertEqual(got.positions, m['generated_structure']['positions'])
        self.assertEqual(got.cell, m['generated_structure']['cell'])
        self.assertEqual(m['input_sha256'], hashlib.sha256(text.encode()).hexdigest())

    def test_geometry_large_fields_and_rounding_singular_cell(self):
        source = replace(self.water, positions=[[123456789.12345679, -123456789.12345679, 0.],
                                               self.water.positions[1], self.water.positions[2]],
                         cell=[[123456789.12345679, 0., 0.], [0., 11., 0.], [0., 0., 12.]], pbc=[True]*3)
        text, m = generate_input(source, InputSettings())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'large.restart'
            path.write_text(text)
            got = read_restart(path)
        self.assertEqual(got.positions, m['generated_structure']['positions'])
        self.assertEqual(got.cell, m['generated_structure']['cell'])
        tiny = replace(source, cell=[[1e-9, 0., 0.], [0., 11., 0.], [0., 0., 12.]])
        with self.assertRaisesRegex(KitError, 'Singular'):
            generate_input(tiny, InputSettings())

    def test_reference_notices_and_catalog(self):
        text, manifest = generate_input(self.water, self.settings)
        for citation in MULTIWFN_CITATIONS:
            self.assertIn('# ' + citation, text)
        self.assertEqual(manifest['references']['Multiwfn'], list(MULTIWFN_CITATIONS))
        self.assertEqual(len(VALENCE), 71)
        self.assertEqual(VALENCE['Fe'], 16)
        self.assertEqual(VALENCE['Pt'], 18)
        self.assertEqual(manifest['units']['cutoff'], 'Ry')

    def test_isolated_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generated.restart"
            text, manifest = generate_input(self.water, self.settings)
            path.write_text(text)
            got = read_restart(path)
            self.assertEqual(got.positions, manifest["generated_structure"]["positions"])
            self.assertEqual(got.cell, manifest["generated_structure"]["cell"])
            self.assertEqual(got.pbc, [False]*3)
            self.assertEqual(got.symbols, self.water.symbols)

    def test_restart_cell_preserved(self):
        water = read_restart(FIXTURES / "water.restart")
        text, manifest = generate_input(water, InputSettings())
        self.assertIn("PERIODIC XY", text)
        self.assertIn("POISSON_SOLVER ANALYTIC", text)
        self.assertEqual(manifest["generated_structure"]["cell"], water.cell)
        self.assertEqual(manifest["generated_structure"]["positions"], water.positions)
        self.assertFalse(manifest["coordinates_translated"])

    def test_tasks_and_balanced_sections(self):
        for task in ("ENERGY", "ENERGY_FORCE", "GEO_OPT", "CELL_OPT"):
            s = replace(self.settings, run_type=task, periodic="XYZ", cell=(10., 11., 12.))
            text, manifest = generate_input(self.water, s)
            stack = []
            for line in text.splitlines():
                fields = line.strip().split()
                if fields[0] == "&END":
                    self.assertEqual(stack.pop(), fields[1])
                elif fields[0].startswith("&"):
                    stack.append(fields[0][1:])
            self.assertEqual(stack, [])
            self.assertEqual("&MOTION" in text, task in {"GEO_OPT", "CELL_OPT"})
            self.assertEqual("STRESS_TENSOR ANALYTICAL" in text, task == "CELL_OPT")
            if task != "ENERGY":
                self.assertEqual(manifest["effective_eps_scf"], 1e-6)
            self.assertNotIn("DIRECT_CELL_OPT", text)

    def test_functionals_basis_dispersion(self):
        for functional in ("PBE", "BLYP"):
            for basis in BASES:
                if basis in {'TZVP-MOLOPT-SR-GTH', 'TZV2P-MOLOPT-SR-GTH'}:
                    # These UCL families lack H/O at the fixed valence: never infer a fallback.
                    with self.assertRaises(KitError):
                        generate_input(self.water, replace(self.settings, functional=functional, basis=basis))
                    continue
                for dispersion in ("none", "d3", "d3bj"):
                    text, _ = generate_input(self.water, replace(self.settings, functional=functional, basis=basis, dispersion=dispersion))
                    self.assertIn(f"POTENTIAL GTH-{functional}-q6", text)
                    self.assertIn(f"BASIS_SET {basis}-q6", text)
                    if dispersion != "none":
                        self.assertIn(f"REFERENCE_FUNCTIONAL {functional}", text)
                        self.assertIn("TYPE DFTD3(BJ)" if dispersion == "d3bj" else "TYPE DFTD3\n", text)

    def test_spin_charge(self):
        radical = replace(self.water, symbols=["O", "H"], positions=self.water.positions[:2])
        text, m = generate_input(radical, replace(self.settings, multiplicity=2))
        self.assertIn("UKS T", text)
        self.assertEqual(m["valence_electron_count"], 7)
        text, _ = generate_input(self.water, replace(self.settings, charge=1, multiplicity=2))
        self.assertIn("CHARGE 1", text)
        for charge, multiplicity in ((0, 2), (0, 10), (8, 1)):
            with self.assertRaises(KitError):
                generate_input(self.water, replace(self.settings, charge=charge, multiplicity=multiplicity))

    def test_cell_opt_orientation(self):
        water = replace(self.water, cell=[[10., 1., 0.], [0., 11., 0.], [0., 0., 12.]], pbc=[True]*3)
        with self.assertRaisesRegex(KitError, "lower-triangular"):
            generate_input(water, InputSettings(run_type="CELL_OPT"))
        # The same nonsingular orientation is not silently rotated for an energy task.
        _, m = generate_input(water, InputSettings())
        self.assertEqual(m["generated_structure"]["cell"], water.cell)

    def test_diag_smear_kpoints(self):
        text, _ = generate_input(self.water, replace(self.settings, periodic="XYZ", cell=(10., 10., 10.),
                                                     scf="diag", smearing=300., kpoints=(2, 2, 2)))
        self.assertIn("SCHEME MONKHORST-PACK 2 2 2", text)
        self.assertIn("ELECTRONIC_TEMPERATURE [K] 300", text)
        self.assertIn("ADDED_MOS 30", text)
        self.assertNotIn("&OT", text)

    def test_validation(self):
        bad = [dict(periodic=None), dict(periodic="INVALID"), dict(periodic="XYZ"),
               dict(run_type="CELL_OPT"), dict(kpoints=(2, 1, 1)), dict(smearing=300.),
               dict(scf="diag", smearing=300., added_mos=0), dict(cutoff=0), dict(rel_cutoff=float("nan")),
               dict(eps_scf=-1.), dict(vacuum=float("inf")), dict(max_scf=0), dict(max_iter=-1),
               dict(project="../escape"), dict(project="x\n@INCLUDE evil"), dict(cell=(0, 1, 1)),
               dict(multiplicity=1.5), dict(kpoints=(1, 0, 1)), dict(pressure=float("nan")),
               dict(functional="PBE0"), dict(basis="fake"), dict(dispersion="d4")]
        for values in bad:
            with self.subTest(values=values), self.assertRaises(KitError):
                generate_input(self.water, replace(self.settings, **values))
        with self.assertRaises(KitError):
            generate_input(replace(self.water, symbols=["U", "H", "H"]), self.settings)
        with self.assertRaises(KitError):
            generate_input(replace(self.water, positions=[[float("inf"), 0, 0]]*3), self.settings)

    def test_transition_metal_presets(self):
        atom = Structure(["Fe"], [[0., 0., 0.]], None, None, {"path": "synthetic"})
        text, manifest = generate_input(atom, replace(self.settings, multiplicity=5))
        self.assertIn("GTH-PBE-q16", text)
        self.assertEqual(manifest["valence_electron_count"], 16)
        with self.assertRaisesRegex(KitError, "Non-SR"):
            generate_input(atom, replace(self.settings, basis="TZVP-MOLOPT-GTH"))
        pt = replace(atom, symbols=["Pt"])
        with self.assertRaisesRegex(KitError, "GTH-BLYP"):
            generate_input(pt, replace(self.settings, functional="BLYP"))

    def test_extxyz_periodicity_and_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h2.extxyz"
            path.write_text('2\nLattice="10 0 0 0 10 0 0 0 10" pbc="T T T"\nH 0 0 0\nH 0 0 0.7\n')
            structure = read_xyz(path)
            _, m = generate_input(structure, InputSettings())
            self.assertEqual(m["poisson_solver"], "PERIODIC")
            _, overridden = generate_input(structure, replace(self.settings, cell=(12., 13., 14.)))
            self.assertEqual(overridden["generated_structure"]["pbc"], [False]*3)
            self.assertEqual(overridden["source_structure"]["pbc"], [True]*3)
            self.assertEqual(overridden["generated_structure"]["cell"][0], [12., 0., 0.])

    def test_explicit_cell_does_not_translate(self):
        _, m = generate_input(self.water, replace(self.settings, cell=(20., 20., 20.)))
        self.assertFalse(m["coordinates_translated"])
        self.assertEqual(m["generated_structure"]["positions"], self.water.positions)

    def test_local_data_headers_and_hashes(self):
        # Invented structurally complete payloads, NOT scientific parameters.
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "BASIS_MOLOPT").write_text(basis_entry("H", "DZVP-MOLOPT-SR-GTH-q1") + basis_entry("O", "DZVP-MOLOPT-SR-GTH-q6"))
            (d / "GTH_POTENTIALS").write_text(potential_entry("H", 1, "GTH-PBE-q1") + potential_entry("O", 6, "GTH-PBE-q6"))
            (d / "dftd3.dat").write_text("synthetic test only\n")
            text, m = generate_input(self.water, replace(self.settings, data_dir=tmp, dispersion="d3"))
            self.assertEqual(set(m["data_sources"]), {"basis", "potential", "dispersion"})
            self.assertIn(str(d / "GTH_POTENTIALS"), text)
            self.assertEqual(m["data_sources"]["basis"]["sha256"], hashlib.sha256((d / "BASIS_MOLOPT").read_bytes()).hexdigest())
            (d / "BASIS_MOLOPT").write_text("# H DZVP-MOLOPT-SR-GTH-q1\n" + basis_entry("O", "DZVP-MOLOPT-SR-GTH-q6"))
            with self.assertRaisesRegex(KitError, "No matching ORB data.* H"):
                generate_input(self.water, replace(self.settings, data_dir=tmp))

    def test_exclusive_output_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "water.inp"
            sidecar = Path(str(out) + ".json")
            sidecar.write_text("existing")
            with self.assertRaises(OutputExists):
                write_input(self.water, self.settings, out)
            self.assertFalse(out.exists())
            self.assertEqual(sidecar.read_text(), "existing")
            sidecar.unlink()  # synthetic test file only
            write_input(self.water, self.settings, out)
            original = out.read_bytes()
            with self.assertRaises(OutputExists):
                write_input(self.water, self.settings, out)
            self.assertEqual(out.read_bytes(), original)
            self.assertEqual(json.loads(sidecar.read_text())["input_text"], out.read_text())

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()):
            out = Path(tmp) / "h2.inp"
            argv = ["generate-input", "--write-json", str(FIXTURES / "trajectory.xyz"), "--periodic", "none", "-o", str(out)]
            self.assertEqual(main(argv), 0)
            self.assertEqual(main(argv), 5)
            self.assertEqual(json.loads(Path(str(out) + ".json").read_text())["source_structure"]["frame"], 1)
            unknown = Path(tmp) / "unknown.inp"
            self.assertEqual(main(["generate-input", str(FIXTURES / "trajectory.xyz"), "-o", str(unknown)]), 2)
            self.assertFalse(unknown.exists())

    def test_density_print_placement_and_frequency(self):
        for task in ("ENERGY", "ENERGY_FORCE", "GEO_OPT", "CELL_OPT"):
            settings = replace(self.settings, run_type=task, periodic="XYZ", cell=(10.,10.,10.),
                               electron_density=True, cube_stride=(1,2,3))
            text, manifest = generate_input(self.water, settings)
            stack = []
            parents = []
            for line in text.splitlines():
                fields = line.strip().split()
                if not fields or fields[0].startswith('#'):
                    continue
                if fields[0] == '&END':
                    self.assertEqual(stack.pop(), fields[1])
                elif fields[0].startswith('&'):
                    if fields[0] == '&E_DENSITY_CUBE':
                        parents = stack.copy()
                        self.assertEqual(fields[1], 'ON')
                    stack.append(fields[0][1:])
            self.assertEqual(parents, ['FORCE_EVAL','DFT','PRINT'])
            self.assertEqual(stack, [])
            for line in ('STRIDE 1 2 3','APPEND F','ADD_LAST NUMERIC','QS_SCF 0','JUST_ENERGY 1','GEO_OPT 0','CELL_OPT 0'):
                self.assertIn(line, text)
            self.assertEqual(manifest['density_output']['stride'], [1,2,3])
            self.assertEqual(manifest['density_output']['each']['GEO_OPT'], 0)
            self.assertEqual(manifest['density_output']['scalar_unit'], 'e/bohr^3')
            self.assertFalse(manifest['density_output']['runtime_validated'])
        text, m = generate_input(self.water, self.settings)
        self.assertNotIn('&E_DENSITY_CUBE', text)
        self.assertFalse(m['density_output']['enabled'])
        self.assertIsNone(m['density_output']['stride'])

    def test_density_spin_condition_stride_and_version(self):
        with self.assertRaises(KitError):
            generate_input(self.water, replace(self.settings, spin_density=True))
        for stride in ((0,1,1), (-1,1,1), (1,1), (1.5,1,1), (True,1,1)):
            with self.subTest(stride=stride), self.assertRaises(KitError):
                generate_input(self.water, replace(self.settings, electron_density=True, cube_stride=stride))
        with self.assertRaises(KitError):
            generate_input(self.water, replace(self.settings, cube_stride=(1,1,1)))
        for spin_requested in (True, False):
            text, m = generate_input(self.water, replace(self.settings, charge=1, multiplicity=2,
                                                        electron_density=not spin_requested, spin_density=spin_requested))
            self.assertIn('UKS T', text)
            self.assertIn('STRIDE 1 1 1', text)
            self.assertNotIn('&SPIN_DENSITY_CUBE', text)
            self.assertTrue(m['density_output']['electron_density'])
            self.assertTrue(m['density_output']['spin_density'])
        for version in CP2K_VERSIONS:
            _, m = generate_input(self.water, replace(self.settings, electron_density=True, cp2k_version=version))
            self.assertEqual(m['target_version'], version)
            self.assertEqual(m['density_output']['reference_version'], 'CP2K '+version)
            self.assertIn('/v'+version+'/', m['density_output']['source'])
            self.assertEqual(len(m['density_output']['definition_sha256']), 64)
            if version == '2024.3':
                self.assertIsNone(m['density_output']['manual_source'])
            else:
                self.assertIn(version.replace('.', '_'), m['density_output']['manual_source'])
        with self.assertRaises(KitError):
            generate_input(self.water, replace(self.settings, cp2k_version='2027.1'))

    def test_density_cli(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()):
            out = Path(tmp)/'h2.inp'
            args = ['generate-input', '--write-json', str(FIXTURES/'trajectory.xyz'), '--periodic','none','-o',str(out),
                    '--electron-density','--cube-stride','1','2','3','--cp2k-version','2024.1']
            self.assertEqual(main(args),0)
            manifest = json.loads(Path(str(out)+'.json').read_text())
            self.assertEqual(manifest['density_output']['stride'],[1,2,3])
            self.assertEqual(manifest['target_version'],'2024.1')
            bad = Path(tmp)/'bad.inp'
            self.assertEqual(main(['generate-input', str(FIXTURES/'trajectory.xyz'), '--periodic','none',
                                   '-o',str(bad),'--spin-density']),2)
            self.assertFalse(bad.exists())

    def test_plain_xyz_explicit_periodicity(self):
        h2 = read_xyz(FIXTURES / "trajectory.xyz", 0)
        with self.assertRaises(KitError):
            generate_input(h2, InputSettings())
        _, m = generate_input(h2, self.settings)
        self.assertEqual(m["generated_structure"]["pbc"], [False]*3)


if __name__ == "__main__":
    unittest.main()
