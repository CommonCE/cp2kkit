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
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.inputgen import BASES, MULTIWFN_CITATIONS, VALENCE, InputSettings, generate_input, write_input
from cp2kkit.structure import Structure, read_restart, read_xyz

FIXTURES = Path(__file__).parent / "fixtures"


class InputGenerationTests(unittest.TestCase):
    def setUp(self):
        self.water = Structure(["O", "H", "H"], [[0., 0., 0.], [0.76, 0., 0.58], [-0.76, 0., 0.58]],
                               None, None, {"path": "synthetic"})
        self.settings = InputSettings(periodic="NONE")

    def test_defaults_and_provenance(self):
        text, manifest = generate_input(self.water, self.settings)
        self.assertIn("RUN_TYPE ENERGY", text)
        self.assertIn("METHOD GPW", text)
        self.assertIn("POTENTIAL GTH-PBE-q6", text)
        self.assertIn("BASIS_SET DZVP-MOLOPT-SR-GTH-q1", text)
        self.assertIn("POISSON_SOLVER WAVELET", text)
        self.assertNotIn("VDW_POTENTIAL", text)
        self.assertEqual(manifest["valence_electron_count"], 8)
        self.assertEqual(manifest["effective_eps_scf"], 5e-6)
        self.assertEqual(manifest["input_sha256"], hashlib.sha256(text.encode()).hexdigest())
        self.assertFalse(manifest["runtime_validated"])
        self.assertIsNone(manifest["runtime_version"])
        self.assertTrue(manifest["coordinates_translated"])
        self.assertEqual(self.water.positions[0], [0., 0., 0.])
        self.assertEqual((text, manifest), generate_input(self.water, self.settings))

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
        self.assertIn("ADDED_MOS 20", text)
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
        # Minimal synthetic headers test validation, not usable basis coefficients.
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "BASIS_MOLOPT").write_text("H DZVP-MOLOPT-SR-GTH-q1\nO DZVP-MOLOPT-SR-GTH-q6\n")
            (d / "GTH_POTENTIALS").write_text("H GTH-PBE-q1\nO GTH-PBE-q6\n")
            (d / "dftd3.dat").write_text("synthetic test only\n")
            text, m = generate_input(self.water, replace(self.settings, data_dir=tmp, dispersion="d3"))
            self.assertEqual(set(m["data_sources"]), {"basis", "potential", "dispersion"})
            self.assertIn(str(d / "GTH_POTENTIALS"), text)
            self.assertEqual(m["data_sources"]["basis"]["sha256"], hashlib.sha256((d / "BASIS_MOLOPT").read_bytes()).hexdigest())
            (d / "BASIS_MOLOPT").write_text("# H DZVP-MOLOPT-SR-GTH-q1\nO DZVP-MOLOPT-SR-GTH-q6\n")
            with self.assertRaisesRegex(KitError, "has no H"):
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
            argv = ["generate-input", str(FIXTURES / "trajectory.xyz"), "--periodic", "none", "-o", str(out)]
            self.assertEqual(main(argv), 0)
            self.assertEqual(main(argv), 5)
            self.assertEqual(json.loads(Path(str(out) + ".json").read_text())["source_structure"]["frame"], 1)
            unknown = Path(tmp) / "unknown.inp"
            self.assertEqual(main(["generate-input", str(FIXTURES / "trajectory.xyz"), "-o", str(unknown)]), 2)
            self.assertFalse(unknown.exists())

    def test_plain_xyz_explicit_periodicity(self):
        h2 = read_xyz(FIXTURES / "trajectory.xyz", 0)
        with self.assertRaises(KitError):
            generate_input(h2, InputSettings())
        _, m = generate_input(h2, self.settings)
        self.assertEqual(m["generated_structure"]["pbc"], [False]*3)


if __name__ == "__main__":
    unittest.main()
