"""Synthetic CUBE preparation tests; no quantum calculation or scheduler calls."""
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit import __version__
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.structure import read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry

SCRIPT = Path(__file__).resolve().parents[1]/'examples/cube-validation/prepare.py'
spec = importlib.util.spec_from_file_location('cube_validation_prepare', SCRIPT)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class CubeValidationPreparationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='cp2kkit-cube-prep-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.data = self.root/'sources'
        self.data.mkdir()
        (self.data/'BASIS_MOLOPT').write_text(''.join(
            basis_entry(el, f'DZVP-MOLOPT-SR-GTH-q{q}') for el, q in (('H', 1), ('O', 6))))
        (self.data/'GTH_POTENTIALS').write_text(''.join(
            potential_entry(el, q, f'GTH-PBE-q{q}') for el, q in (('H', 1), ('O', 6))))
        self.output = self.root/'bundle'

    def prepare(self):
        with redirect_stdout(io.StringIO()):
            return prep.prepare(self.data, self.output)

    def test_identity_geometry_states_requests_and_replay(self):
        original = {p.name: p.read_bytes() for p in self.data.iterdir()}
        self.prepare()
        matrix = json.loads((self.output/'case-matrix.json').read_text())
        self.assertEqual(matrix['generator_version'], __version__)
        self.assertEqual(matrix['target_cp2k_version'], '2026.2')
        self.assertIsNone(matrix['actual_binary_identity'])
        self.assertEqual(len(matrix['cases']), 3)
        self.assertEqual(matrix['geometry'], prep.identity(self.output/'water.xyz'))
        self.assertEqual(matrix['preparation_source'], prep.identity(SCRIPT))
        checkout = SCRIPT.parents[2]
        self.assertEqual(matrix['validation_protocol'], prep.identity(checkout/'docs/cube-native-validation.md'))
        self.assertEqual((self.output/'VALIDATION.md').read_bytes(),
                         (checkout/'docs/cube-native-validation.md').read_bytes())
        for name, evidence in matrix['implementation_sources'].items():
            self.assertEqual(evidence, prep.identity(checkout/name))
        for name in prep.DATA_FILES:
            self.assertEqual(matrix['data_sources'][name], prep.identity(self.data/name))
            self.assertEqual(matrix['staged_data'][name], prep.identity(self.output/'data'/name))
            self.assertEqual((self.output/'data'/name).read_bytes(), original[name])
        common = InputSettings.from_config(matrix['common_requested_settings'])
        structure = read_structure(self.output/'water.xyz')
        baseline = None
        for record, (name, overrides), electrons, spin in zip(
                matrix['cases'], prep.CASES, (8, 8, 7), ('RKS', 'RKS', 'UKS')):
            with self.subTest(case=name):
                path = self.output/record['input']
                manifest = json.loads((self.output/record['sidecar']).read_text())
                self.assertEqual(record['input_sha256'], prep.identity(path)['sha256'])
                self.assertEqual(record['generator_input_sha256'], manifest['input_sha256'])
                self.assertEqual(manifest['input_sha256'],
                                 hashlib.sha256(manifest['input_text'].encode()).hexdigest())
                self.assertNotEqual(record['input_sha256'], record['generator_input_sha256'])
                self.assertEqual(path.read_text(), prep.portable_input(manifest))
                text, replay = generate_input(structure, replace(common, **overrides))
                self.assertEqual(manifest['input_text'], text)
                self.assertEqual(manifest, json.loads(json.dumps(replay)))
                self.assertEqual(record['requested_settings'], manifest['settings'])
                self.assertEqual(record['spin_treatment'], spin)
                self.assertEqual(record['explicit_electron_count'], electrons)
                self.assertEqual(manifest['basis_validation']['status'], 'data_checked')
                for key, value in overrides.items():
                    self.assertEqual(manifest['settings'][key], value)
                for key in ('eps_scf', 'cutoff', 'rel_cutoff', 'max_scf', 'max_outer_scf',
                            'cell', 'periodic', 'functional', 'basis', 'run_type', 'kpoints',
                            'dispersion', 'smearing', 'cube_stride'):
                    self.assertEqual(manifest['settings'][key], matrix['common_requested_settings'][key])
                if baseline is None:
                    baseline = manifest
                self.assertEqual(manifest['generated_structure'], baseline['generated_structure'])
                self.assertEqual(manifest['kinds'], baseline['kinds'])
                self.assertEqual(manifest['source_structure'], baseline['source_structure'])
                for field in prep.PENDING_FIELDS:
                    self.assertIsNone(record[field], field)
                self.assertEqual(record['checks_status'], 'pending')
                self.assertEqual(record['expected_requests']['density'], manifest['density_output'])
                for key in ('potential', 'orbitals'):
                    self.assertEqual(record['expected_requests'][key], manifest['extra_cube_output'][key])
                self.assertEqual(record['expected_requests']['density']['spin_density'], spin == 'UKS')
                self.assertFalse(record['expected_requests']['potential']['sign_conversion_applied'])
                self.assertTrue(all(record['expected_requests'][key]['enabled']
                                    for key in ('density', 'potential', 'orbitals')))
                for filename in prep.DATA_FILES:
                    self.assertEqual((path.parent/filename).read_bytes(), original[filename])
                    self.assertEqual((path.parent/filename).resolve(), (self.output/'data'/filename).resolve())
        channels = [r['expected_frontier_channels'] for r in matrix['cases']]
        self.assertEqual([len(c) for c in channels], [1, 1, 2])
        self.assertEqual(channels[0][0]['requested_occupied_indices'], [4])
        self.assertEqual(channels[0][0]['requested_virtual_indices'], [5])
        self.assertEqual(channels[1][0]['requested_occupied_indices'], [3, 4])
        self.assertEqual(channels[1][0]['requested_virtual_indices'], [5, 6])
        self.assertEqual([(c['channel'], c['cp2k_spin_index'], c['homo_index'], c['lumo_index'])
                          for c in channels[2]], [('alpha', 1, 4, 5), ('beta', 2, 3, 4)])
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.data.iterdir()})

    def test_existing_paths_and_dangling_symlinks_preserved(self):
        self.output.mkdir()
        sentinel = self.output/'old.wfn'
        sentinel.write_bytes(b'preserve')
        alias = self.root/'alias'
        alias.symlink_to(self.output, target_is_directory=True)
        dangling = self.root/'dangling'
        dangling.symlink_to(self.root/'missing', target_is_directory=True)
        regular = self.root/'regular'
        regular.write_text('preserve')
        for path in (self.output, alias, dangling, regular):
            with self.subTest(path=path), self.assertRaises(FileExistsError):
                prep.prepare(self.data, path)
        self.assertEqual(list(self.output.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b'preserve')
        self.assertTrue(dangling.is_symlink())
        self.assertEqual(regular.read_text(), 'preserve')

    def test_missing_data_fails_before_directory_creation(self):
        (self.data/'GTH_POTENTIALS').unlink()
        with self.assertRaises(FileNotFoundError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def assert_no_published_text(self):
        self.assertFalse(list(self.output.rglob('*.inp')))
        self.assertFalse(list(self.output.rglob('*.json')))
        self.assertFalse(list(self.output.rglob('*.tmp')))
        self.assertFalse((self.output/'VALIDATION.md').exists())

    def test_malformed_selected_data_rejected_without_inputs(self):
        (self.data/'BASIS_MOLOPT').write_text('H invalid\n')
        with self.assertRaises(KitError):
            self.prepare()
        self.assert_no_published_text()

    def test_generation_failure_retains_inspectable_data_but_no_inputs(self):
        generate = prep.generate_input
        calls = 0

        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError('injected generation failure')
            return generate(*args)

        with patch.object(prep, 'generate_input', side_effect=fail_second):
            with self.assertRaisesRegex(ValueError, 'injected generation failure'):
                self.prepare()
        self.assert_no_published_text()
        self.assertTrue((self.output/'water.xyz').exists())
        self.assertTrue((self.output/'data/BASIS_MOLOPT').exists())
        with self.assertRaises(FileExistsError):
            self.prepare()

    def test_copy_failure_cleans_partial_copy_only(self):
        def broken_copy(source, target):
            target.write(b'partial')
            raise OSError('injected copy failure')

        with patch.object(prep.shutil, 'copyfileobj', side_effect=broken_copy):
            with self.assertRaisesRegex(OSError, 'injected copy failure'):
                self.prepare()
        self.assertFalse((self.output/'data/BASIS_MOLOPT').exists())
        self.assertTrue((self.data/'BASIS_MOLOPT').exists())
        self.assert_no_published_text()

    def test_changed_data_copy_rejected(self):
        copy = prep.shutil.copyfileobj

        def altered_copy(source, target):
            copy(source, target)
            target.write(b'changed')

        with patch.object(prep.shutil, 'copyfileobj', side_effect=altered_copy):
            with self.assertRaisesRegex(ValueError, 'Data changed during staging'):
                self.prepare()
        self.assert_no_published_text()

    def test_publication_collision_rolls_back_owned_inputs_not_foreign_file(self):
        import os
        link = os.link
        calls = 0
        collision = self.output/'01-rks-ot/water.inp.json'

        def collide(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                Path(target).write_text('foreign identity')
            return link(source, target)

        with patch('cp2kkit.io.os.link', side_effect=collide):
            with self.assertRaises(OutputExists):
                self.prepare()
        self.assertFalse((self.output/'01-rks-ot/water.inp').exists())
        self.assertEqual(collision.read_text(), 'foreign identity')
        self.assertFalse(list(self.output.rglob('*.tmp')))
        self.assertFalse((self.output/'case-matrix.json').exists())

    def test_portable_renderer_rejects_unexpected_references(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected generated data reference'):
            prep.portable_input({'input_text': 'BASIS_SET_FILE_NAME wrong\n',
                                 'emitted_data_files': {'basis': ['BASIS_MOLOPT'],
                                                        'potential': 'GTH_POTENTIALS'}})


if __name__ == '__main__':
    unittest.main()
