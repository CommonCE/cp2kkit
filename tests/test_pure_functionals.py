"""Synthetic non-hybrid XC regressions; no CP2K/Libxc execution or scientific energies."""
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import build_parser, main
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.functional_registry import FUNCTIONAL_PROFILES, FUNCTIONALS, parse_functional
from cp2kkit.input_tui import GROUPS, command_arguments, parse_value, run_interactive, visible_fields
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.method_profiles import POTENTIAL_CATALOG, xc_lines
from cp2kkit.structure import read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry


COMPONENTS = {
    'RPBE': ('GGA_X_RPBE', 'GGA_C_PBE'),
    'TPSS': ('MGGA_X_TPSS', 'MGGA_C_TPSS'),
    'REVTPSS': ('MGGA_X_REVTPSS', 'MGGA_C_REVTPSS'),
    'SCAN': ('MGGA_X_SCAN', 'MGGA_C_SCAN'),
    'R2SCAN': ('MGGA_X_R2SCAN', 'MGGA_C_R2SCAN'),
    'MN15L': ('MGGA_X_MN15_L', 'MGGA_C_MN15_L'),
    'HLE17': ('MGGA_XC_HLE17',),
    'B97M-RV': ('MGGA_XC_B97M_V',),
}


class TTY(io.StringIO):
    def isatty(self):
        return True


class PureFunctionalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cp2kkit-xc-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'water.xyz'
        self.source.write_text('3\nsynthetic\nO 0 0 0\nH 0 1 0\nH 1 0 0\n')
        self.water = read_structure(self.source)
        self.settings = InputSettings(periodic='NONE', allow_pbe_potential=True, libxc_available=True)
        self.output = self.root/'new.inp'
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def generate(self, functional='R2SCAN', structure=None, **kwargs):
        return generate_input(structure or self.water, replace(self.settings, functional=functional, **kwargs))

    def data(self, potentials='PBE', kernel=None):
        data = self.root/'data with spaces'
        data.mkdir(exist_ok=True)
        (data/'BASIS_MOLOPT').write_text(basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6')+
                                       basis_entry('H', 'DZVP-MOLOPT-SR-GTH-q1'))
        (data/'GTH_POTENTIALS').write_text(potential_entry('O', 6, f'GTH-{potentials}-q6')+
                                         potential_entry('H', 1, f'GTH-{potentials}-q1'))
        if kernel:
            (data/kernel).write_text('synthetic kernel bytes; NOT a numerical kernel\n')
        return data

    def test_registry_exact_scope_and_original_order(self):
        self.assertEqual(FUNCTIONALS[:15], ('PBE', 'BLYP', 'PBESOL', 'REVPBE', 'RPBE', 'PADE', 'BP86',
                                       'TPSS', 'REVTPSS', 'SCAN', 'R2SCAN', 'MN15L', 'HLE17', 'B97M-RV', 'BEEFVDW'))
        self.assertEqual({name for name, p in FUNCTIONAL_PROFILES.items() if p.libxc}, set(COMPONENTS) | {'BEEFVDW'})

    def test_aliases_are_shared_by_cli_tui_config_and_api(self):
        field = next(f for _, group in GROUPS for f in group if f.name == 'functional')
        for alias, canonical in (('lda', 'PADE'), ('Pade', 'PADE'), ('BP', 'BP86'), ('r2Scan', 'R2SCAN'),
                                  ('revTPSS', 'REVTPSS'), ('MN15-L', 'MN15L'), ('BEEF-vdW', 'BEEFVDW')):
            with self.subTest(alias=alias):
                self.assertEqual(parse_functional(alias), canonical)
                self.assertEqual(parse_value(field, alias), canonical)
                args = build_parser().parse_args(['generate-input', str(self.source), '-o', str(self.output), '--functional', alias])
                self.assertEqual(args.functional, canonical)
                _, report = self.generate(alias)
                self.assertEqual(report['settings']['functional'], canonical)
                restored = InputSettings.from_config({**asdict(self.settings), 'functional': alias})
                self.assertEqual(restored.functional, canonical)
                self.assertEqual(generate_input(self.water, restored), self.generate(canonical))
        self.assertEqual(parse_value(field, '1'), 'PBE')
        self.assertEqual(parse_value(field, '5'), 'RPBE')

    def test_deferred_hybrid_xtb_arbitrary_and_injected_functionals_stay_unavailable(self):
        for value in ('BHandHLYP', 'PBEh', 'M06-2X', 'GFN0-xTB', 'GFN2-xTB', 'OLYP', 'B97M-V',
                      'PBE\n&HF', '', None, 1, ['PBE']):
            with self.subTest(value=value), self.assertRaises(KitError):
                self.generate(value)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            main(['generate-input', str(self.source), '-o', str(self.output), '--functional', 'PBEh'])
        self.assertEqual(cm.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_every_profile_has_no_hf_and_preserves_core_settings(self):
        for functional in FUNCTIONALS[:15]:
            with self.subTest(functional=functional):
                text, report = self.generate(functional, cutoff=530., rel_cutoff=67., eps_scf=2e-7, charge=1, multiplicity=2)
                self.assertNotIn('&HF', text)
                self.assertNotIn('AUXILIARY_DENSITY', text)
                self.assertEqual(report['method_profile']['exact_exchange_fraction'], 0.)
                self.assertEqual(report['settings']['charge'], 1)
                self.assertEqual(report['settings']['multiplicity'], 2)
                self.assertEqual(report['settings']['cutoff'], 530.)
                self.assertEqual(report['settings']['rel_cutoff'], 67.)
                self.assertEqual(report['effective_eps_scf'], 2e-7)
                self.assertFalse(report['runtime_validated'])
                self.assertFalse(report['method_profile']['build_verified'])
                self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), report['input_sha256'])
                self.assertEqual((text, report), self.generate(functional, cutoff=530., rel_cutoff=67., eps_scf=2e-7, charge=1, multiplicity=2))

    def test_libxc_component_definitions_exact_and_without_shortcuts(self):
        for functional, components in COMPONENTS.items():
            with self.subTest(functional=functional):
                text, report = self.generate(functional)
                expected = ['      &XC_FUNCTIONAL']
                for component in components:
                    expected += ['        &'+component, '        &END '+component]
                expected += ['      &END XC_FUNCTIONAL']
                self.assertEqual(xc_lines(functional), expected)
                self.assertIn('\n'.join(expected), text)
                self.assertEqual(report['method_profile']['xc_components'], list(components))
                self.assertTrue(report['method_profile']['libxc_required'])
                self.assertEqual(report['method_profile']['xc_backend'], 'Libxc')
                self.assertEqual(report['method_profile']['kinetic_energy_density'], functional != 'RPBE')

    def test_each_libxc_profile_requires_explicit_boolean_build_assertion(self):
        for functional, profile in FUNCTIONAL_PROFILES.items():
            if not profile.libxc:
                continue
            with self.subTest(functional=functional), self.assertRaisesRegex(KitError, 'Libxc-enabled.*build'):
                self.generate(functional, libxc_available=False)
        for value in (1, 'true', None):
            with self.subTest(value=value), self.assertRaisesRegex(KitError, 'Boolean'):
                self.generate(libxc_available=value)

    def test_native_pade_and_bp86_use_matched_real_potential_tags(self):
        for functional, tag in (('PADE', 'PADE'), ('BP86', 'BP')):
            with self.subTest(functional=functional):
                text, report = self.generate(functional, allow_pbe_potential=False, libxc_available=False)
                self.assertIn('&XC_FUNCTIONAL '+tag+'\n', text)
                self.assertIn('POTENTIAL GTH-'+tag+'-q6', text)
                self.assertEqual(report['method_profile']['potential_approximations'], [])
                self.assertFalse(report['kinds']['O']['potential_approximation'])
                self.assertEqual(report['kinds']['O']['potential_functional'], functional)
                self.assertIn(6, POTENTIAL_CATALOG[functional]['O'])

    def test_local_pade_and_bp86_sources_are_checked_not_renamed(self):
        for functional, tag in (('PADE', 'PADE'), ('BP86', 'BP')):
            data = self.data(tag)
            _, report = self.generate(functional, allow_pbe_potential=False, data_dir=str(data))
            self.assertEqual(report['basis_validation']['status'], 'data_checked')
            self.assertEqual(report['kinds']['O']['potential_source']['sha256'], hashlib.sha256((data/'GTH_POTENTIALS').read_bytes()).hexdigest())
            self.assertEqual(report['method_profile']['potential_approximations'], [])

    def test_missing_potentials_do_not_fallback_without_approval(self):
        for functional in ('TPSS', 'REVTPSS', 'SCAN', 'R2SCAN', 'MN15L', 'HLE17', 'B97M-RV', 'BEEFVDW'):
            with self.subTest(functional=functional), self.assertRaisesRegex(KitError, '--allow-pbe-potential'):
                self.generate(functional, allow_pbe_potential=False)
        # BP is incomplete in the pinned library. Nb q13 is not invented as GTH-BP.
        niobium = replace(self.water, symbols=['Nb'], positions=[[0., 0., 0.]])
        with self.assertRaisesRegex(KitError, '--allow-pbe-potential'):
            self.generate('BP86', niobium, allow_pbe_potential=False)
        _, report = self.generate('BP86', niobium)
        self.assertEqual(report['kinds']['Nb']['potential'], 'GTH-PBE-q13')
        self.assertTrue(report['kinds']['Nb']['potential_approximation'])

    def test_actual_matched_meta_potentials_preferred_even_without_approval(self):
        data = self.data('R2SCAN')
        text, report = self.generate(data_dir=str(data), allow_pbe_potential=False)
        self.assertIn('POTENTIAL GTH-R2SCAN-q6', text)
        self.assertEqual(report['method_profile']['potential_approximations'], [])

    def test_pbe_approval_does_not_relabel_uzh_or_change_electron_model(self):
        for functional in FUNCTIONALS[5:15]:
            with self.subTest(functional=functional), self.assertRaisesRegex(KitError, 'requires'):
                self.generate(functional, basis='uzh-pbe-tzvp')

    def test_new_profiles_remain_target_version_gated(self):
        for functional in FUNCTIONALS[5:15]:
            for target in ('2024.1', '2025.2', '2026.1'):
                with self.subTest(functional=functional, target=target), self.assertRaisesRegex(KitError, '2026.2'):
                    self.generate(functional, cp2k_version=target)

    def test_meta_nonlocal_scope_rejects_ae_cellopt_kpoints_and_u(self):
        for functional, profile in FUNCTIONAL_PROFILES.items():
            if not profile.restricted:
                continue
            for kwargs in ({'basis': 'ae-pob-tzvp'}, {'run_type': 'CELL_OPT'},
                           {'kpoints': (2, 2, 2), 'scf': 'diag'}, {'dft_plus_u': (('O', 1, 2.),)}):
                with self.subTest(functional=functional, kwargs=kwargs), self.assertRaisesRegex(KitError, 'generator scope limit'):
                    self.generate(functional, **kwargs)

    def test_gamma_energy_force_and_geo_opt_allow_rks_and_uks(self):
        periodic = replace(self.water, pbc=[True]*3, cell=[[12., 0., 0.], [0., 12., 0.], [0., 0., 12.]])
        for functional in FUNCTIONALS[5:15]:
            for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
                for magnetic in (None, ()):
                    with self.subTest(functional=functional, task=task, magnetic=magnetic):
                        text, report = self.generate(functional, periodic, periodic='XYZ', run_type=task, magnetism=magnetic)
                        self.assertIn('RUN_TYPE '+task, text)
                        self.assertIn('UKS T' if magnetic == () else 'UKS F', text)
                        self.assertEqual(report['generated_structure']['pbc'], [True]*3)
                        self.assertEqual(report['explicit_electron_count'], 8)

    def test_pade_bp86_preserve_existing_ae_and_cell_opt_paths(self):
        for functional in ('PADE', 'BP86'):
            _, report = self.generate(functional, basis='ae-pob-tzvp', allow_pbe_potential=False)
            self.assertEqual(report['electron_count_model'], 'all_electron')
            self.assertEqual(report['explicit_electron_count'], 10)
            self.assertFalse(report['kinds']['O']['potential_approximation'])
            _, report = self.generate(functional, periodic='XYZ', cell=(12., 12., 12.), run_type='CELL_OPT')
            self.assertEqual(report['settings']['run_type'], 'CELL_OPT')

    def test_explicit_dispersion_matrix_and_rejected_pairs(self):
        allowed = {
            'PADE': ('none',), 'BP86': ('none', 'd3', 'd3bj'), 'TPSS': ('none', 'd3', 'd3bj'),
            'REVTPSS': ('none', 'd3', 'd3bj'), 'SCAN': ('none', 'd3', 'd3bj'),
            'R2SCAN': ('none', 'd3bj'), 'MN15L': ('none', 'd3'), 'HLE17': ('none',),
            'B97M-RV': ('none',), 'BEEFVDW': ('none',),
        }
        for functional, choices in allowed.items():
            self.assertEqual(FUNCTIONAL_PROFILES[functional].dispersion, choices)
            for dispersion in ('none', 'd3', 'd3bj'):
                with self.subTest(functional=functional, dispersion=dispersion):
                    if dispersion not in choices:
                        with self.assertRaisesRegex(KitError, 'No checked '+dispersion):
                            self.generate(functional, dispersion=dispersion)
                        continue
                    text, report = self.generate(functional, dispersion=dispersion)
                    if dispersion != 'none':
                        self.assertIn('REFERENCE_FUNCTIONAL '+functional+'\n', text)
                        self.assertEqual(report['method_profile']['dispersion_reference'], functional)
                    elif not FUNCTIONAL_PROFILES[functional].nonlocal_type:
                        self.assertNotIn('&VDW_POTENTIAL', text)

    def test_b97m_rv_and_beef_are_complete_nonlocal_methods(self):
        for functional, type_, kernel in (('B97M-rV', 'RVV10', 'rVV10_kernel_table.dat'),
                                          ('BEEF-vdW', 'LMKLL', 'vdW_kernel_table.dat')):
            text, report = self.generate(functional)
            self.assertIn('POTENTIAL_TYPE NON_LOCAL', text)
            self.assertIn('TYPE '+type_, text)
            self.assertIn('KERNEL_FILE_NAME '+kernel, text)
            self.assertEqual(text.count('&VDW_POTENTIAL\n'), 1)
            self.assertNotIn('&PAIR_POTENTIAL', text)
            if type_ == 'RVV10':
                self.assertIn('PARAMETERS 6 0.01', text)
                self.assertEqual(report['nonlocal_correlation']['parameters'], [6.0, 0.01])
            else:
                self.assertNotIn('PARAMETERS ', text)
                self.assertIn('&XC_FUNCTIONAL BEEFVDW', text)
            self.assertFalse(report['nonlocal_correlation']['runtime_validated'])
            self.assertEqual(report['nonlocal_correlation']['kernel_validation'], 'not_checked')
            self.assertIsNone(report['nonlocal_correlation']['kernel_source'])
            self.assertIsNone(report['emitted_data_files']['dispersion'])
            self.assertEqual(report['emitted_data_files']['xc_kernel'], kernel)
            self.assertTrue(any('intrinsic' in w for w in report['warnings']))

    def test_kernel_data_dir_spaces_hashes_and_validation_boundary(self):
        for functional, kernel in (('B97M-RV', 'rVV10_kernel_table.dat'), ('BEEFVDW', 'vdW_kernel_table.dat')):
            data = self.data(kernel=kernel)
            text, report = self.generate(functional, data_dir=str(data))
            path = data/kernel
            self.assertIn('KERNEL_FILE_NAME '+str(path)+'\n', text)
            self.assertNotIn('KERNEL_FILE_NAME "', text)
            self.assertEqual(report['data_sources']['xc_kernel']['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(report['nonlocal_correlation']['kernel_source'], report['data_sources']['xc_kernel'])
            self.assertEqual(report['nonlocal_correlation']['kernel_validation'], 'source_bytes_only')
            self.assertFalse(report['nonlocal_correlation']['runtime_validated'])

    def test_missing_or_non_utf8_kernel_fails_before_publication(self):
        data = self.data()
        settings = replace(self.settings, functional='B97M-RV', data_dir=str(data))
        for bad in (None, b'\xff'):
            if bad is not None:
                (data/'rVV10_kernel_table.dat').write_bytes(bad)
            with self.assertRaises(KitError):
                write_input(self.water, settings, self.output)
            self.assertFalse(self.output.exists())
            self.assertFalse(Path(str(self.output)+'.json').exists())

    def test_kernel_can_never_be_an_output_target(self):
        data = self.data(kernel='rVV10_kernel_table.dat')
        kernel = data/'rVV10_kernel_table.dat'
        output = self.root/'kernel-alias.inp'
        os.link(kernel, output)
        with self.assertRaisesRegex(KitError, 'source/data'):
            write_input(self.water, replace(self.settings, functional='B97M-RV', data_dir=str(data)), output)
        self.assertTrue(kernel.read_text().startswith('synthetic'))
        self.assertEqual(output.read_bytes(), kernel.read_bytes())

    def test_semilocal_none_does_not_read_a_kernel_or_emit_nonlocal(self):
        data = self.data()
        for functional in ('PADE', 'BP86', 'TPSS', 'R2SCAN'):
            text, report = self.generate(functional, data_dir=str(data))
            self.assertNotIn('&NON_LOCAL', text)
            self.assertFalse(report['nonlocal_correlation']['enabled'])
            self.assertNotIn('xc_kernel', report['data_sources'])
            self.assertIsNone(report['emitted_data_files']['xc_kernel'])

    def test_replay_config_and_input_publication_for_all_new_profiles(self):
        for functional in FUNCTIONALS[5:15]:
            with self.subTest(functional=functional):
                settings = replace(self.settings, functional=functional, write_json=True)
                output = self.root/(functional+'.inp')
                argv = command_arguments(self.source, -1, output, settings)
                args = build_parser().parse_args(argv[3:])
                restored = InputSettings.from_config({n: getattr(args, n) for n in InputSettings.__dataclass_fields__})
                self.assertEqual(generate_input(self.water, restored), generate_input(self.water, settings))
                path, sidecar, _ = write_input(self.water, settings, output)
                report = json.loads(sidecar.read_text())
                self.assertEqual(path.read_text(), report['input_text'])
                replay = InputSettings.from_config(report)
                self.assertEqual(generate_input(self.water, replay)[0], path.read_text())
                with self.assertRaises(OutputExists):
                    write_input(self.water, settings, output)

    def test_cli_subprocess_and_canonical_manifest(self):
        argv = command_arguments(self.source, -1, self.output,
                                 replace(self.settings, functional='B97M-RV', write_json=True))
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        report = json.loads(Path(str(self.output)+'.json').read_text())
        self.assertEqual(report['settings']['functional'], 'B97M-RV')
        self.assertTrue(report['nonlocal_correlation']['enabled'])

    def test_tui_build_approval_alias_preview_and_intrinsic_correlation_display(self):
        log = TTY()
        code = run_interactive(str(self.source), -1, str(self.output), InputSettings(periodic='NONE', write_json=True),
                               stdin=TTY('110\nB97M-rV\n114\ny\n113\ny\np\n\nw\ny\n'), stdout=log, plain=True)
        self.assertEqual(code, 0)
        report = json.loads(Path(str(self.output)+'.json').read_text())
        self.assertEqual(report['settings']['functional'], 'B97M-RV')
        self.assertIn('Required nonlocal correlation: RVV10', log.getvalue())
        self.assertIn('required RVV10 retained', log.getvalue())
        self.assertIn('--libxc-available', log.getvalue())
        self.assertIn('MGGA_XC_B97M_V', log.getvalue())
        # API-seeded aliases must not hide build approval or intrinsic correlation.
        seeded_output = self.root/'seeded-beef.inp'
        seeded_log = TTY()
        code = run_interactive(str(self.source), -1, str(seeded_output),
                               InputSettings(functional='BEEF-vdW', periodic='NONE', write_json=True),
                               stdin=TTY('114\ny\n113\ny\nw\ny\n'), stdout=seeded_log, plain=True)
        self.assertEqual(code, 0)
        self.assertIn('Required nonlocal correlation: LMKLL', seeded_log.getvalue())
        seeded = json.loads(Path(str(seeded_output)+'.json').read_text())
        self.assertEqual(seeded['settings']['functional'], 'BEEFVDW')
        self.assertEqual(seeded['method_profile']['xc_backend'], 'CP2K-native + Libxc')

    def test_visibility_uses_profile_build_requirements(self):
        fields = tuple(f for _, group in GROUPS for f in group)
        for functional, profile in FUNCTIONAL_PROFILES.items():
            values = {**asdict(self.settings), 'path': str(self.source), 'frame': -1, 'functional': functional}
            visible = {f.name for f in visible_fields(fields, values)}
            self.assertEqual('libxc_available' in visible, profile.libxc)
            self.assertEqual('allow_pbe_potential' in visible,
                             functional not in {'PBE', 'BLYP', 'PBE0', 'HSE06', 'B3LYP'})

    def test_cdd_all_components_share_xc_and_nonlocal_identity(self):
        for functional in ('PADE', 'BP86', 'R2SCAN', 'B97M-RV', 'BEEFVDW'):
            settings = replace(self.settings, functional=functional, density_difference=True,
                               fragment_a_indices='1', fragment_a_charge=0, fragment_a_multiplicity=1,
                               fragment_b_charge=0, fragment_b_multiplicity=1)
            _, report = generate_input(self.water, settings)
            for component in report['density_difference']['components'].values():
                self.assertEqual(component['settings']['functional'], functional)
                self.assertEqual(component['method_profile']['xc_components'], report['method_profile']['xc_components'])
                self.assertEqual(component['nonlocal_correlation'], report['nonlocal_correlation'])
                self.assertTrue(component['density_output']['enabled'])

    def test_cdd_kernel_mutation_between_components_is_rejected(self):
        data = self.data(kernel='rVV10_kernel_table.dat')
        settings = replace(self.settings, functional='B97M-RV', data_dir=str(data), density_difference=True,
                           fragment_a_indices='1', fragment_a_charge=0, fragment_a_multiplicity=1,
                           fragment_b_charge=0, fragment_b_multiplicity=1)
        original = generate_input
        calls = 0
        def mutate(structure, requested, **kwargs):
            nonlocal calls
            text, report = original(structure, requested, **kwargs)
            calls += 1
            if calls == 1:
                (data/'rVV10_kernel_table.dat').write_text('changed synthetic kernel')
            return text, report
        with patch('cp2kkit.inputgen.generate_input', side_effect=mutate), self.assertRaisesRegex(KitError, 'kernel identity'):
            write_input(self.water, settings, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name('new-fragment-A.inp').exists())


if __name__ == '__main__':
    unittest.main()
