"""Retained-0.2.8 grid/OT/restart/comment policy; synthetic, not native execution."""
import os
import unittest
from dataclasses import replace
from unittest.mock import patch

from cp2kkit.basis_registry import OPTIONS
from cp2kkit.gapw import resolve_ngrids
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.structure import Structure


class InputPolicyTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)
        self.water = Structure(['O', 'H', 'H'], [[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]],
                               None, None, {'path': 'synthetic.xyz'})
        self.settings = InputSettings(periodic='NONE')

    def generate(self, **kwargs):
        return generate_input(self.water, replace(self.settings, **kwargs))

    def test_every_ae_family_and_legacy_profile_defaults_to_explicit_irac(self):
        for option in OPTIONS:
            if option.kind_type != 'all-electron':
                continue
            for profile in ('auto', 'native'):
                with self.subTest(basis=option.id, profile=profile):
                    text, m = self.generate(basis=option.id, gapw_profile=profile)
                    self.assertEqual(text.count('        ALGORITHM IRAC\n'), 1)
                    self.assertEqual(m['method_profile']['ot_algorithm'], 'IRAC')
                    self.assertNotIn('NGRIDS', text)
                    self.assertIsNone(m['method_profile']['ngrids'])

    def test_every_builtin_pp_family_defaults_to_explicit_strict(self):
        for option in OPTIONS:
            if not option.selectable or option.kind_type == 'all-electron' or option.protocol == 'custom':
                continue
            atom = replace(self.water, symbols=['Fe' if option.id in ('molopt-sr-tzvp', 'molopt-sr-tzv2p') else 'O'],
                           positions=[[0., 0., 0.]])
            text, m = generate_input(atom, replace(self.settings, basis=option.id))
            self.assertIn('        ALGORITHM STRICT\n', text)
            self.assertEqual(m['method_profile']['ot_algorithm'], 'STRICT')

    def test_grid_policy_uses_effective_overrides_not_unused_global_basis(self):
        text, m = self.generate(basis_overrides=(('O', 'molopt-tzv2p'),))
        self.assertIn('NGRIDS 5', text)
        self.assertEqual(m['method_profile']['ngrids'], 5)
        text, m = self.generate(basis='molopt-tzv2p',
                                basis_overrides=(('O', 'molopt-sr-dzvp'), ('H', 'molopt-sr-dzvp')))
        self.assertNotIn('NGRIDS', text)
        self.assertIsNone(m['method_profile']['ngrids'])

    def test_custom_alias_does_not_infer_classic_registry_grid_policy(self):
        self.assertIsNone(resolve_ngrids({'O': {'basis_id': 'custom-orbital', 'basis': 'TZVP-MOLOPT-GTH'}}))
        for basis in ('molopt-tzvp', 'molopt-tzv2p', 'molopt-tzv2px'):
            self.assertEqual(resolve_ngrids({'O': {'basis_id': basis}}), 5)

    def test_backup_policy_is_nested_in_scf_and_does_not_disable_writing(self):
        for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT', 'CELL_OPT'):
            for scf in ('ot', 'diag'):
                text, m = self.generate(run_type=task, scf=scf, periodic='XYZ', cell=(12., 12., 12.))
                stack, backups = [], []
                for line in text.splitlines():
                    tokens = line.split('#', 1)[0].split()
                    if not tokens:
                        continue
                    if tokens[0].upper() == '&END':
                        self.assertEqual(stack.pop(), tokens[1])
                    elif tokens[0].startswith('&'):
                        stack.append(tokens[0][1:])
                    elif tokens[0] == 'BACKUP_COPIES':
                        self.assertEqual(tokens[1], '0')
                        backups.append(tuple(stack))
                self.assertFalse(stack)
                expected = [('FORCE_EVAL', 'DFT', 'SCF', 'PRINT', 'RESTART')]
                if task in ('GEO_OPT', 'CELL_OPT'):
                    expected.append(('MOTION', 'PRINT', 'RESTART'))
                self.assertEqual(backups, expected)
                self.assertNotIn('&RESTART OFF', text)
                self.assertEqual(m['wavefunction_output']['restart_backup_copies'], 0)
                self.assertTrue(m['wavefunction_output']['restart_enabled'])
                self.assertFalse(m['wavefunction_output']['runtime_validated'])

    def test_only_generator_and_multiwfn_header_comments_remain(self):
        for functional in ('PBE', 'BLYP', 'PBESOL', 'REVPBE', 'RPBE'):
            text, _ = self.generate(functional=functional, libxc_available=True, allow_pbe_potential=True,
                                    dispersion='d3bj', run_type='GEO_OPT', fixed_atoms='1',
                                    magnetism=(), electron_density=True)
            header, body = text.split('&GLOBAL', 1)
            self.assertEqual(len(header.splitlines()), 4)
            self.assertIn('# Generated by cp2kkit', header)
            self.assertIn('10.1002/jcc.22885', header)
            self.assertIn('10.1063/5.0216272', header)
            self.assertNotIn('#', body)
            self.assertNotIn('!', body)
            self.assertNotIn('SCF_GUESS', body)
            self.assertNotIn('WFN_RESTART_FILE_NAME', body)

    def test_restart_suggestion_does_not_claim_emitted_or_existing_file(self):
        for kpoints, suffix in (((1, 1, 1), '.wfn'), ((2, 2, 2), '.kp')):
            text, m = self.generate(project='actual-project', periodic='XYZ', cell=(12., 12., 12.),
                                    scf='diag', kpoints=kpoints)
            hint = m['restart_template']
            self.assertEqual(hint['filename'], 'actual-project-RESTART'+suffix)
            for key in ('enabled', 'emitted', 'filename_commented', 'guess_commented', 'runtime_verified'):
                self.assertFalse(hint[key])
            self.assertNotIn(hint['filename'], text)

    def test_uniform_scf_default_and_explicit_overrides_for_all_tasks(self):
        for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT', 'CELL_OPT'):
            for scf in ('ot', 'diag'):
                for requested in (None, 5e-6, 1e-8):
                    text, m = self.generate(run_type=task, scf=scf, eps_scf=requested,
                                            periodic='XYZ', cell=(12., 12., 12.))
                    expected = 1e-6 if requested is None else requested
                    values = [float(line.split()[1]) for line in text.splitlines()
                              if line.strip().startswith('EPS_SCF ')]
                    self.assertEqual(values, [expected]*(2 if scf == 'ot' else 1))
                    self.assertEqual(m['effective_eps_scf'], expected)
                    self.assertEqual(m['settings']['eps_scf'], requested)
                    self.assertIn('EPS_DEFAULT '+('1.0E-11' if task == 'ENERGY' else '1.0E-12'), text)

    def test_manual_ot_override_and_physical_settings_survive_policy_changes(self):
        for basis, algorithm in (('molopt-sr-dzvp', 'IRAC'), ('ae-def2-tzvp', 'STRICT')):
            text, m = self.generate(basis=basis, ot_algorithm=algorithm, charge=1, multiplicity=2,
                                    cutoff=477., rel_cutoff=63.)
            self.assertIn('ALGORITHM '+algorithm, text)
            for key, value in dict(charge=1, multiplicity=2, cutoff=477., rel_cutoff=63.).items():
                self.assertEqual(m['settings'][key], value)
            self.assertNotIn('NGRIDS', text)
