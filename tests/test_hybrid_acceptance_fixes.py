"""Synthetic regression for returned-run findings; never execute CP2K or submit."""
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cp2kkit.hybrid import cell_heights, hybrid_runtime_file
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.errors import KitError
from cp2kkit.structure import BOHR_TO_ANGSTROM, read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry


class HybridAcceptanceFixTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='cp2kkit-hybrid-fixes-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root/('long synthetic data directory ' * 3)
        self.data.mkdir()
        self.source = self.root/'water.xyz'
        self.source.write_text('3\nsynthetic\nO 0 0 0\nH 1 0 0\nH 0 1 0\n')
        self.water = read_structure(self.source)
        (self.data/'BASIS_MOLOPT').write_text(basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6')+
                                              basis_entry('H', 'DZVP-MOLOPT-SR-GTH-q1'))
        (self.data/'BASIS_ADMM_UZH').write_text(basis_entry('O', 'admm-dzp-q6')+
                                                basis_entry('H', 'admm-dzp-q1'))
        (self.data/'GTH_POTENTIALS').write_text(potential_entry('O', 6, 'GTH-PBE-q6')+
                                                potential_entry('H', 1, 'GTH-PBE-q1'))
        (self.data/'t_c_g.dat').write_text('Synthetic table bytes, not a numerical table\n')
        self.settings = InputSettings(functional='PBE0', periodic='XYZ', cell=(16., 16., 16.),
                                      data_dir=str(self.data))
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def generate(self, **changes):
        return generate_input(self.water, replace(self.settings, **changes))

    def test_portable_automatic_files_preserve_absolute_provenance(self):
        for algorithm in ({}, {'admm': True}, {'ri_hfx': True}):
            for environment in (False, True):
                with self.subTest(algorithm=algorithm, environment=environment):
                    with patch.dict(os.environ, CP2K_DATA_DIR=str(self.data)):
                        text, m = self.generate(**algorithm, data_dir=None if environment else str(self.data))
                    expected = ['BASIS_MOLOPT'] + (['BASIS_ADMM_UZH'] if algorithm.get('admm') else [])
                    self.assertEqual(m['emitted_data_files']['basis'], sorted(expected))
                    self.assertEqual(m['emitted_data_files']['potential'], 'GTH_POTENTIALS')
                    self.assertEqual(m['emitted_data_files']['hfx_truncated_gamma'], 't_c_g.dat')
                    self.assertNotIn(str(self.data), text)
                    self.assertIn('T_C_G_DATA t_c_g.dat\n', text)
                    self.assertTrue(any('CP2K_DATA_DIR' in w for w in m['warnings']))
                    for source in m['data_sources'].values():
                        self.assertTrue(Path(source['path']).is_absolute())
                        self.assertEqual(source['sha256'], hashlib.sha256(Path(source['path']).read_bytes()).hexdigest())
                    self.assertGreater(len(m['data_sources']['hfx_truncated_gamma']['path']), 80)
                    self.assertFalse(m['runtime_validated'])

    def test_explicit_sources_and_outside_root_are_not_rebased(self):
        orb, potential = self.data/'BASIS_MOLOPT', self.data/'GTH_POTENTIALS'
        text, m = self.generate(basis_files=(str(orb),), potential_files=(str(potential),))
        self.assertIn('BASIS_SET_FILE_NAME '+str(orb.resolve())+'\n', text)
        self.assertIn('POTENTIAL_FILE_NAME '+str(potential.resolve())+'\n', text)
        outside = self.root/'BASIS_MOLOPT'
        outside.write_bytes(orb.read_bytes())
        self.assertEqual(hybrid_runtime_file(str(outside), self.data), str(outside))
        self.assertEqual(hybrid_runtime_file(str(orb), None), str(orb))
        self.assertEqual(hybrid_runtime_file(str(orb), self.data, explicit=True), str(orb))
        self.assertEqual(hybrid_runtime_file('BASIS_MOLOPT_UZH', self.data), 'BASIS_MOLOPT_UZH')
        self.assertEqual(m['kinds']['O']['basis_source']['path'], str(orb.resolve()))

    def test_data_aliases_remain_protected_publication_targets(self):
        table = self.data/'t_c_g.dat'
        alias = self.root/'table-hardlink.inp'
        os.link(table, alias)
        original = table.read_bytes()
        for target in (table, alias, self.data/'BASIS_MOLOPT', self.data/'GTH_POTENTIALS'):
            with self.subTest(target=target), self.assertRaises(KitError):
                write_input(self.water, replace(self.settings, ri_hfx=True), target)
        self.assertEqual(table.read_bytes(), original)

    def test_explicit_force_printing_is_hybrid_energy_force_only(self):
        for algorithm in ({}, {'admm': True}, {'ri_hfx': True}):
            for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
                with self.subTest(algorithm=algorithm, task=task):
                    text, m = self.generate(**algorithm, run_type=task)
                    active = task == 'ENERGY_FORCE'
                    self.assertEqual(text.count('&FORCES ON'), int(active))
                    self.assertEqual(m['force_output']['explicit_print'], active)
                    self.assertEqual(m['force_output']['unit'], 'hartree/bohr' if active else None)
                    self.assertFalse(m['force_output']['runtime_validated'])
                    self.assertIn('PRINT_LEVEL LOW', text)
                    if active:
                        self.assertIn('FILENAME __STD_OUT__', text)
                        stack = []
                        for line in text.splitlines():
                            fields = line.split()
                            if not fields or fields[0].startswith('#'):
                                continue
                            if fields[0] == '&END':
                                self.assertEqual(stack.pop(), fields[1])
                            elif fields[0].startswith('&'):
                                if fields[0] == '&FORCES':
                                    self.assertEqual(stack, ['FORCE_EVAL', 'PRINT'])
                                stack.append(fields[0][1:])
                        self.assertEqual(stack, [])
        text, m = self.generate(functional='PBE', run_type='ENERGY_FORCE')
        self.assertNotIn('&FORCES', text)
        self.assertFalse(m['force_output']['explicit_print'])
        self.assertIn(str(self.data/'BASIS_MOLOPT'), text)  # Preserve non-hybrid path policy.

    def test_hse06_range_warning_and_no_silent_model_change(self):
        for algorithm in ({}, {'admm': True}, {'ri_hfx': True},
                          {'ri_hfx': True, 'ri_metric': 'TRUNCATED', 'ri_cutoff_radius': 1.7}):
            with self.subTest(algorithm=algorithm):
                text, m = self.generate(functional='HSE06', **algorithm)
                estimate = m['method_profile']['hfx']['short_range_cutoff_estimate']
                self.assertAlmostEqual(estimate['value_angstrom'], 14.278692847881375, places=10)
                self.assertEqual(estimate['half_minimum_cell_face_spacing_angstrom'], 8.)
                self.assertTrue(estimate['exceeds_half_cell'])
                self.assertFalse(estimate['runtime_observed'])
                self.assertEqual(estimate['selection'], 'source_derived')
                self.assertTrue(any('unphysical total energies' in w for w in m['warnings']))
                self.assertIn('OMEGA 0.11\n', text)
                interaction = text.split('&INTERACTION_POTENTIAL\n')[1].split('&END INTERACTION_POTENTIAL')[0]
                self.assertNotIn('CUTOFF_RADIUS', interaction)
                self.assertEqual(m['settings']['hf_eps_schwarz'], 1e-6)
                self.assertEqual(m['generated_structure']['cell'], [[16., 0., 0.], [0., 16., 0.], [0., 0., 16.]])
                self.assertIsNone(m['method_profile']['hfx']['cutoff_radius_angstrom'])

    def test_hse06_range_estimate_does_not_certify_larger_cells(self):
        for periodic, cell in (('NONE', (16., 16., 16.)), ('XYZ', (64., 64., 64.))):
            text, m = self.generate(functional='HSE06', periodic=periodic, cell=cell)
            estimate = m['method_profile']['hfx']['short_range_cutoff_estimate']
            self.assertEqual(estimate['exceeds_half_cell'], False if periodic == 'XYZ' else None)
            self.assertFalse(any('unphysical total energies' in w for w in m['warnings']))
            self.assertFalse(m['method_profile']['hfx']['runtime_validated'])
            self.assertNotIn('CUTOFF_RADIUS', text)
        _, m = self.generate()
        self.assertIsNone(m['method_profile']['hfx']['short_range_cutoff_estimate'])

    def test_hse06_skew_cell_bound_and_explicit_screening_dependence(self):
        cell = [[32., 0., 0.], [31., 4., 0.], [0., 0., 32.]]
        water = replace(self.water, cell=cell, pbc=[True]*3)
        _, m = generate_input(water, replace(self.settings, functional='HSE06', cell=None))
        estimate = m['method_profile']['hfx']['short_range_cutoff_estimate']
        self.assertAlmostEqual(estimate['half_minimum_cell_face_spacing_angstrom'], min(cell_heights(cell))/2)
        self.assertTrue(estimate['exceeds_half_cell'])
        values = []
        for eps in (1e-4, 1e-6, 1e-12):
            _, m = self.generate(functional='HSE06', hf_eps_schwarz=eps)
            value = m['method_profile']['hfx']['short_range_cutoff_estimate']['value_angstrom']
            r = value/BOHR_TO_ANGSTROM
            self.assertAlmostEqual(math.erfc(.11*r)/r/eps, 1., places=12)
            values.append(value)
        self.assertEqual(values, sorted(values))

    def test_cli_force_output_and_short_names(self):
        out = self.root/'cli.inp'
        result = subprocess.run([sys.executable, '-m', 'cp2kkit', 'generate-input', str(self.source),
                                 '--functional', 'HSE06', '--periodic', 'XYZ', '--cell', '16', '16', '16',
                                 '--ri-hfx', '--run-type', 'ENERGY_FORCE', '--data-dir', str(self.data),
                                 '--output', str(out), '--write-json'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('&FORCES ON', out.read_text())
        self.assertNotIn(str(self.data), out.read_text())
        m = json.loads(Path(str(out)+'.json').read_text())
        self.assertTrue(m['force_output']['explicit_print'])
        self.assertTrue(m['method_profile']['hfx']['short_range_cutoff_estimate']['exceeds_half_cell'])


if __name__ == '__main__':
    unittest.main()
