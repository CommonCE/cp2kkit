"""D3 whole-line filename regressions; no CP2K execution or native certification."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cp2k_data import cp2k_long_path, cp2k_path
from cp2kkit.errors import KitError
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.structure import Structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry


class DispersionPathTests(unittest.TestCase):
    def setUp(self):
        self.atom = Structure(["O"], [[0., 0., 0.]], None, None, {"path": "synthetic.xyz"})
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CP2K_DATA_DIR", None)

    def test_d3_and_bj_default_filename_is_not_quoted(self):
        for basis in ("molopt-sr-dzvp", "ae-pob-tzvp"):
            for dispersion in ("d3", "d3bj"):
                with self.subTest(basis=basis, dispersion=dispersion):
                    text, m = generate_input(self.atom, InputSettings(periodic="NONE", basis=basis, dispersion=dispersion))
                    self.assertIn("\n          PARAMETER_FILE_NAME dftd3.dat\n", text)
                    self.assertNotIn('PARAMETER_FILE_NAME "dftd3.dat"', text)
                    self.assertEqual(m["input_text"], text)
                    self.assertEqual(m["method_profile"]["dispersion_reference"], "PBE")

    def test_literal_internal_spaces_and_long_paths_are_preserved(self):
        for path in ("dftd3.dat", "/data/my parameters/dftd3.dat", "/data/"+80*"x"+"/dftd3.dat"):
            with self.subTest(path=path):
                self.assertEqual(cp2k_long_path(path), path)
        # Ordinary token-valued keywords retain their separate quoting contract.
        self.assertEqual(cp2k_path("/data/my basis/file"), '"/data/my basis/file"')

    def test_ambiguous_or_injected_paths_rejected_without_stripping(self):
        for path in ("", " dftd3.dat", "dftd3.dat ", "/data/#name/dftd3.dat", "/data/!name/dftd3.dat",
                     '"/data/dftd3.dat"', "x\n&END", "x\tfile", "${FILE}", "@SET", "a\\b"):
            with self.subTest(path=path), self.assertRaises(KitError):
                cp2k_long_path(path)

    def test_checked_data_directory_with_spaces_is_emitted_as_whole_line(self):
        with tempfile.TemporaryDirectory(prefix="cp2kkit-d3-") as tmp:
            root = Path(tmp)/"data with spaces"
            root.mkdir()
            (root/"BASIS_MOLOPT").write_text(basis_entry("O", "DZVP-MOLOPT-SR-GTH-q6"))
            (root/"GTH_POTENTIALS").write_text(potential_entry("O", 6, "GTH-PBE-q6"))
            (root/"dftd3.dat").write_text("invented hash fixture, NOT real D3 parameters\n")
            text, m = generate_input(self.atom, InputSettings(periodic="NONE", dispersion="d3bj", data_dir=str(root)))
            self.assertIn("PARAMETER_FILE_NAME "+str(root/"dftd3.dat")+"\n", text)
            self.assertIn('BASIS_SET_FILE_NAME '+str(root/"BASIS_MOLOPT")+'\n', text)
            self.assertEqual(m["data_sources"]["dispersion"]["path"], str(root/"dftd3.dat"))
            self.assertRegex(m["data_sources"]["dispersion"]["sha256"], r"^[0-9a-f]{64}$")

    def test_no_dispersion_emits_no_parameter_file_keyword(self):
        text, _ = generate_input(self.atom, InputSettings(periodic="NONE"))
        self.assertNotIn("PARAMETER_FILE_NAME", text)
