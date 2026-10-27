"""Synthetic preparation checks only; no CP2K, MPI or scheduler invocation."""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.structure import read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry

SCRIPT = Path(__file__).resolve().parents[1]/'examples/admm-ri-validation/prepare.py'
spec = importlib.util.spec_from_file_location('prepare_admm_ri', SCRIPT)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class NativeValidationPreparationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='cp2kkit-native-prep-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root/'sources'
        self.data.mkdir()
        (self.data/'BASIS_MOLOPT').write_text(''.join(
            basis_entry(el, f'DZVP-MOLOPT-SR-GTH-q{q}') for el, q in (('H', 1), ('O', 6))))
        (self.data/'BASIS_ADMM_UZH').write_text(''.join(
            basis_entry(el, f'admm-dzp-q{q}') for el, q in (('H', 1), ('O', 6))))
        (self.data/'GTH_POTENTIALS').write_text(''.join(
            potential_entry(el, q, f'GTH-PBE-q{q}') for el, q in (('H', 1), ('O', 6))))
        (self.data/'t_c_g.dat').write_text('Synthetic bytes, not an actual CP2K table\n')
        self.output = self.root/'bundle'

    def prepare(self):
        with redirect_stdout(io.StringIO()):
            return prep.prepare(self.data, self.output)

    def test_six_cases_identity_portable_data_and_unknown_results(self):
        original = {p.name: p.read_bytes() for p in self.data.iterdir()}
        self.prepare()
        matrix = json.loads((self.output/'case-matrix.json').read_text())
        self.assertEqual(len(matrix['cases']), 6)
        self.assertEqual(matrix['generator_version'], '0.3.6')
        self.assertIsNone(matrix['actual_binary_identity'])
        self.assertIsNone(matrix['energy_acceptance_tolerance_hartree'])
        self.assertEqual(len(matrix['comparison_pairs']), 7)
        baseline = json.loads((self.output/'01-direct/water.inp.json').read_text())
        structure = read_structure(self.output/'water.xyz')
        # An explicit cell does not center atoms: keep the smoke molecule inside.
        self.assertTrue(all(6. < x < 10. for row in structure.positions for x in row))
        common = InputSettings.from_config(matrix['common_requested_settings'])
        for record, (_, admm, ri, variant) in zip(matrix['cases'], prep.CASES):
            directory = self.output/record['id']
            manifest = json.loads((directory/'water.inp.json').read_text())
            self.assertEqual(record['input_sha256'], prep.identity(directory/'water.inp')['sha256'])
            self.assertEqual(manifest['input_sha256'], record['input_sha256'])
            self.assertEqual(manifest['generated_structure'], baseline['generated_structure'])
            self.assertEqual(manifest['explicit_electron_count'], 8)
            for key in baseline['settings']:
                if key not in {'admm', 'ri_hfx', 'admm_variant'}:
                    self.assertEqual(manifest['settings'][key], baseline['settings'][key], key)
            for element, kind in manifest['kinds'].items():
                self.assertEqual({k: v for k, v in kind.items() if k != 'aux_fit'}, baseline['kinds'][element])
            for key in ('fraction', 'interaction_potential', 'omega', 'cutoff_radius_angstrom',
                        'screen_on_initial_p', 'eps_schwarz'):
                self.assertEqual(manifest['method_profile']['hfx'][key], baseline['method_profile']['hfx'][key])
            text, replay = generate_input(structure, replace(common, admm=admm, ri_hfx=ri, admm_variant=variant))
            self.assertEqual(text, (directory/'water.inp').read_text())
            self.assertEqual(json.loads(json.dumps(replay)), manifest)
            for key in ('process_exit_status', 'native_syntax_accepted', 'scf_converged', 'clean_exit',
                        'energy_hartree', 'wall_time_seconds', 'peak_memory_bytes'):
                self.assertIsNone(record[key])
            for name, raw in original.items():
                self.assertEqual((directory/name).read_bytes(), raw)
                self.assertTrue((directory/name).is_symlink())
                self.assertEqual((directory/name).resolve(), (self.output/'data'/name).resolve())
            if ri:
                self.assertEqual(record['ri']['basis_parent_role'], 'AUX_FIT' if admm else 'ORB')
            if admm:
                self.assertEqual(record['admm']['variant'], variant)
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.data.iterdir()})

    def test_existing_directory_and_symlink_refused(self):
        self.output.mkdir()
        sentinel = self.output/'old.wfn'
        sentinel.write_text('Protected existing result\n')
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(list(self.output.iterdir()), [sentinel])
        alias = self.root/'alias'
        alias.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(FileExistsError), redirect_stdout(io.StringIO()):
            prep.prepare(self.data, alias)
        self.assertEqual(sentinel.read_text(), 'Protected existing result\n')

    def test_missing_data_fails_before_publication(self):
        (self.data/'t_c_g.dat').unlink()
        with self.assertRaises(FileNotFoundError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_generation_failure_leaves_inspectable_partial_not_matrix(self):
        with patch.object(prep, 'generate_input', side_effect=ValueError('injected failure')):
            with self.assertRaisesRegex(ValueError, 'injected failure'):
                self.prepare()
        self.assertTrue((self.output/'water.xyz').exists())
        self.assertFalse((self.output/'case-matrix.json').exists())
        self.assertFalse((self.output/'01-direct/water.inp').exists())
        self.assertEqual(len(list(self.data.iterdir())), 4)
        with self.assertRaises(FileExistsError):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
