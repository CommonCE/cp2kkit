"""Synthetic surface preparation only; never run CP2K or submit jobs."""
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cp2kkit import __version__
from cp2kkit.structure import read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry

SCRIPT = Path(__file__).resolve().parents[1]/'examples/surface-density/prepare.py'
spec = importlib.util.spec_from_file_location('surface_prepare', SCRIPT)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class SurfacePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root/'source'
        self.data.mkdir()
        elements = (('B', 3), ('N', 5), ('H', 1), ('O', 6), ('C', 4))
        (self.data/'BASIS_MOLOPT').write_text(''.join(
            basis_entry(el, f'DZVP-MOLOPT-SR-GTH-q{q}') for el, q in elements))
        (self.data/'GTH_POTENTIALS').write_text(''.join(
            potential_entry(el, q, f'GTH-PBE-q{q}') for el, q in elements))
        self.output = self.root/'new'

    def prepare(self):
        with redirect_stdout(io.StringIO()):
            return prep.prepare(self.data, self.output)

    def test_models_bundles_states_portability_hashes(self):
        self.prepare()
        matrix = json.loads((self.output/'case-matrix.json').read_text())
        self.assertEqual(matrix['generator_version'], __version__)
        self.assertEqual(len(matrix['cases']), 9)
        for case in matrix['cases']:
            path = self.output/case['input']
            self.assertEqual(case['input_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertIsNone(case['process_exit_status'])
            self.assertIsNone(case['scf_converged'])
            self.assertIn('BASIS_SET_FILE_NAME data/BASIS_MOLOPT', path.read_text())
            self.assertIn('POTENTIAL_FILE_NAME data/GTH_POTENTIALS', path.read_text())
            for name in prep.DATA_FILES:
                self.assertEqual((path.parent/'data'/name).read_bytes(), (self.data/name).read_bytes())
        for model, count, electrons in [('water', 21, 80), ('ammonia', 22, 80), ('carbon-dioxide', 21, 88)]:
            directory = self.output/model
            structure = read_structure(directory/'adsorption.extxyz')
            self.assertEqual(len(structure.symbols), count)
            self.assertEqual(structure.pbc, [True, True, True])
            self.assertEqual(structure.cell[2], [0, 0, 18])
            manifest = json.loads((directory/'density.inp.json').read_text())
            components = manifest['density_difference']['components']
            self.assertEqual(components['whole']['explicit_electron_count'], electrons)
            self.assertEqual(components['fragment_a']['explicit_electron_count'], 72)
            for component in components.values():
                self.assertEqual(component['settings']['charge'], 0)
                self.assertEqual(component['settings']['multiplicity'], 1)
                self.assertEqual(component['generated_structure']['cell'], components['whole']['generated_structure']['cell'])
            self.assertEqual(len((directory/'density-atom-map.csv').read_text().splitlines()), count+1)

    def test_geometry_determinism_and_surface_distance(self):
        self.assertEqual(list(prep.geometries()), list(prep.geometries()))
        for name, text in prep.geometries():
            path = self.root/(name+'.extxyz')
            path.write_text(text)
            structure = read_structure(path)
            self.assertTrue(all(row[2] == 6 for row in structure.positions[:18]))
            self.assertTrue(all(row[2] >= 9.2 for row in structure.positions[18:]))

    def test_existing_directory_symlink_and_missing_data(self):
        self.output.mkdir()
        sentinel = self.output/'result.wfn'
        sentinel.write_text('preserve')
        with self.assertRaises(FileExistsError):
            self.prepare()
        alias = self.root/'alias'
        alias.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            prep.prepare(self.data, alias)
        self.assertEqual(sentinel.read_text(), 'preserve')
        (self.data/'BASIS_MOLOPT').unlink()
        with self.assertRaises(FileNotFoundError):
            prep.prepare(self.data, self.root/'missing-data')
        self.assertFalse((self.root/'missing-data').exists())

    def test_portable_renderer_rejects_unexpected_data(self):
        with self.assertRaises(ValueError):
            prep.portable_input({'input_text': 'BASIS_SET_FILE_NAME wrong-library\n'})


if __name__ == '__main__':
    unittest.main()
