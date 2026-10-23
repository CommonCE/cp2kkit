"""Synthetic generation and mocked publication only; never run CP2K/Multiwfn."""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import build_parser
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.input_editor import FIELDS, applicable_entries
from cp2kkit.input_tui import command_arguments, run_interactive
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.ri_hfx import RI_BASIS_SIZES, acceleration_capabilities
from cp2kkit.structure import read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry
from tests.test_input_tui import TTY


class RIHFXTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='cp2kkit-ri-hfx-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root/'water.xyz'
        self.source.write_text('3\nsynthetic\nO 0 0 0\nH 1 0 0\nH 0 1 0\n')
        self.water = read_structure(self.source)
        self.data = self.root/'synthetic data'
        self.data.mkdir()
        self.orb = self.data/'BASIS_MOLOPT'
        self.orb.write_text(basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6')+
                            basis_entry('H', 'DZVP-MOLOPT-SR-GTH-q1'))
        (self.data/'GTH_POTENTIALS').write_text(potential_entry('O', 6, 'GTH-PBE-q6')+
                                              potential_entry('H', 1, 'GTH-PBE-q1'))
        (self.data/'t_c_g.dat').write_text('synthetic bytes, not a real truncation table\n')
        self.settings = InputSettings(functional='PBE0', periodic='NONE', ri_hfx=True, data_dir=str(self.data))
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def generate(self, **changes):
        return generate_input(self.water, replace(self.settings, **changes))

    def test_profiles_tasks_solvers_pbc_and_sizes(self):
        for functional in ('PBE0', 'HSE06'):
            for run_type in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
                for scf in ('ot', 'diag'):
                    for periodic in ('NONE', 'XYZ'):
                        for size in RI_BASIS_SIZES:
                            with self.subTest(f=functional, task=run_type, scf=scf, pbc=periodic, size=size):
                                text, m = self.generate(functional=functional, run_type=run_type, scf=scf,
                                                        periodic=periodic, cell=(16., 17., 18.), ri_basis_size=size)
                                hfx = m['method_profile']['hfx']
                                ri = hfx['ri']
                                self.assertEqual(text.count('&RI T\n'), 1)
                                self.assertEqual(text.count('AUTO_BASIS RI_HFX '+size+'\n'), 1)
                                self.assertIn('    SORT_BASIS EXP\n', text)
                                self.assertIn('          RI_METRIC HFX\n', text)
                                self.assertIn('          RI_FLAVOR RHO\n', text)
                                self.assertNotIn('&MEMORY', text)
                                self.assertNotIn('MAX_MEMORY', text)
                                self.assertNotIn('AUX_FIT', text)
                                self.assertNotIn('BASIS_SET RI_', text)
                                self.assertTrue(hfx['ri_hfx'])
                                self.assertFalse(hfx['admm'])
                                self.assertEqual(hfx['algorithm'], 'ri_gamma')
                                self.assertIsNone(hfx['max_memory_mib_per_mpi_process'])
                                self.assertIsNone(hfx['eps_storage_scaling'])
                                expected = 'SHORTRANGE' if functional == 'HSE06' else 'COULOMB' if periodic == 'NONE' else 'TRUNCATED'
                                self.assertEqual(ri['effective_metric_operator'], expected)
                                self.assertEqual(ri['effective_metric_omega_bohr_inverse'], hfx['omega'])
                                self.assertEqual(ri['effective_metric_cutoff_radius_angstrom'], hfx['cutoff_radius_angstrom'])
                                self.assertEqual(ri['basis_parent_role'], 'ORB')
                                self.assertEqual(ri['basis_size'], size)
                                self.assertFalse(ri['runtime_validated'])
                                self.assertFalse(m['runtime_validated'])
                                self.assertEqual(m['settings']['scf'], scf)
                                # AUTO_BASIS must belong to DFT and RI to HF (not KIND or SCF).
                                stack = []
                                for line in text.splitlines():
                                    parts = line.split()
                                    if not parts or parts[0].startswith('#'):
                                        continue
                                    if parts[0] == '&END':
                                        self.assertEqual(stack.pop(), parts[1])
                                    elif parts[0].startswith('&'):
                                        if parts[0] == '&RI':
                                            self.assertEqual(stack[-1], 'HF')
                                        stack.append(parts[0][1:])
                                    elif parts[0] == 'AUTO_BASIS':
                                        self.assertEqual(stack[-1], 'DFT')
                                self.assertEqual(stack, [])

    def test_off_preserves_direct_text_and_default_config(self):
        old = InputSettings.from_config({'functional': 'PBE0', 'periodic': 'NONE', 'data_dir': str(self.data)})
        self.assertFalse(old.ri_hfx)
        text, m = generate_input(self.water, old)
        self.assertEqual(text, self.generate(ri_hfx=False)[0])
        self.assertNotIn('AUTO_BASIS', text)
        self.assertNotIn('&RI', text)
        self.assertIn('MAX_MEMORY 512', text)
        self.assertEqual(m['method_profile']['hfx']['algorithm'], 'direct_four_center')
        self.assertNotIn('ri', m['method_profile']['hfx'])
        self.assertNotIn('AUTO_BASIS', self.generate(ri_hfx=False, functional='PBE')[0])

    def test_hf_and_xc_physics_are_preserved(self):
        for functional in ('PBE0', 'HSE06'):
            for periodic in ('NONE', 'XYZ'):
                changes = dict(functional=functional, periodic=periodic, cell=(13., 14., 15.))
                _, direct = self.generate(ri_hfx=False, **changes)
                _, ri = self.generate(**changes)
                for key in ('fraction', 'omega', 'interaction_potential', 'cutoff_radius_angstrom',
                            'eps_schwarz'):
                    self.assertEqual(direct['method_profile']['hfx'][key], ri['method_profile']['hfx'][key])
                self.assertEqual(direct['method_profile']['xc_parameters'], ri['method_profile']['xc_parameters'])

    def test_controls_and_retained_requests_are_validated(self):
        cases = ({'ri_hfx': 1}, {'ri_hfx': 'true'}, {'ri_basis_size': 'medium'},
                 {'ri_basis_size': None}, {'ri_basis_size': 'admm-dzp'},
                 {'ri_eps_filter': 0}, {'ri_eps_filter': 1}, {'ri_eps_filter': True},
                 {'ri_eps_filter': float('nan')}, {'ri_eps_filter': float('inf')},
                 {'ri_eps_filter': '1e-9'}, {'ri_memory_cut': True}, {'ri_memory_cut': 0},
                 {'ri_memory_cut': -1}, {'ri_memory_cut': 3.5}, {'hf_memory': 1024},
                 {'ri_hfx': False, 'ri_basis_size': 'SMALL'},
                 {'ri_hfx': False, 'ri_eps_filter': 1e-8}, {'ri_hfx': False, 'ri_memory_cut': 4})
        target = self.root/'existing.inp'
        target.write_text('preserve previous input\n')
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(KitError):
                write_input(self.water, replace(self.settings, **changes), target)
            self.assertEqual(target.read_text(), 'preserve previous input\n')
        text, m = self.generate(ri_eps_filter=1e-10, ri_memory_cut=5)
        self.assertIn('MEMORY_CUT 5', text)
        self.assertEqual(m['method_profile']['hfx']['ri']['eps_filter'], 1e-10)

    def test_unsupported_combinations_fail_before_writing(self):
        cases = ({'admm': True}, {'functional': 'PBE'}, {'functional': 'B3LYP'},
                 {'functional': 'BHANDHLYP', 'libxc_available': True},
                 {'functional': 'M06-2X', 'libxc_available': True},
                 {'functional': 'PBEH', 'pbeh_fraction': .3}, {'cp2k_version': '2026.1'},
                 {'basis': 'uzh-pbe0-dzvp'}, {'basis': 'custom-orbital'},
                 {'basis': 'ae-pob-dzvp-rev2'}, {'periodic': 'XY'},
                 {'run_type': 'CELL_OPT', 'periodic': 'XYZ'}, {'periodic': 'XYZ', 'kpoints': (2, 2, 2)},
                 {'scf': 'diag', 'smearing': 300.}, {'dft_plus_u': (('O', 1, 2.),)})
        out = self.root/'invalid.inp'
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(KitError):
                write_input(self.water, replace(self.settings, **changes), out)
            self.assertFalse(out.exists())

    def test_xtb_rejects_active_and_hidden_ri_controls(self):
        for method in ('GFN0-xTB', 'GFN1-xTB', 'GFN2-xTB'):
            for change in ({'ri_hfx': True}, {'ri_basis_size': 'SMALL'}, {'ri_eps_filter': 1e-8}, {'ri_memory_cut': 4}):
                with self.subTest(method=method, change=change), self.assertRaises(KitError):
                    generate_input(self.water, InputSettings(method=method, periodic='NONE', tblite_available=True, **change))

    def test_actual_orb_required_and_hash_recorded(self):
        with self.assertRaisesRegex(KitError, 'actual orbital basis'):
            self.generate(data_dir=None)
        with patch.dict(os.environ, CP2K_DATA_DIR=str(self.data)):
            text, m = self.generate(data_dir=None)
            self.assertIn('AUTO_BASIS RI_HFX', text)
            self.assertEqual(m['kinds']['O']['basis_source']['sha256'], hashlib.sha256(self.orb.read_bytes()).hexdigest())
        # Explicit ORB files suffice; runtime potential availability is still separately disclosed.
        _, m = self.generate(data_dir=None, basis_files=(str(self.orb),))
        self.assertIsNotNone(m['kinds']['O']['basis_source'])
        self.orb.write_text('O DZVP-MOLOPT-SR-GTH-q6\n')
        with self.assertRaises(KitError):
            self.generate()

    def test_split_kinds_and_charged_uks(self):
        text, m = self.generate(magnetism=(('H', .5), ('@2', -.5)))
        self.assertIn('UKS T', text)
        self.assertEqual(text.count('AUTO_BASIS RI_HFX'), 1)
        self.assertEqual(len(m['kinds']), 3)
        text, m = self.generate(charge=1, multiplicity=2)
        self.assertIn('MULTIPLICITY 2', text)
        self.assertEqual(m['settings']['charge'], 1)

    def test_config_replay_and_cli_subprocess(self):
        settings = replace(self.settings, ri_basis_size='LARGE', ri_eps_filter=1e-10, ri_memory_cut=5, ri_metric='TRUNCATED', ri_cutoff_radius=1.7, write_json=True)
        text, m = generate_input(self.water, settings)
        self.assertEqual(generate_input(self.water, InputSettings.from_config(json.loads(json.dumps(m))))[0], text)
        out = self.root/'cli.inp'
        argv = command_arguments(str(self.source), -1, str(out), settings)
        ns = build_parser().parse_args(argv[3:])
        self.assertTrue(ns.ri_hfx)
        self.assertEqual(ns.ri_basis_size, 'LARGE')
        self.assertEqual(ns.ri_metric, 'TRUNCATED')
        self.assertEqual(ns.ri_cutoff_radius, 1.7)
        result = subprocess.run(argv, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(out.read_text(), text)
        saved = json.loads(Path(str(out)+'.json').read_text())
        self.assertEqual(saved['method_profile']['hfx']['ri']['memory_cut'], 5)
        self.assertEqual(InputSettings.from_config(saved).ri_basis_size, 'LARGE')

    def test_menu_121_category_direct_and_hidden_retention(self):
        for route in ('121', '100\n121'):
            out = self.root/('menu-'+str(len(route))+'.inp')
            log = TTY()
            # Enable, choose size/filter/batching, review, write (category 0 returns first).
            back = '0\n' if route.startswith('100') else ''
            result = run_interactive(str(self.source), -1, str(out), replace(self.settings, ri_hfx=False),
                                     stdin=TTY(route+'\ny\nLARGE\n1e-10\n5\n\n'+back+'r\n\n0\n'), stdout=log, plain=True)
            self.assertEqual(result, 0, log.getvalue())
            self.assertIn('AUTO_BASIS RI_HFX LARGE', out.read_text())
            self.assertIn('RI-HFX: fraction=0.25', log.getvalue())
            self.assertIn('batching, not a memory cap', log.getvalue())
        values = asdict(self.settings)
        self.assertIn(121, {e.number for e in applicable_entries(values)})
        values['functional'] = 'B3LYP'
        self.assertNotIn(121, {e.number for e in applicable_entries(values)})
        self.assertTrue(values['ri_hfx'])
        values.update(functional='PBE0', method='GFN1-xTB')
        self.assertNotIn(121, {e.number for e in applicable_entries(values)})

    def test_menu_disable_and_explicitly_reset_retained_controls(self):
        out = self.root/'reset-ri.inp'
        log = TTY()
        settings = replace(self.settings, ri_basis_size='LARGE', ri_eps_filter=1e-10, ri_memory_cut=5)
        result = run_interactive(str(self.source), -1, str(out), settings,
                                 stdin=TTY('121\nn\nMEDIUM\n1e-9\n3\n0\n'), stdout=log, plain=True)
        self.assertEqual(result, 0, log.getvalue())
        self.assertNotIn('AUTO_BASIS', out.read_text())
        self.assertIn('MAX_MEMORY 512', out.read_text())

    def test_density_bundle_keeps_ri_identity_and_exclusive_outputs(self):
        out = self.root/'cdd.inp'
        settings = replace(self.settings, ri_metric='TRUNCATED', ri_cutoff_radius=1.7,
                           density_difference=True, fragment_a_indices='1',
                           fragment_a_charge=0, fragment_a_multiplicity=1,
                           fragment_b_charge=0, fragment_b_multiplicity=1, write_json=True)
        write_input(self.water, settings, out)
        m = json.loads(Path(str(out)+'.json').read_text())
        # Bundle embeds complete component manifests, all generated with the same RI state.
        self.assertIn('AUTO_BASIS RI_HFX MEDIUM', out.read_text())
        from cp2kkit.density_workflow import bundle_paths
        paths = bundle_paths(settings, out)
        components = m['density_difference']['components']
        for path, key in zip(paths[:3], ('whole', 'fragment_a', 'fragment_b')):
            self.assertIn('AUTO_BASIS RI_HFX MEDIUM', path.read_text())
            self.assertEqual(components[key]['method_profile']['hfx'], m['method_profile']['hfx'])
        before = out.read_bytes()
        with self.assertRaises(OutputExists):
            write_input(self.water, settings, out)
        self.assertEqual(out.read_bytes(), before)
        self.assertTrue(m['runtime_validated'] is False)

    def test_sources_json_collision_symlinks_and_rollback_protected(self):
        with self.assertRaises(KitError):
            write_input(self.water, self.settings, self.orb)
        out = self.root/'old.inp'
        out.write_text('old input\n')
        sidecar = Path(str(out)+'.json')
        sidecar.write_text('old json\n')
        with self.assertRaises(OutputExists):
            write_input(self.water, replace(self.settings, write_json=True), out)
        self.assertEqual(out.read_text(), 'old input\n')
        self.assertEqual(sidecar.read_text(), 'old json\n')
        link = self.root/'link.inp'
        link.symlink_to(out)
        with self.assertRaises(KitError):
            write_input(self.water, self.settings, link)
        fresh = self.root/'fresh.inp'
        with patch('cp2kkit.inputgen.json_text', side_effect=RuntimeError('injected JSON failure')):
            with self.assertRaises(RuntimeError):
                write_input(self.water, replace(self.settings, write_json=True), fresh)
        self.assertFalse(fresh.exists())
        self.assertFalse(Path(str(fresh)+'.json').exists())

    def test_independent_metric_preserves_exchange_for_all_supported_paths(self):
        for functional in ('PBE0', 'HSE06'):
            for periodic in ('NONE', 'XYZ'):
                for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
                    for scf in ('ot', 'diag'):
                        changes = dict(functional=functional, periodic=periodic, run_type=task,
                                       scf=scf, cell=(12., 13., 14.))
                        _, inherited = self.generate(**changes)
                        text, m = self.generate(ri_metric='TRUNCATED', ri_cutoff_radius=1.7, **changes)
                        hfx = m['method_profile']['hfx']
                        ri = hfx['ri']
                        self.assertEqual(ri['metric'], 'TRUNCATED')
                        self.assertEqual(ri['effective_metric_cutoff_radius_angstrom'], 1.7)
                        self.assertIsNone(ri['effective_metric_omega_bohr_inverse'])
                        self.assertIn('RI_METRIC TRUNCATED', text)
                        for key in ('fraction', 'interaction_potential', 'omega', 'cutoff_radius_angstrom', 'eps_schwarz'):
                            self.assertEqual(hfx[key], inherited['method_profile']['hfx'][key])
                        stack = []
                        radii = {}
                        for line in text.splitlines():
                            parts = line.split()
                            if not parts:
                                continue
                            if parts[0] == '&END':
                                stack.pop()
                            elif parts[0].startswith('&'):
                                stack.append(parts[0][1:])
                            elif parts[0] == 'CUTOFF_RADIUS':
                                radii[stack[-1]] = float(parts[-1])
                        self.assertEqual(radii['RI'], 1.7)
                        if hfx['cutoff_radius_angstrom'] is not None:
                            self.assertEqual(radii['INTERACTION_POTENTIAL'], hfx['cutoff_radius_angstrom'])
                        else:
                            self.assertNotIn('INTERACTION_POTENTIAL', radii)
                        self.assertEqual(generate_input(self.water, InputSettings.from_config(m))[0], text)

    def test_metric_controls_fail_before_publication(self):
        cases = ({'ri_metric': 'COULOMB'}, {'ri_metric': 'hfx'}, {'ri_metric': None},
                 {'ri_metric': 'TRUNCATED'}, {'ri_cutoff_radius': 1.5},
                 {'ri_hfx': False, 'ri_metric': 'TRUNCATED', 'ri_cutoff_radius': 1.5})
        cases += tuple({'ri_metric': 'TRUNCATED', 'ri_cutoff_radius': radius}
                       for radius in (True, '1.5', 0, -1, float('nan'), float('inf')))
        out = self.root/'metric-invalid.inp'
        out.write_text('existing target\n')
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(KitError):
                write_input(self.water, replace(self.settings, write_json=True, **changes), out)
            self.assertEqual(out.read_text(), 'existing target\n')
            self.assertFalse(Path(str(out)+'.json').exists())
        for method in ('GFN0-xTB', 'GFN1-xTB', 'GFN2-xTB'):
            with self.assertRaises(KitError):
                generate_input(self.water, InputSettings(method=method, ri_metric='TRUNCATED', ri_cutoff_radius=1.5))

    def test_metric_periodic_bound_uses_emitted_skew_cell(self):
        # Minimum face spacing is 6, despite all three edges being longer.
        skew = replace(self.water, cell=[[10., 0., 0.], [8., 6., 0.], [0., 0., 12.]], pbc=[True]*3)
        settings = replace(self.settings, functional='HSE06', periodic='XYZ', ri_metric='TRUNCATED')
        for radius in (3., 3.1):
            with self.assertRaisesRegex(KitError, 'ri_cutoff_radius.*half'):
                generate_input(skew, replace(settings, ri_cutoff_radius=radius))
        _, m = generate_input(skew, replace(settings, ri_cutoff_radius=2.99))
        self.assertAlmostEqual(m['method_profile']['hfx']['ri']['metric_cutoff_exclusive_limit_angstrom'], 3.)
        with self.assertRaises(KitError):
            self.generate(functional='HSE06', periodic='XYZ', cell=(6.000000001, 10., 10.),
                          ri_metric='TRUNCATED', ri_cutoff_radius=3.)
        _, m = self.generate(ri_metric='TRUNCATED', ri_cutoff_radius=100.)
        self.assertIsNone(m['method_profile']['hfx']['ri']['metric_cutoff_exclusive_limit_angstrom'])

    def test_full_path_threshold_provenance_is_not_runtime_evidence(self):
        for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
            text, m = self.generate(run_type=task, eps_scf=2e-7)
            thresholds = m['method_profile']['hfx']['ri']['thresholds']
            qs = thresholds['FORCE_EVAL/DFT/QS/EPS_PGF_ORB']
            hf = thresholds['FORCE_EVAL/DFT/XC/HF/RI/EPS_PGF_ORB']
            self.assertAlmostEqual(qs['value'], (1e-11 if task == 'ENERGY' else 1e-12)**.5)
            self.assertEqual(qs['selection'], 'source_derived')
            self.assertEqual(hf['selection'], 'native_default')
            self.assertEqual(hf['value'], 1e-5)
            self.assertFalse(qs['emitted'])
            self.assertFalse(hf['emitted'])
            self.assertNotIn('EPS_PGF_ORB', text)
            self.assertEqual(thresholds['FORCE_EVAL/DFT/SCF/EPS_SCF']['value'], 2e-7)
            self.assertTrue(thresholds['FORCE_EVAL/DFT/SCF/EPS_SCF']['emitted'])
            self.assertTrue(all(not item['runtime_observed'] for item in thresholds.values()))

    def test_all_ri_operators_resolve_and_protect_initialization_table(self):
        table = self.data/'t_c_g.dat'
        original = table.read_bytes()
        alias = self.root/'table-alias.inp'
        os.link(table, alias)
        for functional in ('PBE0', 'HSE06'):
            for periodic in ('NONE', 'XYZ'):
                text, m = self.generate(functional=functional, periodic=periodic, cell=(12., 13., 14.))
                self.assertEqual(text.count('T_C_G_DATA '), 1)
                source = m['data_sources']['hfx_truncated_gamma']
                self.assertEqual(source['sha256'], hashlib.sha256(original).hexdigest())
                with self.assertRaises(KitError):
                    write_input(self.water, replace(self.settings, functional=functional, periodic=periodic,
                                                   cell=(12., 13., 14.)), table)
                self.assertEqual(table.read_bytes(), original)
                with self.assertRaisesRegex(KitError, 'source/data file'):
                    write_input(self.water, replace(self.settings, functional=functional, periodic=periodic,
                                                   cell=(12., 13., 14.)), alias)
                self.assertEqual(alias.read_bytes(), original)
        text, m = self.generate(functional='HSE06', data_dir=None, basis_files=(str(self.orb),))
        self.assertIn('T_C_G_DATA t_c_g.dat', text)
        self.assertEqual(m['method_profile']['hfx']['data_validation'], 'not_checked')
        self.assertTrue(any('initialization data' in warning for warning in m['warnings']))
        table.unlink()  # Disposable synthetic fixture only.
        out = self.root/'missing-table.inp'
        with self.assertRaisesRegex(KitError, 't_c_g.dat'):
            write_input(self.water, replace(self.settings, functional='HSE06'), out)
        self.assertFalse(out.exists())

    def test_menu_metric_review_and_explicit_reset(self):
        out = self.root/'metric-menu.inp'
        log = TTY()
        result = run_interactive(str(self.source), -1, str(out), self.settings,
                                 stdin=TTY('121\n\n\n\n\nTRUNCATED\n1.7\nr\n\n0\n'), stdout=log, plain=True)
        self.assertEqual(result, 0, log.getvalue())
        self.assertIn('metric TRUNCATED', log.getvalue())
        self.assertIn('RI radius=1.7 angstrom', log.getvalue())
        self.assertIn('FORCE_EVAL/DFT/QS/EPS_PGF_ORB', log.getvalue())
        self.assertIn('native_default', log.getvalue())
        reset = self.root/'metric-reset.inp'
        result = run_interactive(str(self.source), -1, str(reset),
                                 replace(self.settings, ri_metric='TRUNCATED', ri_cutoff_radius=1.7),
                                 stdin=TTY('121\nn\nHFX\nauto\n0\n'), stdout=log, plain=True)
        self.assertEqual(result, 0, log.getvalue())
        self.assertNotIn('AUTO_BASIS', reset.read_text())

    def test_capability_matrix_matches_enabled_paths(self):
        caps = acceleration_capabilities()
        self.assertEqual(caps['ri_hfx'], ['PBE0', 'HSE06'])
        self.assertEqual(len(caps['direct_hfx']), 6)
        self.assertFalse(caps['ri_hfx_admm'])
        self.assertFalse(caps['runtime_validated'])
        _, m = self.generate()
        self.assertEqual(m['method_profile']['hybrid_acceleration_capabilities'], caps)


if __name__ == '__main__':
    unittest.main()
