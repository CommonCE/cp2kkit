"""Synthetic AE/OT contracts; no CP2K or Multiwfn execution."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.basis_registry import OPTIONS, parse_basis
from cp2kkit.cli import build_parser, main
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.input_tui import command_arguments, run_interactive
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.structure import Structure
from tests.synthetic_cp2k_data import basis_entry


class TTY(io.StringIO):
    def isatty(self):
        return True


class AllElectronTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        environment = patch.dict(os.environ, {}, clear=False)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop('CP2K_DATA_DIR', None)
        self.water = Structure(['O', 'H', 'H'], [[0., 0., 0.], [.76, 0., .58], [-.76, 0., .58]],
                               None, None, {'path': 'synthetic-water.xyz'})
        self.settings = InputSettings(periodic='NONE', basis='ae-pob-tzvp')

    def generate(self, **kwargs):
        return generate_input(self.water, replace(self.settings, **kwargs))

    def libraries(self, basis=None, potential=None):
        b = self.root/'basis'
        p = self.root/'potential'
        b.write_text(basis or basis_entry('O', 'pob-TZVP')+basis_entry('H', 'pob-TZVP'))
        p.write_text(potential or 'O ALL ALLELECTRON\n 2 2 4\n .2 0\nH ALL ALLELECTRON\n 1\n .2 0\n')
        return {'basis_files': (str(b),), 'potential_files': (str(p),)}

    def test_every_family_generates_a_complete_water_template(self):
        ae = [o for o in OPTIONS if o.kind_type == 'all-electron']
        self.assertEqual([o.number for o in ae], list(range(50, 60)))
        for option in ae:
            with self.subTest(option=option.id):
                text, m = self.generate(basis=option.id)
                self.assertIn('METHOD GAPW', text)
                self.assertIn('POTENTIAL ALL', text)
                self.assertNotIn('POTENTIAL GTH-', text)
                self.assertNotIn('-q8', text)
                self.assertEqual(m['explicit_electron_count'], 10)
                self.assertIsNone(m['valence_electron_count'])
                self.assertEqual(m['electron_count_model'], 'all_electron')
                self.assertEqual(m['basis_validation']['status'], 'unverified_template')
                self.assertFalse(m['runtime_validated'])
                for kind in m['kinds'].values():
                    self.assertIsNone(kind['basis_q'])
                    self.assertIsNone(kind['potential_q'])
                    self.assertIsNone(kind['valence_electrons'])

    def test_automatic_settings_and_pob_irac(self):
        text, m = self.generate(cutoff=477., rel_cutoff=63.)
        for line in ('ALGORITHM IRAC', 'PRECONDITIONER FULL_ALL',
                     'CUTOFF [Ry] 477', 'REL_CUTOFF [Ry] 63'):
            self.assertIn(line, text)
        self.assertFalse(m['method_profile']['gapw']['convergence_verified'])
        self.assertTrue(m['method_profile']['gapw']['automatic_settings'])
        self.assertIn('ALGORITHM IRAC', self.generate(basis='ae-def2-tzvp')[0])
        self.assertFalse(any('Non-SR MOLOPT' in w for w in m['warnings']))

    def test_all_profiles_omit_gapw_threshold_and_atomic_grid_overrides(self):
        controls = ('EPSFIT', 'EPSRHO0', 'EPSSVD', 'LEBEDEV_GRID', 'RADIAL_GRID')
        for basis in (o.id for o in OPTIONS if o.kind_type == 'all-electron'):
            for profile in ('auto', 'native'):
                with self.subTest(basis=basis, profile=profile):
                    text, m = self.generate(basis=basis, gapw_profile=profile)
                    for keyword in controls:
                        self.assertNotIn(keyword, text)
                    gapw = m['method_profile']['gapw']
                    self.assertEqual(gapw['qs'], {})
                    self.assertEqual(gapw['kind'], {})
                    self.assertEqual(gapw['cp2k_default_controls'], [*controls, 'NGRIDS'])
                    self.assertFalse(any(i['setting'].split('/')[-1] in controls for i in gapw['automatic_settings']))

    def test_native_profile_omits_numerical_conveniences(self):
        text, m = self.generate(gapw_profile='native')
        for keyword in ('EPSFIT', 'EPSRHO0', 'EPSSVD', 'LEBEDEV_GRID', 'RADIAL_GRID'):
            self.assertNotIn(keyword, text)
        self.assertIn('METHOD GAPW', text)
        self.assertNotIn('NGRIDS', text)
        self.assertIn('ALGORITHM IRAC', text)
        self.assertEqual(m['method_profile']['ot_algorithm'], 'IRAC')

    def test_ae_omitted_grid_matches_metadata_without_resetting_cutoffs(self):
        for profile in ('auto', 'native'):
            text, m = self.generate(gapw_profile=profile, cutoff=477., rel_cutoff=63.)
            self.assertNotIn('NGRIDS', text)
            self.assertIsNone(m['method_profile']['ngrids'])
            self.assertIsNone(m['method_profile']['gapw']['ngrids'])
            self.assertEqual(m['method_profile']['gapw']['profile_version'], 4)
            self.assertFalse(any(i['setting'] == 'MGRID/NGRIDS'
                                 for i in m['method_profile']['gapw']['automatic_settings']))
            self.assertEqual(m['settings']['cutoff'], 477.)
            self.assertEqual(m['settings']['rel_cutoff'], 63.)
        self.assertNotIn('NGRIDS', self.generate(basis='molopt-sr-dzvp')[0])

    def test_manual_ot_algorithm_wins_over_auto_and_native(self):
        for profile in ('auto', 'native'):
            for algorithm in ('STRICT', 'IRAC'):
                with self.subTest(profile=profile, algorithm=algorithm):
                    text, m = self.generate(gapw_profile=profile, ot_algorithm=algorithm)
                    self.assertIn('ALGORITHM '+algorithm, text)
                    self.assertEqual(m['method_profile']['ot_algorithm'], algorithm)
                    item = next(i for i in m['method_profile']['gapw']['automatic_settings']
                                if i['setting'] == 'SCF/OT/ALGORITHM')
                    self.assertEqual(item['source'], 'user')

    def test_pp_default_ot_selection_is_explicit_strict(self):
        text, m = self.generate(basis='molopt-sr-dzvp')
        self.assertIn('ALGORITHM STRICT', text)
        self.assertIsNone(m['method_profile']['gapw'])
        self.assertEqual(m['valence_electron_count'], 8)
        self.assertEqual(m['explicit_electron_count'], 8)
        self.assertIn('ALGORITHM IRAC', self.generate(basis='molopt-sr-dzvp', ot_algorithm='IRAC')[0])
        self.assertIn('ALGORITHM STRICT', self.generate(basis='molopt-sr-dzvp', ot_algorithm='STRICT')[0])

    def test_diagonalization_preserves_but_does_not_emit_ot_algorithm(self):
        text, m = self.generate(scf='diag', ot_algorithm='IRAC')
        self.assertNotIn('&OT', text)
        self.assertNotIn('ALGORITHM IRAC', text)
        self.assertIsNone(m['method_profile']['ot_algorithm'])
        self.assertEqual(m['settings']['ot_algorithm'], 'IRAC')

    def test_ae_magnetic_bounds_and_split_kinds_use_core_inclusive_counts(self):
        _, m = self.generate(magnetism=(('O', 7.), ('@2', 1.), ('@3', -1.)))
        self.assertEqual(m['source_structure']['symbols'], ['O', 'H', 'H'])
        self.assertEqual(len(m['kinds']), 3)
        self.assertEqual(sorted(k['explicit_electrons'] for k in m['kinds'].values()), [1, 1, 8])
        with self.assertRaises(KitError):
            self.generate(basis='molopt-sr-dzvp', magnetism=(('O', 7.),))

    def test_main_menu_numeric_algorithm_choices_and_enter_keep(self):
        path = self.root/'one.xyz'
        path.write_text('1\nsynthetic atom\nO 0 0 0\n')
        for number, algorithm in ((1, 'IRAC'), (2, 'STRICT')):
            output = self.root/f'choice-{number}.inp'
            log = TTY()
            run_interactive(str(path), -1, str(output), self.settings,
                            stdin=TTY(f'324\n{number}\n324\n\n0\ny\n\n'), stdout=log, plain=True)
            self.assertIn('ALGORITHM '+algorithm, output.read_text())

    def test_invalid_algorithm_and_profile_are_not_repaired(self):
        for kwargs in ({'ot_algorithm': 'BROYDEN'}, {'ot_algorithm': 'irac'}, {'gapw_profile': 'tight'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(KitError):
                self.generate(**kwargs)

    def test_actual_synthetic_nuclear_potential_and_hashes(self):
        _, m = self.generate(**self.libraries())
        self.assertEqual(m['basis_validation']['status'], 'data_checked')
        self.assertEqual(m['kinds']['O']['nuclear_charge'], 8)
        self.assertEqual(m['kinds']['O']['nuclear_charge_source'], 'nuclear_occupations')
        self.assertRegex(m['kinds']['O']['potential_source']['sha256'], r'^[0-9a-f]{64}$')
        self.assertFalse(m['basis_validation']['runnable_verified'])

    def test_bad_all_potential_payloads_rejected(self):
        for payload in ('O ALL\n', 'O ALL\n 6\n .2 0\n', 'O ALL\n 8\n .2 1\n',
                        'O ALL\n 8\n NaN 0\n', 'O GTH-PBE-q8\n 8\n .2 1 -1\n 0\n'):
            with self.subTest(payload=payload), self.assertRaises(KitError):
                self.generate(**self.libraries(potential=payload))

    def test_q_qualified_orbital_is_not_an_ae_entry(self):
        with self.assertRaises(KitError):
            self.generate(**self.libraries(basis=basis_entry('O', 'pob-TZVP', 'pob-TZVP-q8')))

    def test_mixed_models_rejected_but_all_ae_element_overrides_work(self):
        with self.assertRaisesRegex(KitError, 'Mixed all-electron'):
            self.generate(basis_overrides=(('H', 'molopt-sr-dzvp'),))
        text, m = self.generate(basis='molopt-sr-dzvp',
                               basis_overrides=(('O', 'ae-pob-tzvp'), ('H', 'ae-def2-tzvp')))
        self.assertIn('METHOD GAPW', text)
        self.assertEqual(m['explicit_electron_count'], 10)
        self.assertIn('ALGORITHM IRAC', text)

    def test_unsupported_requests_are_not_silently_disabled(self):
        for kwargs in ({'electron_density': True}, {'dft_plus_u': (('O', 1, 2.),)},
                       {'cp2k_version': '2025.1'}, {'run_type': 'CELL_OPT'}, {'kpoints': (2, 2, 2)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(KitError):
                self.generate(**kwargs)

    def test_heavy_ecp_branch_is_not_turned_into_all_electron(self):
        heavy = Structure(['Rb'], [[0., 0., 0.]], None, None, {'path': 'Rb.xyz'})
        with self.assertRaisesRegex(KitError, 'No audited all-electron coverage'):
            generate_input(heavy, replace(self.settings, multiplicity=2))

    def test_functional_charge_spin_and_cutoffs_preserved(self):
        _, m = self.generate(functional='BLYP', charge=1, multiplicity=2, dispersion='d3bj',
                             eps_scf=2e-7, cutoff=500., rel_cutoff=70.)
        for k, value in dict(functional='BLYP', charge=1, multiplicity=2, dispersion='d3bj',
                             eps_scf=2e-7, cutoff=500., rel_cutoff=70.).items():
            self.assertEqual(m['settings'][k], value)
        self.assertEqual(m['explicit_electron_count'], 9)
        self.assertFalse(m['kinds']['O']['potential_approximation'])
        with self.assertRaisesRegex(KitError, 'Charge/multiplicity inconsistent'):
            self.generate(charge=1, multiplicity=1)

    def test_semantic_names_replay_and_sidecar_roundtrip(self):
        self.assertEqual(parse_basis('def2-tzvp'), 'ae-def2-tzvp')
        self.assertEqual(parse_basis('pob-tzvp'), 'ae-pob-tzvp')
        settings = replace(self.settings, ot_algorithm='STRICT')
        _, m = generate_input(self.water, settings)
        loaded = InputSettings.from_config(json.loads(json.dumps(m)))
        self.assertEqual(generate_input(self.water, loaded)[0], generate_input(self.water, settings)[0])
        args = command_arguments('water.xyz', -1, 'new.inp', settings)
        parsed = build_parser().parse_args(args[3:])
        self.assertEqual(parsed.ot_algorithm, 'STRICT')
        self.assertEqual(parsed.gapw_profile, 'auto')

    def test_opt_in_json_collision_preserves_previous_input(self):
        output = self.root/'new.inp'
        write_input(self.water, replace(self.settings, write_json=True), output)
        original = output.read_bytes()
        with self.assertRaises(OutputExists):
            write_input(self.water, replace(self.settings, ot_algorithm='STRICT', write_json=True), output)
        self.assertEqual(output.read_bytes(), original)

    def test_cli_ot_algorithm_is_case_insensitive(self):
        path = self.root/'water.xyz'
        path.write_text('3\nsynthetic\nO 0 0 0\nH .76 0 .58\nH -.76 0 .58\n')
        output = self.root/'cli.inp'
        with redirect_stderr(io.StringIO()):
            code = main(['generate-input', str(path), '-o', str(output), '--periodic', 'NONE',
                         '--basis', 'ae-pob-tzvp', '--ot-algorithm', 'strict'])
        self.assertEqual(code, 0)
        self.assertIn('ALGORITHM STRICT', output.read_text())

    def test_direct_324_choices_keep_cancel_auto_and_hidden_value(self):
        path = self.root/'water.xyz'
        path.write_text('3\nsynthetic\nO 0 0 0\nH .76 0 .58\nH -.76 0 .58\n')
        output = self.root/'menu.inp'
        # Explicit STRICT, switch diag/back, abandoned change, then confirm.
        lines = '300\n324\nSTRICT\n4\ndiag\n4\not\n324\nback\n0\n0\ny\n\n'
        log = TTY()
        code = run_interactive(str(path), -1, str(output), replace(self.settings, write_json=True),
                               stdin=TTY(lines), stdout=log, plain=True)
        self.assertEqual(code, 0)
        self.assertIn('324. ALGORITHM:', log.getvalue())
        self.assertIn('IRAC', log.getvalue())
        self.assertIn('STRICT', log.getvalue())
        self.assertIn('ALGORITHM STRICT', output.read_text())
        self.assertEqual(json.loads(Path(str(output)+'.json').read_text())['settings']['ot_algorithm'], 'STRICT')
        # Auto restores pob IRAC without altering the stored starting settings.
        other = self.root/'auto.inp'
        run_interactive(str(path), -1, str(other), replace(self.settings, ot_algorithm='STRICT'),
                        stdin=TTY('324\nauto\n0\ny\n\n'), stdout=TTY(), plain=True)
        self.assertIn('ALGORITHM IRAC', other.read_text())
