"""CP2K v2026.2 header/keyword regression, not calculations or recommended settings."""
import hashlib
import io
import json
import shlex
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import build_parser, main
from cp2kkit.data_catalog import CATALOG_SOURCES
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.input_tui import GROUPS, command_arguments, run_interactive, visible_fields
from cp2kkit.inputgen import BASES, FUNCTIONALS, VALENCE, InputSettings, generate_input, write_input
from cp2kkit.method_profiles import (BASIS_CATALOG, FUNCTIONAL_PROFILES, FunctionalProfile,
                                     format_basis_overrides, parse_basis_overrides)
from cp2kkit.structure import Structure, read_restart, read_structure


class TTY(io.StringIO):
    def isatty(self):
        return True


class MethodProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.path = self.dir/'synthetic.xyz'
        self.path.write_text('4\nsynthetic Fe2O2\nFe 0 0 0\nFe 2 0 0\nO 0 2 0\nO 2 2 0\n')
        self.structure = read_structure(self.path)
        self.water = Structure(['O', 'H', 'H'], [[0., 0., 0.], [0., 1., 0.], [1., 0., 0.]],
                               None, [False]*3, {'path': 'synthetic-water.xyz'})
        self.settings = InputSettings(periodic='NONE')
        self.output = self.dir/'new.inp'

    def generate(self, structure=None, **kwargs):
        return generate_input(self.water if structure is None else structure, replace(self.settings, **kwargs))

    def invoke(self, argv):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def session(self, lines, **kwargs):
        log = TTY()
        code = run_interactive(str(self.path), -1, str(self.output), replace(self.settings, **kwargs),
                               stdin=TTY(lines), stdout=log, plain=True)
        return code, log.getvalue()

    def mixed(self, **kwargs):
        return replace(self.settings, basis='TZV2P-MOLOPT-GTH',
                       basis_overrides=(('Fe', 'TZV2P-MOLOPT-SR-GTH'),), **kwargs)

    def data_files(self):
        # Deliberately header-only synthetic libraries: names/hashes, NOT native basis validation.
        (self.dir/'BASIS_MOLOPT').write_text('O TZV2P-MOLOPT-GTH-q6\n')
        (self.dir/'BASIS_MOLOPT_UCL').write_text('Fe TZV2P-MOLOPT-SR-GTH-q16\n')
        (self.dir/'GTH_POTENTIALS').write_text('O GTH-PBE-q6\nFe GTH-PBE-q16\n')

    def test_functional_names_and_distinct_xc_expansions(self):
        self.assertEqual(FUNCTIONALS, ('PBE', 'BLYP', 'PBESOL', 'REVPBE', 'RPBE'))
        for functional in ('PBESOL', 'REVPBE', 'RPBE'):
            with self.subTest(functional=functional):
                text, manifest = self.generate(functional=functional, allow_pbe_potential=True, libxc_available=True)
                if functional == 'RPBE':
                    self.assertIn('&GGA_X_RPBE\n', text)
                    self.assertIn('&GGA_C_PBE\n', text)
                    self.assertNotIn('PARAMETRIZATION', text)
                    self.assertEqual(manifest['method_profile']['xc_backend'], 'Libxc')
                else:
                    self.assertIn('&PBE\n          PARAMETRIZATION '+functional, text)
                    self.assertNotIn('&GGA_X_RPBE', text)
                    self.assertEqual(manifest['method_profile']['xc_backend'], 'CP2K-native')
                self.assertNotIn('&XC_FUNCTIONAL '+functional, text)
                self.assertFalse(manifest['method_profile']['build_verified'])
                self.assertIn('GTH-PBE-q6', text)
                self.assertNotIn('GTH-'+functional, text)

    def test_all_new_functionals_require_approval_when_potentials_are_unmatched(self):
        for functional in ('PBESOL', 'REVPBE', 'RPBE'):
            with self.subTest(functional=functional), self.assertRaisesRegex(KitError, '--allow-pbe-potential'):
                self.generate(functional=functional, libxc_available=True)
        code, _, err = self.invoke(['generate-input', str(self.path), '-o', str(self.output),
                                    '--periodic', 'NONE', '--functional', 'PBEsol'])
        self.assertEqual(code, 2)
        self.assertIn('--allow-pbe-potential', err)
        self.assertFalse(self.output.exists())

    def test_actual_pbesol_boron_potential_is_preferred_without_approval(self):
        boron = replace(self.water, symbols=['B'], positions=[[0., 0., 0.]])
        text, manifest = self.generate(boron, functional='PBESOL', multiplicity=2)
        self.assertIn('POTENTIAL GTH-PBESOL-q3', text)
        self.assertFalse(manifest['kinds']['B']['potential_approximation'])
        self.assertEqual(manifest['method_profile']['potential_approximations'], [])

    def test_mixed_exact_and_approved_potentials_keep_their_actual_identity(self):
        source = replace(self.water, symbols=['B', 'O'], positions=self.water.positions[:2])
        text, manifest = self.generate(source, functional='PBESOL', multiplicity=2, allow_pbe_potential=True)
        self.assertIn('GTH-PBESOL-q3', text)
        self.assertIn('GTH-PBE-q6', text)
        self.assertEqual(manifest['method_profile']['potential_approximations'], ['O'])
        self.assertTrue(any('User-approved GTH-PBE' in warning for warning in manifest['warnings']))

    def test_rpbe_requires_an_explicit_libxc_build_assertion(self):
        with self.assertRaisesRegex(KitError, '--libxc-available'):
            self.generate(functional='RPBE', allow_pbe_potential=True)
        _, manifest = self.generate(functional='RPBE', allow_pbe_potential=True, libxc_available=True)
        self.assertTrue(manifest['method_profile']['libxc_required'])
        self.assertTrue(manifest['method_profile']['libxc_user_asserted'])
        self.assertFalse(manifest['runtime_validated'])
        for kwargs in ({'libxc_available': 'yes'}, {'allow_pbe_potential': 1}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(KitError, 'Boolean'):
                self.generate(**kwargs)

    def test_dispersion_reference_whitelist_uses_the_actual_functional(self):
        for functional in FUNCTIONALS:
            for dispersion in ('none', 'd3', 'd3bj'):
                with self.subTest(functional=functional, dispersion=dispersion):
                    text, manifest = self.generate(functional=functional, dispersion=dispersion,
                                                   allow_pbe_potential=True, libxc_available=True)
                    if dispersion == 'none':
                        self.assertNotIn('&VDW_POTENTIAL', text)
                        self.assertIsNone(manifest['method_profile']['dispersion_reference'])
                    else:
                        self.assertIn('REFERENCE_FUNCTIONAL '+functional+'\n', text)
                        self.assertIn('TYPE DFTD3(BJ)' if dispersion == 'd3bj' else 'TYPE DFTD3\n', text)
        with patch.dict(FUNCTIONAL_PROFILES, {'REVPBE': FunctionalProfile('REVPBE', dispersion=('none',))}):
            with self.assertRaisesRegex(KitError, 'No checked d3 combination'):
                self.generate(functional='REVPBE', allow_pbe_potential=True, dispersion='d3')

    def test_sr_triple_zeta_families_use_ucl_and_preserve_valence(self):
        fe = replace(self.water, symbols=['Fe'], positions=[[0., 0., 0.]])
        for basis in ('TZVP-MOLOPT-SR-GTH', 'TZV2P-MOLOPT-SR-GTH'):
            with self.subTest(basis=basis):
                text, manifest = self.generate(fe, basis=basis)
                self.assertIn('BASIS_SET_FILE_NAME "BASIS_MOLOPT_UCL"', text)
                self.assertIn('BASIS_SET '+basis+'-q16', text)
                self.assertIn('NGRIDS 4', text)
                self.assertEqual(manifest['valence_electron_count'], 16)

    def test_sr_missing_light_elements_and_mg_q_mismatch_never_fallback(self):
        for basis in ('TZVP-MOLOPT-SR-GTH', 'TZV2P-MOLOPT-SR-GTH'):
            with self.assertRaisesRegex(KitError, 'No basis or valence fallback'):
                self.generate(basis=basis)
            mg = replace(self.water, symbols=['Mg'], positions=[[0., 0., 0.]])
            with self.assertRaisesRegex(KitError, 'q10'):
                self.generate(mg, basis=basis)
        # UCL has Mg-q2, but the generator's explicit-valence preset remains Mg-q10.
        self.assertEqual(BASIS_CATALOG['BASIS_MOLOPT_UCL']['TZVP-MOLOPT-SR-GTH']['Mg'], (2,))

    def test_tzv2px_and_non_sr_coverage_extensions(self):
        text, _ = self.generate(basis='TZV2PX-MOLOPT-GTH')
        self.assertIn('TZV2PX-MOLOPT-GTH-q6', text)
        self.assertIn('NGRIDS 5', text)
        for el, bases in (('Cu', ('DZVP-MOLOPT-GTH',)),
                          ('Br', ('DZVP-MOLOPT-GTH', 'TZVP-MOLOPT-GTH', 'TZV2P-MOLOPT-GTH', 'TZV2PX-MOLOPT-GTH'))):
            for basis in bases:
                with self.subTest(el=el, basis=basis):
                    atom = replace(self.water, symbols=[el], positions=[[0., 0., 0.]])
                    _, manifest = self.generate(atom, basis=basis, multiplicity=2)
                    self.assertEqual(manifest['kinds'][el]['basis_file'], 'BASIS_MOLOPT_UCL')
                    self.assertEqual(manifest['kinds'][el]['valence_electrons'], VALENCE[el])

    def test_explicit_mixed_basis_files_and_grid_are_deterministic(self):
        settings = self.mixed()
        text, manifest = generate_input(self.structure, settings)
        self.assertEqual(text.count('BASIS_SET_FILE_NAME'), 2)
        self.assertEqual(manifest['method_profile']['basis_files'], ['BASIS_MOLOPT', 'BASIS_MOLOPT_UCL'])
        self.assertIn('NGRIDS 5', text)
        self.assertIn('TZV2P-MOLOPT-GTH-q6', text)
        self.assertIn('TZV2P-MOLOPT-SR-GTH-q16', text)
        self.assertEqual((text, manifest), generate_input(self.structure, settings))

    def test_overrides_apply_to_both_afm_kinds_with_hubbard_correction(self):
        settings = self.mixed(functional='RPBE', allow_pbe_potential=True, libxc_available=True,
                              magnetism=(('@2', -4.), ('Fe', 4.)), dft_plus_u=(('Fe', 2, 4.),))
        before = self.path.read_bytes()
        output, sidecar, _ = write_input(self.structure, settings, self.output)
        manifest = json.loads(sidecar.read_text())
        for label in ('Fe_m1', 'Fe_m2'):
            self.assertEqual(manifest['kinds'][label]['basis'], 'TZV2P-MOLOPT-SR-GTH-q16')
            self.assertEqual(manifest['kinds'][label]['basis_file'], 'BASIS_MOLOPT_UCL')
            self.assertEqual(manifest['kinds'][label]['dft_plus_u']['U_minus_J'], 4.)
        self.assertEqual(read_restart(output).symbols, self.structure.symbols)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(manifest['settings']['multiplicity'], 1)
        self.assertEqual(manifest['settings']['charge'], 0)

    def test_all_legacy_sr_pbe_valence_presets_still_generate(self):
        for basis in BASES[:2]:
            for el, q in VALENCE.items():
                with self.subTest(el=el, basis=basis):
                    atom = replace(self.water, symbols=[el], positions=[[0., 0., 0.]])
                    text, manifest = self.generate(atom, basis=basis, multiplicity=1+q%2)
                    self.assertIn(f'POTENTIAL GTH-PBE-q{q}', text)
                    self.assertEqual(manifest['kinds'][el]['basis_file'], 'BASIS_MOLOPT')
        self.assertEqual(len(VALENCE), 71)

    def test_all_advertised_basis_coverages_use_the_fixed_valence_policy(self):
        expected_counts = dict(zip(BASES, (71, 71, 11, 10, 10, 54, 54, 10)))
        for basis, count in expected_counts.items():
            supported = [el for el, q in VALENCE.items()
                         if any(q in families.get(basis, {}).get(el, ()) for families in BASIS_CATALOG.values())]
            self.assertEqual(len(supported), count)
            for el in supported:
                with self.subTest(el=el, basis=basis):
                    atom = replace(self.water, symbols=[el], positions=[[0., 0., 0.]])
                    _, manifest = self.generate(atom, basis=basis, multiplicity=1+VALENCE[el]%2)
                    self.assertEqual(manifest['kinds'][el]['basis'], f'{basis}-q{VALENCE[el]}')

    def test_new_features_are_version_gated_but_legacy_profiles_are_preserved(self):
        for version in ('2024.1', '2025.2', '2026.1'):
            self.generate(cp2k_version=version)
            for kwargs in ({'functional': 'PBESOL', 'allow_pbe_potential': True},
                           {'basis': 'TZV2PX-MOLOPT-GTH'},
                           {'basis_overrides': (('O', 'TZVP-MOLOPT-GTH'),)}):
                with self.subTest(version=version, kwargs=kwargs), self.assertRaisesRegex(KitError, 'only for CP2K 2026.2'):
                    self.generate(cp2k_version=version, **kwargs)

    def test_basis_map_roundtrip_and_invalid_api_entries(self):
        value = parse_basis_overrides('O=TZVP-MOLOPT-GTH; Fe=TZV2P-MOLOPT-SR-GTH')
        self.assertEqual(parse_basis_overrides(format_basis_overrides(value)), value)
        for raw in ('off', 'none', 'auto'):
            self.assertEqual(parse_basis_overrides(raw), ())
        for raw in ('Fe=bogus', 'Fe', 'Fe=TZVP-MOLOPT-GTH; Fe=DZVP-MOLOPT-GTH', '@1=TZVP-MOLOPT-GTH'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_basis_overrides(raw)
        for value in ('Fe=TZVP-MOLOPT-GTH', ({'Fe': 'TZVP-MOLOPT-GTH'},), ((1, 'TZVP-MOLOPT-GTH'),),
                      (('Co', 'TZVP-MOLOPT-GTH'),), (('Fe', 'bogus'),), (('Fe', 'off; O=TZVP-MOLOPT-GTH'),),
                      (('Fe', 'TZVP-MOLOPT-GTH; O=TZVP-MOLOPT-GTH'),)):
            with self.subTest(value=value), self.assertRaises(KitError):
                self.generate(self.structure, basis_overrides=value)

    def test_multiple_data_files_are_verified_and_hashed_individually(self):
        self.data_files()
        settings = self.mixed(data_dir=str(self.dir))
        text, manifest = generate_input(self.structure, settings)
        expected = {'basis': 'BASIS_MOLOPT', 'basis:BASIS_MOLOPT_UCL': 'BASIS_MOLOPT_UCL', 'potential': 'GTH_POTENTIALS'}
        self.assertEqual(set(manifest['data_sources']), set(expected))
        for key, filename in expected.items():
            path = self.dir/filename
            self.assertEqual(manifest['data_sources'][key]['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertIn(str(path.resolve()), text)

    def test_wrong_library_or_q_header_cannot_satisfy_selected_basis(self):
        self.data_files()
        (self.dir/'BASIS_MOLOPT').write_text('O TZV2P-MOLOPT-GTH-q6\nFe TZV2P-MOLOPT-SR-GTH-q16\n')
        (self.dir/'BASIS_MOLOPT_UCL').write_text('Fe TZV2P-MOLOPT-SR-GTH-q8\n')
        with self.assertRaisesRegex(KitError, 'BASIS_MOLOPT_UCL has no Fe'):
            generate_input(self.structure, self.mixed(data_dir=str(self.dir)))
        (self.dir/'BASIS_MOLOPT_UCL').unlink()  # Own synthetic artifact only.
        with self.assertRaisesRegex(KitError, 'Cannot read'):
            write_input(self.structure, self.mixed(data_dir=str(self.dir)), self.output)
        self.assertFalse(self.output.exists())

    def test_cli_replay_roundtrip_including_approvals_and_sorted_api_maps(self):
        settings = self.mixed(functional='RPBE', allow_pbe_potential=True, libxc_available=True)
        settings = replace(settings, basis_overrides=[['O', 'TZV2P-MOLOPT-GTH'], ['Fe', 'TZV2P-MOLOPT-SR-GTH']])
        argv = command_arguments(self.path, -1, self.output, settings)
        self.assertEqual(shlex.split(shlex.join(argv)), argv)
        parsed = build_parser().parse_args(argv[3:])
        self.assertEqual(parsed.basis_overrides[0][0], 'Fe')
        code, stdout, _ = self.invoke(argv[3:])
        self.assertEqual(code, 0)
        self.assertEqual(stdout, '')
        text, expected = generate_input(self.structure, settings)
        self.assertEqual(self.output.read_text(), text)
        self.assertEqual(json.loads(Path(str(self.output)+'.json').read_text()), json.loads(json.dumps(expected)))

    def test_interactive_rpbe_requires_both_manual_assertions(self):
        code, log = self.session('1\nRPBE\n129\ny\n130\ny\n0\ny\n\n')
        self.assertEqual(code, 0)
        self.assertIn('--allow-pbe-potential', log)
        self.assertIn('--libxc-available', log)
        self.assertIn('XC backend: Libxc', log)
        self.assertIn('potential approximation: True', log)
        settings = replace(self.settings, functional='RPBE', allow_pbe_potential=True, libxc_available=True)
        self.assertEqual(self.output.read_text(), generate_input(self.structure, settings)[0])

    def test_interactive_mixed_basis_edit_and_clear(self):
        _, log = self.session('2\nTZV2P-MOLOPT-GTH\n128\nFe=bogus\nFe=TZV2P-MOLOPT-SR-GTH\n0\ny\n\n')
        self.assertIn('Invalid input', log)
        self.assertIn('BASIS_MOLOPT_UCL', log)
        self.assertEqual(self.output.read_text(), generate_input(self.structure, self.mixed())[0])
        other = self.dir/'clear.inp'
        log = TTY()
        run_interactive(str(self.path), -1, str(other), self.mixed(),
                        stdin=TTY('128\noff\n2\nDZVP-MOLOPT-SR-GTH\n0\ny\n\n'), stdout=log, plain=True)
        self.assertNotIn('BASIS_MOLOPT_UCL', other.read_text())

    def test_hidden_approvals_are_retained_without_changing_backend(self):
        fields = [f for _, group in GROUPS for f in group]
        from dataclasses import asdict
        values = {**asdict(self.settings), 'path': str(self.path), 'frame': -1}
        visible = lambda: {f.name for f in visible_fields(fields, values)}
        self.assertNotIn('allow_pbe_potential', visible())
        self.assertNotIn('libxc_available', visible())
        values['functional'] = 'PBESOL'
        self.assertIn('allow_pbe_potential', visible())
        self.assertNotIn('libxc_available', visible())
        values['functional'] = 'RPBE'
        self.assertIn('libxc_available', visible())
        self.session('1\nPBE\n0\ny\n\n', functional='RPBE', allow_pbe_potential=True, libxc_available=True)
        manifest = json.loads(Path(str(self.output)+'.json').read_text())
        self.assertTrue(manifest['settings']['allow_pbe_potential'])
        self.assertTrue(manifest['settings']['libxc_available'])
        self.assertFalse(manifest['method_profile']['libxc_required'])
        self.assertEqual(manifest['method_profile']['xc_backend'], 'CP2K-native')
        self.assertNotIn('GGA_X_RPBE', self.output.read_text())

    def test_extended_outputs_still_refuse_collisions(self):
        sidecar = Path(str(self.output)+'.json')
        sidecar.write_text('existing')
        with self.assertRaises(OutputExists):
            write_input(self.structure, self.mixed(), self.output)
        self.assertEqual(sidecar.read_text(), 'existing')
        self.assertFalse(self.output.exists())

    def test_catalog_metadata_is_pinned_and_not_mutable_through_a_manifest(self):
        _, manifest = self.generate()
        for source in CATALOG_SOURCES:
            self.assertIn('/v2026.2/', source['url'])
            self.assertRegex(source['sha256'], r'^[a-f0-9]{64}$')
        manifest['method_profile']['catalog_sources'][0]['sha256'] = 'modified'
        _, next_manifest = self.generate()
        self.assertNotEqual(next_manifest['method_profile']['catalog_sources'][0]['sha256'], 'modified')
        self.assertFalse(next_manifest['method_profile']['runtime_validated'])
