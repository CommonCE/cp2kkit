"""Synthetic hybrid input tests only; no CP2K invocation or scientific energies."""
import hashlib
import json
import os
from dataclasses import asdict, replace
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from cp2kkit.cli import build_parser
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.functional_registry import FUNCTIONAL_PROFILES, FUNCTIONALS, parse_functional
from cp2kkit.hybrid import cell_heights
from cp2kkit.input_editor import FIELDS, applicable_entries
from cp2kkit.input_tui import command_arguments, parse_value, run_interactive, visible_fields
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.structure import read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry
from tests.test_input_tui import TTY


HYBRIDS = ('PBE0', 'HSE06', 'B3LYP', 'BHANDHLYP', 'M06-2X', 'PBEH')


def controls(functional):
    return {'libxc_available': True} if functional in {'BHANDHLYP', 'M06-2X'} else (
        {'pbeh_fraction': .45} if functional == 'PBEH' else {})


class HybridTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='cp2kkit-hybrid-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root/'water.xyz'
        self.source.write_text('3\nsynthetic\nO 0 0 0\nH 1 0 0\nH 0 1 0\n')
        self.water = read_structure(self.source)
        self.settings = InputSettings(periodic='NONE', functional='PBE0', allow_pbe_potential=True)
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def generate(self, functional='PBE0', structure=None, **kwargs):
        return generate_input(structure or self.water, replace(self.settings, functional=functional,
                                                              **(controls(functional) | kwargs)))

    def periodic(self, cell=None):
        return replace(self.water, cell=cell or [[20., 0., 0.], [0., 20., 0.], [0., 0., 20.]], pbc=[True]*3)

    def data(self, potential='PBE'):
        data = self.root/'synthetic data'
        data.mkdir(exist_ok=True)
        (data/'BASIS_MOLOPT').write_text(basis_entry('H', 'DZVP-MOLOPT-SR-GTH-q1')+
                                       basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6'))
        (data/'GTH_POTENTIALS').write_text(potential_entry('H', 1, f'GTH-{potential}-q1')+
                                         potential_entry('O', 6, f'GTH-{potential}-q6'))
        return data

    def test_registry_order_and_shared_normalization(self):
        self.assertEqual(FUNCTIONALS[15:], HYBRIDS)
        self.assertEqual(FUNCTIONALS[:5], ('PBE', 'BLYP', 'PBESOL', 'REVPBE', 'RPBE'))
        for f in HYBRIDS:
            self.assertEqual(parse_functional(f.lower()), f)
            self.assertEqual(parse_value(FIELDS['functional'], f.lower()), f)
            self.assertEqual(parse_value(FIELDS['functional'], str(FUNCTIONALS.index(f)+1)), f)
        for f in ('HSE03', 'BHandH', 'PBE0\n&HF'):
            with self.assertRaises(ValueError):
                parse_functional(f)

    def test_new_libxc_compositions_require_build_assertion(self):
        for functional, fraction, components in (
                ('BHANDHLYP', .5, ('HYB_GGA_XC_BHANDHLYP',)),
                ('M06-2X', .54, ('HYB_MGGA_X_M06_2X', 'MGGA_C_M06_2X'))):
            with self.assertRaisesRegex(KitError, 'Libxc-enabled'):
                self.generate(functional, libxc_available=False)
            text, report = self.generate(functional)
            for component in components:
                self.assertIn('&'+component+'\n', text)
            self.assertNotIn('SCALE_X', text)
            self.assertNotIn('          SCALE ', text)  # Libxc already includes semilocal mixing.
            model = report['method_profile']
            self.assertEqual(model['exact_exchange_fraction'], fraction)
            self.assertEqual(model['hfx']['fraction'], fraction)
            self.assertEqual(model['xc_backend'], 'Libxc')
            self.assertEqual(model['kinetic_energy_density'], functional == 'M06-2X')
            if functional == 'M06-2X':
                self.assertTrue(any('kinetic-energy density' in w for w in report['warnings']))

    def test_pbeh_fraction_required_bounded_and_not_silently_reused(self):
        self.assertIsNone(FUNCTIONAL_PROFILES['PBEH'].exact_exchange_fraction)
        from cp2kkit.method_profiles import xc_lines
        with self.assertRaisesRegex(KitError, 'explicit resolved fraction'):
            xc_lines('PBEH')
        for value in (None, 0, -1, 1.01, True, '0.45', float('nan'), float('inf'), 10**400):
            with self.subTest(value=value), self.assertRaisesRegex(KitError, 'explicit pbeh_fraction'):
                self.generate('PBEH', pbeh_fraction=value)
        for value in (.01, .25, .45, .123456789012345, 1.):
            text, report = self.generate('PBEH', pbeh_fraction=value)
            model = report['method_profile']
            self.assertEqual(model['hfx']['fraction'], value)
            self.assertEqual(model['exact_exchange_fraction'], value)
            self.assertAlmostEqual(float(model['xc_parameters'][0]['parameters']['SCALE_X'])+value, 1.)
            self.assertIn('FRACTION '+repr(value)+'\n', text)
            self.assertIn('SCALE_C 1.0', text)
        for functional in HYBRIDS[:-1]+('PBE',):
            with self.assertRaisesRegex(KitError, 'requires PBEH'):
                self.generate(functional, pbeh_fraction=.45)
        with self.assertRaisesRegex(KitError, 'DFT/density requests'):
            generate_input(self.water, InputSettings(method='GFN1-xTB', periodic='NONE', pbeh_fraction=.45))
        output = self.root/'protected.inp'
        output.write_text('retain previous input\n')
        with self.assertRaises(KitError):
            write_input(self.water, replace(self.settings, functional='PBEH'), output)
        self.assertEqual(output.read_text(), 'retain previous input\n')

    def test_pbeh_menu_fraction_replay_and_visibility(self):
        self.assertIn('pbeh_fraction', [f.name for f in visible_fields(
            (FIELDS['pbeh_fraction'],), asdict(replace(self.settings, functional='PBEH')))])
        output = self.root/'pbeh-tui.inp'
        log = TTY()
        code = run_interactive(str(self.source), -1, str(output), replace(InputSettings(periodic='NONE'), write_json=True),
                               stdin=TTY('1\n21\n120\n\n\n\n0.45\nr\n\n0\n'), stdout=log, plain=True)
        self.assertEqual(code, 0, log.getvalue())
        report = json.loads(Path(str(output)+'.json').read_text())
        self.assertEqual(report['settings']['pbeh_fraction'], .45)
        self.assertIn('Direct HFX: fraction=0.45', log.getvalue())

    def test_pbe0_complete_composition_and_metadata(self):
        text, report = self.generate()
        self.assertIn('&PBE\n          SCALE_X 0.75\n          SCALE_C 1.0\n', text)
        self.assertIn('FRACTION 0.25\n', text)
        model = report['method_profile']
        self.assertEqual(model['exact_exchange_fraction'], 0.25)
        self.assertEqual(model['family'], 'hybrid-GGA')
        self.assertIsNone(model['native_shortcut'])
        self.assertEqual(model['xc_backend'], 'CP2K-native')
        self.assertFalse(model['libxc_required'])
        self.assertEqual(model['xc_parameters'], [{'component': 'PBE', 'parameters': {'SCALE_X': '0.75', 'SCALE_C': '1.0'}}])

    def test_hse06_screened_exchange_has_same_omega_in_xc_and_hf(self):
        for periodic in ('NONE', 'XYZ'):
            text, report = self.generate('HSE06', self.periodic() if periodic == 'XYZ' else None, periodic=periodic)
            self.assertIn('&XWPBE\n          SCALE_X -0.25\n          SCALE_X0 1.0\n          OMEGA 0.11', text)
            self.assertIn('&PBE\n          SCALE_X 0.0\n          SCALE_C 1.0', text)
            self.assertEqual(text.count('OMEGA 0.11'), 2)
            self.assertIn('POTENTIAL_TYPE SHORTRANGE', text)
            self.assertIn('FRACTION 0.25', text)
            self.assertNotIn('CUTOFF_RADIUS', text)
            self.assertNotIn('T_C_G_DATA', text)
            hfx = report['method_profile']['hfx']
            self.assertEqual(hfx['omega'], .11)
            self.assertEqual(hfx['omega_unit'], 'bohr^-1')
            self.assertIsNone(hfx['cutoff_radius_angstrom'])

    def test_b3lyp_vwn3_definition_not_native_vwn5_shortcut(self):
        text, report = self.generate('B3LYP')
        for line in ('&LYP\n          SCALE_C 0.81', '&BECKE88\n          SCALE_X 0.72',
                     '&VWN\n          FUNCTIONAL_TYPE VWN3\n          SCALE_C 0.19',
                     '&XALPHA\n          SCALE_X 0.08', 'FRACTION 0.2'):
            self.assertIn(line, text)
        self.assertNotIn('&XC_FUNCTIONAL B3LYP', text)
        self.assertNotIn('VWN5', text)
        self.assertEqual(report['method_profile']['exact_exchange_fraction'], .2)
        self.assertTrue(any('VWN3' in w for w in report['warnings']))

    def test_isolated_full_coulomb_no_auxiliaries_or_restart_screening(self):
        for f in HYBRIDS:
            text, report = self.generate(f)
            self.assertEqual(text.count('      &HF\n'), 1)
            self.assertNotIn('&RI', text)
            self.assertNotIn('AUXILIARY_DENSITY', text)
            self.assertNotIn('AUX_FIT', text)
            self.assertIn('SCREEN_ON_INITIAL_P F', text)
            self.assertIn('MAX_MEMORY 512', text)
            if f != 'HSE06':
                self.assertIn('POTENTIAL_TYPE COULOMB', text)
                self.assertNotIn('T_C_G_DATA', text)
            hfx = report['method_profile']['hfx']
            self.assertFalse(hfx['admm'])
            self.assertFalse(hfx['ri_hfx'])
            self.assertFalse(hfx['build_verified'])
            self.assertFalse(hfx['runtime_validated'])
            self.assertFalse(report['runtime_validated'])
            self.assertEqual(report['input_sha256'], hashlib.sha256(text.encode()).hexdigest())
            self.assertEqual((text, report), self.generate(f))
            # Every section closes by its own name and nesting stays balanced.
            stack = []
            for line in text.splitlines():
                words = line.split()
                if words and words[0] == '&END':
                    self.assertEqual(stack.pop(), words[1])
                elif words and words[0].startswith('&'):
                    stack.append(words[0][1:])
            self.assertFalse(stack)

    def test_periodic_global_hybrid_truncation_auto_and_explicit(self):
        for f in ('PBE0', 'B3LYP', 'BHANDHLYP', 'M06-2X', 'PBEH'):
            text, report = self.generate(f, self.periodic(), periodic='XYZ')
            self.assertIn('POTENTIAL_TYPE TRUNCATED', text)
            self.assertIn('CUTOFF_RADIUS [angstrom] 6', text)
            self.assertIn('T_C_G_DATA t_c_g.dat', text)
            self.assertEqual(report['method_profile']['hfx']['cutoff_radius_angstrom'], 6.)
            text, report = self.generate(f, self.periodic(), periodic='XYZ', hf_cutoff_radius=7.25)
            self.assertIn('CUTOFF_RADIUS [angstrom] 7.25', text)
            self.assertEqual(report['settings']['hf_cutoff_radius'], 7.25)
        _, small = self.generate(structure=self.periodic([[8.,0.,0.],[0.,10.,0.],[0.,0.,12.]]), periodic='XYZ')
        self.assertAlmostEqual(small['method_profile']['hfx']['cutoff_radius_angstrom'], 8/2.01)

    def test_skew_cell_face_spacing_not_edge_length_and_no_clipping(self):
        cell = [[10., 0., 0.], [9., 3., 0.], [0., 0., 12.]]
        self.assertLess(min(cell_heights(cell)), 3.1)
        _, report = self.generate(structure=self.periodic(cell), periodic='XYZ')
        hfx = report['method_profile']['hfx']
        self.assertAlmostEqual(hfx['cutoff_radius_angstrom'], min(cell_heights(cell))/2.01)
        for radius in (2., 10., min(cell_heights(cell))/2):
            with self.assertRaisesRegex(KitError, 'half the minimum cell face spacing'):
                self.generate(structure=self.periodic(cell), periodic='XYZ', hf_cutoff_radius=radius)

    def test_invalid_controls_and_inactive_requests_fail(self):
        for changes in ({'hf_eps_schwarz': v} for v in (0, -1, 1, float('nan'), float('inf'), True, '1e-6', 10**400)):
            with self.subTest(changes=changes), self.assertRaises(KitError):
                self.generate(**changes)
        for value in (0, -1, 1.5, True, '512', None):
            with self.subTest(value=value), self.assertRaises(KitError):
                self.generate(hf_memory=value)
        for value in (0, -1, float('nan'), float('inf'), True, '3', 10**400):
            with self.subTest(value=value), self.assertRaises(KitError):
                self.generate(hf_cutoff_radius=value)
        for f in ('PBE0', 'HSE06'):
            with self.assertRaisesRegex(KitError, 'hf_cutoff_radius'):
                self.generate(f, hf_cutoff_radius=2.)
        for change in ({'hf_memory': 1024}, {'hf_eps_schwarz': 1e-7}, {'hf_cutoff_radius': 2.}):
            with self.assertRaisesRegex(KitError, 'require a supported hybrid'):
                self.generate('PBE', **change)
            with self.assertRaisesRegex(KitError, 'DFT/density requests'):
                generate_input(self.water, replace(InputSettings(periodic='NONE', method='GFN1-xTB'), **change))

    def test_scope_conflicts_do_not_change_physics(self):
        for f in HYBRIDS:
            for changes in ({'basis': 'ae-pob-tzvp'}, {'basis': 'uzh-pbe0-dzvp'}, {'basis': 'uzh-pbe-dzvp'},
                            {'basis': 'custom-orbital'}, {'run_type': 'CELL_OPT'}, {'smearing': 300., 'scf': 'diag'},
                            {'kpoints': (2, 2, 2), 'scf': 'diag'}, {'dft_plus_u': (('O', 1, 2.),)},
                            {'periodic': 'XY', 'cell': (12., 12., 12.)}, {'cp2k_version': '2026.1'}):
                with self.subTest(f=f, changes=changes), self.assertRaises(KitError):
                    self.generate(f, **changes)

    def test_family_potentials_and_matched_real_file_preference(self):
        for f, family in (('PBE0', 'PBE'), ('HSE06', 'PBE'), ('B3LYP', 'BLYP'),
                          ('BHANDHLYP', 'PBE'), ('M06-2X', 'PBE'), ('PBEH', 'PBE')):
            for approval in (False, True):
                text, report = self.generate(f, allow_pbe_potential=approval)
                self.assertIn('POTENTIAL GTH-'+family+'-q6', text)
                self.assertNotIn('POTENTIAL GTH-'+f, text)
                self.assertEqual(report['method_profile']['potential_approximations'], ['H', 'O'])
                self.assertEqual(report['kinds']['O']['potential_functional'], family)
                self.assertTrue(any('Standard family GTH-'+family in w for w in report['warnings']))
                self.assertFalse(any('User-approved GTH-PBE' in w for w in report['warnings']))
            data = self.data(family)
            text, report = self.generate(f, data_dir=str(data), allow_pbe_potential=False)
            self.assertIn('POTENTIAL GTH-'+family+'-q6', text)
            self.assertRegex(report['kinds']['O']['potential_source']['entry_sha256'], r'^[0-9a-f]{64}$')
            # Actual exact-hybrid entries still win over the family entries.
            with (data/'GTH_POTENTIALS').open('a') as stream:
                stream.write(potential_entry('H', 1, f'GTH-{f}-q1'))
            text, report = self.generate(f, data_dir=str(data), allow_pbe_potential=False)
            self.assertIn('POTENTIAL GTH-'+f+'-q1', text)
            self.assertIn('POTENTIAL GTH-'+family+'-q6', text)
            self.assertEqual(report['method_profile']['potential_approximations'], ['O'])
            with (data/'GTH_POTENTIALS').open('a') as stream:
                stream.write(potential_entry('O', 6, f'GTH-{f}-q6'))
            text, report = self.generate(f, data_dir=str(data), allow_pbe_potential=False)
            self.assertIn('POTENTIAL GTH-'+f+'-q6', text)
            self.assertFalse(report['method_profile']['potential_approximations'])

    def test_family_missing_never_crosses_family_even_with_approval(self):
        for f, wrong_family in (('PBE0', 'BLYP'), ('HSE06', 'BLYP'), ('B3LYP', 'PBE')):
            data = self.data(wrong_family)
            for approval in (False, True):
                with self.subTest(f=f, approval=approval), self.assertRaisesRegex(KitError, 'No verified family GTH-'):
                    self.generate(f, data_dir=str(data), allow_pbe_potential=approval)

    def test_truncated_gamma_source_hash_missing_and_overwrite_protection(self):
        data = self.data()
        settings = replace(self.settings, periodic='XYZ', data_dir=str(data))
        structure = self.periodic()
        with self.assertRaises(KitError):
            generate_input(structure, settings)
        table = data/'t_c_g.dat'
        table.write_text('Synthetic table bytes, not a numerical HFX table\n')
        text, report = generate_input(structure, settings)
        source = report['data_sources']['hfx_truncated_gamma']
        self.assertEqual(source['sha256'], hashlib.sha256(table.read_bytes()).hexdigest())
        # T_C_G_DATA is char_t: a checked absolute path is provenance only.
        self.assertIn('T_C_G_DATA t_c_g.dat\n', text)
        self.assertEqual(source['path'], str(table.resolve()))
        self.assertEqual(report['emitted_data_files']['hfx_truncated_gamma'], 't_c_g.dat')
        self.assertEqual(report['method_profile']['hfx']['data_validation'], 'source_bytes_only')
        with self.assertRaises(KitError):
            write_input(structure, settings, table)
        self.assertTrue(table.read_text().startswith('Synthetic'))

    def test_tasks_solvers_charge_spin_density_and_magnetic_kinds(self):
        for f in HYBRIDS:
            for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
                for solver in ('ot', 'diag'):
                    text, report = self.generate(f, run_type=task, scf=solver, charge=1, multiplicity=2,
                                                electron_density=True, spin_density=True,
                                                magnetism=(('@1', 1.),), eps_scf=3e-7, cutoff=550., rel_cutoff=70.)
                    self.assertIn('UKS T', text)
                    self.assertIn('RUN_TYPE '+task, text)
                    self.assertIn('&E_DENSITY_CUBE', text)
                    self.assertIn('MAGNETIZATION 1', text)
                    self.assertEqual(report['explicit_electron_count'], 7)
                    self.assertEqual(report['effective_eps_scf'], 3e-7)
                    self.assertEqual(report['settings']['cutoff'], 550.)

    def test_dispersion_whitelist_complete_reference_and_no_double_correction(self):
        for f in HYBRIDS:
            for dispersion in ('none', 'd3', 'd3bj'):
                if dispersion not in FUNCTIONAL_PROFILES[f].dispersion:
                    with self.assertRaisesRegex(KitError, 'No checked'):
                        self.generate(f, dispersion=dispersion)
                    continue
                text, report = self.generate(f, dispersion=dispersion)
                self.assertEqual(text.count('&VDW_POTENTIAL\n'), int(dispersion != 'none'))
                if dispersion != 'none':
                    reference = 'M062X' if f == 'M06-2X' else f
                    self.assertIn('REFERENCE_FUNCTIONAL '+reference, text)
                    self.assertEqual(report['method_profile']['dispersion_reference'], reference)
                self.assertFalse(report['nonlocal_correlation']['enabled'])
                self.assertEqual(text.count('      &HF\n'), 1)

    def test_cli_subprocess_and_config_replay_for_every_hybrid(self):
        for f in HYBRIDS:
            output = self.root/(f+'.inp')
            settings = replace(self.settings, functional=f, allow_pbe_potential=False,
                               write_json=True, hf_memory=768, hf_eps_schwarz=2e-7, **controls(f))
            argv = command_arguments(self.source, -1, output, settings)
            args = build_parser().parse_args(argv[3:])
            self.assertEqual(args.hf_memory, 768)
            result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(Path(str(output)+'.json').read_text())
            text, replay = generate_input(self.water, InputSettings.from_config(report))
            self.assertEqual(text, output.read_text())
            self.assertEqual(json.loads(json.dumps(replay)), report)
            with self.assertRaises(OutputExists):
                write_input(self.water, settings, output)
            original = output.read_text()
            with self.assertRaises(KitError):
                write_input(self.water, replace(settings, hf_memory=0), output)
            self.assertEqual(output.read_text(), original)

    def test_tui_method_choices_parameters_review_and_visibility(self):
        for f in HYBRIDS:
            values = asdict(replace(self.settings, functional=f, **controls(f)))
            entries = applicable_entries(values)
            self.assertIn(120, {e.number for e in entries})
            self.assertNotIn(114, {e.number for e in entries})
        self.assertNotIn(120, {e.number for e in applicable_entries(asdict(InputSettings()))})
        output = self.root/'tui.inp'
        log = TTY()
        code = run_interactive(str(self.source), -1, str(output), replace(InputSettings(periodic='NONE'), write_json=True),
                               stdin=TTY('1\nB3LYP\n120\n2e-7\n768\nauto\nr\n\n0\n'), stdout=log, plain=True)
        self.assertEqual(code, 0, log.getvalue())
        report = json.loads(Path(str(output)+'.json').read_text())
        self.assertEqual(report['settings']['functional'], 'B3LYP')
        self.assertEqual(report['settings']['hf_memory'], 768)
        self.assertEqual(report['settings']['hf_eps_schwarz'], 2e-7)
        self.assertIn('Direct HFX: fraction=0.2', log.getvalue())

    def test_density_bundle_rejects_hfx_identity_mismatch(self):
        settings = replace(self.settings, density_difference=True, fragment_a_indices='1',
                           fragment_a_charge=0, fragment_a_multiplicity=3,
                           fragment_b_charge=0, fragment_b_multiplicity=1)
        original = generate_input

        def altered(structure, settings, **kwargs):
            text, report = original(structure, settings, **kwargs)
            if kwargs:
                report['method_profile']['hfx']['fraction'] = 0.5
            return text, report

        with patch('cp2kkit.inputgen.generate_input', side_effect=altered):
            with self.assertRaisesRegex(KitError, 'HFX operator/radius/data identity'):
                generate_input(self.water, settings)

    def test_density_bundle_preserves_hfx_identity_and_protected_publication(self):
        for f in HYBRIDS:
            settings = replace(self.settings, functional=f, periodic='XYZ', density_difference=True,
                               fragment_a_indices='1', fragment_a_charge=0, fragment_a_multiplicity=3,
                               fragment_b_charge=0, fragment_b_multiplicity=1, **controls(f))
            text, report = generate_input(self.periodic(), settings)
            components = report['density_difference']['components']
            for component in components.values():
                self.assertEqual(component['method_profile']['hfx'], report['method_profile']['hfx'])
                self.assertIn('&HF', component['input_text'])
            output = self.root/(f+'-CDD.inp')
            write_input(self.periodic(), settings, output)
            with self.assertRaises(OutputExists):
                write_input(self.periodic(), settings, output)
