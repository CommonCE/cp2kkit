"""Restart hints and optimization output contracts; no native calculation."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import build_parser, main
from cp2kkit.errors import KitError
from cp2kkit.input_tui import command_arguments, run_interactive
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.structure import Structure
from tests.test_input_tui import TTY


class RestartMotionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root/'oxygen.xyz'
        self.source.write_text('1\nsynthetic atom\nO 0 0 0\n')
        self.atom = Structure(['O'], [[0., 0., 0.]], None, None, {'path': str(self.source)})
        self.settings = InputSettings(periodic='NONE')
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def generate(self, **kwargs):
        return generate_input(self.atom, replace(self.settings, **kwargs))

    def test_gamma_restart_lines_are_commented_and_use_project_not_output(self):
        text, m = self.generate(project='custom-name')
        self.assertIn('#   WFN_RESTART_FILE_NAME custom-name-RESTART.wfn\n', text)
        self.assertIn('#     SCF_GUESS RESTART #', text)
        active = '\n'.join(line.split('#', 1)[0] for line in text.splitlines())
        self.assertNotIn('SCF_GUESS', active)
        self.assertNotIn('WFN_RESTART_FILE_NAME', active)
        self.assertNotIn('SCF_GUESS ATOMIC', text)
        self.assertFalse(m['restart_template']['enabled'])
        self.assertFalse(m['restart_template']['runtime_verified'])
        self.assertEqual(m['restart_template']['filename'], 'custom-name-RESTART.wfn')

    def test_default_project_restart_name_follows_source_stem(self):
        self.assertIn('#   WFN_RESTART_FILE_NAME oxygen-RESTART.wfn', self.generate()[0])

    def test_non_gamma_uses_kp_extension_without_reading_restart(self):
        text, m = self.generate(project='solid', periodic='XYZ', cell=(12., 12., 12.),
                                scf='diag', kpoints=(2, 2, 2))
        self.assertIn('#   WFN_RESTART_FILE_NAME solid-RESTART.kp', text)
        self.assertNotIn('solid-RESTART.wfn', text)
        self.assertFalse(m['restart_template']['enabled'])
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_gamma_diagonalization_still_uses_wfn(self):
        self.assertIn('oxygen-RESTART.wfn', self.generate(scf='diag')[0])

    def test_bfgs_lbfgs_radius_nesting_for_both_optimization_tasks(self):
        for task in ('GEO_OPT', 'CELL_OPT'):
            for optimizer in ('BFGS', 'LBFGS'):
                with self.subTest(task=task, optimizer=optimizer):
                    text, m = self.generate(run_type=task, optimizer=optimizer,
                                            periodic='XYZ', cell=(12., 12., 12.))
                    self.assertIn(f'    &{optimizer}\n      TRUST_RADIUS [angstrom] 0.2\n    &END {optimizer}', text)
                    motion = text.split('&MOTION\n', 1)[1]
                    self.assertLess(motion.index('TRUST_RADIUS'), motion.index('&END '+task))
                    self.assertEqual(m['motion_output']['trust_radius_angstrom'], .2)
                    self.assertEqual(m['units']['trust_radius'], 'angstrom')

    def test_all_electron_optimization_shares_restart_and_motion_controls(self):
        for profile in ('auto', 'native'):
            text, m = self.generate(run_type='GEO_OPT', basis='ae-pob-tzvp',
                                    gapw_profile=profile, trajectory_format='EXTXYZ')
            self.assertEqual(m['electron_count_model'], 'all_electron')
            self.assertIn('METHOD GAPW', text)
            self.assertIn('#   WFN_RESTART_FILE_NAME oxygen-RESTART.wfn', text)
            self.assertIn('TRUST_RADIUS [angstrom] 0.2', text)
            self.assertIn('FORMAT EXTXYZ', text)
            self.assertIn('BACKUP_COPIES 0', text)
            for keyword in ('EPSFIT', 'EPSRHO0', 'EPSSVD', 'LEBEDEV_GRID', 'RADIAL_GRID'):
                self.assertNotIn(keyword, text)

    def test_cg_does_not_emit_radius_and_retains_requested_value(self):
        text, m = self.generate(run_type='GEO_OPT', optimizer='CG', trust_radius=.37)
        self.assertNotIn('TRUST_RADIUS', text)
        self.assertIsNone(m['motion_output']['trust_radius_angstrom'])
        self.assertEqual(m['settings']['trust_radius'], .37)

    def test_radius_precision_and_integer_api_replay_are_stable(self):
        for radius in (2, .1234567890123456):
            settings = replace(self.settings, run_type='GEO_OPT', trust_radius=radius)
            text, m = generate_input(self.atom, settings)
            argv = command_arguments(self.source, -1, self.root/'next.inp', settings)
            parsed = build_parser().parse_args(argv[3:])
            replay = replace(settings, trust_radius=parsed.trust_radius)
            self.assertEqual(generate_input(self.atom, replay)[0], text)
            self.assertEqual(m['motion_output']['trust_radius_angstrom'], float(radius))

    def test_invalid_radius_is_not_repaired(self):
        for radius in (0, -1, float('inf'), float('nan'), 10**500, True, '0.2'):
            with self.subTest(radius=radius), self.assertRaises(KitError):
                self.generate(run_type='GEO_OPT', trust_radius=radius)

    def test_all_three_formats_and_backup_section_in_motion(self):
        for task in ('GEO_OPT', 'CELL_OPT'):
            for fmt in ('PDB', 'XYZ', 'EXTXYZ'):
                with self.subTest(task=task, format=fmt):
                    text, m = self.generate(run_type=task, periodic='XYZ', cell=(12., 12., 12.),
                                            trajectory_format=fmt)
                    self.assertIn('  &PRINT\n    &TRAJECTORY\n      FORMAT '+fmt+'\n    &END TRAJECTORY\n    &RESTART\n      BACKUP_COPIES 0', text)
                    self.assertEqual(text.count('BACKUP_COPIES 0'), 1)
                    self.assertEqual(m['motion_output']['trajectory_format'], fmt)
                    self.assertEqual(m['motion_output']['restart_backup_copies'], 0)
                    self.assertIn('RESTART\n  &END PRINT\n&END MOTION', text)

    def test_energy_omits_motion_and_keeps_hidden_output_preferences(self):
        for task in ('ENERGY', 'ENERGY_FORCE'):
            text, m = self.generate(run_type=task, trajectory_format='PDB', trust_radius=.37)
            self.assertNotIn('&MOTION', text)
            self.assertNotIn('TRUST_RADIUS', text)
            self.assertFalse(m['motion_output']['enabled'])
            self.assertIsNone(m['motion_output']['trajectory_format'])
            self.assertEqual(m['settings']['trajectory_format'], 'PDB')
            self.assertEqual(m['settings']['trust_radius'], .37)

    def test_invalid_format_rejected_and_extxyz_target_gate_is_conditional(self):
        with self.assertRaises(KitError):
            self.generate(run_type='GEO_OPT', trajectory_format='DCD')
        with self.assertRaisesRegex(KitError, 'EXTXYZ'):
            self.generate(run_type='GEO_OPT', trajectory_format='EXTXYZ', cp2k_version='2024.1')
        self.assertNotIn('&MOTION', self.generate(trajectory_format='EXTXYZ', cp2k_version='2024.1')[0])

    def test_xyz_periodic_cell_warning_and_restart_backup_warning(self):
        _, m = self.generate(run_type='CELL_OPT', periodic='XYZ', cell=(12., 12., 12.))
        self.assertTrue(any('XYZ trajectories' in w for w in m['warnings']))
        self.assertTrue(any('BACKUP_COPIES 0' in w for w in m['warnings']))

    def test_cli_case_insensitive_trajectory_and_project_restart_name(self):
        output = self.root/'different-output.inp'
        with redirect_stderr(io.StringIO()):
            code = main(['generate-input', str(self.source), '-o', str(output), '--periodic', 'NONE',
                         '--project', 'actual-project', '--run-type', 'GEO_OPT',
                         '--trajectory-format', 'extxyz', '--trust-radius', '0.15'])
        self.assertEqual(code, 0)
        text = output.read_text()
        self.assertIn('FORMAT EXTXYZ', text)
        self.assertIn('TRUST_RADIUS [angstrom] 0.15', text)
        self.assertIn('actual-project-RESTART.wfn', text)
        self.assertNotIn('different-output-RESTART.wfn', text)

    def test_config_and_replay_roundtrip_preserve_motion_settings(self):
        settings = replace(self.settings, run_type='GEO_OPT', trajectory_format='EXTXYZ', trust_radius=.17)
        text, m = generate_input(self.atom, settings)
        loaded = InputSettings.from_config(json.loads(json.dumps(m)))
        self.assertEqual(generate_input(self.atom, loaded)[0], text)
        parsed = build_parser().parse_args(command_arguments(self.source, -1, 'new.inp', settings)[3:])
        self.assertEqual(parsed.trajectory_format, 'EXTXYZ')
        self.assertEqual(parsed.trust_radius, .17)

    def test_main_menu_visibility_formats_and_radius_retention(self):
        output = self.root/'menu.inp'
        log = TTY()
        # Hidden -5 in ENERGY; select optimization/format/radius; hide radius for CG,
        # try selecting it (refused), then restore LBFGS and write.
        lines = '-5\n-1\nGEO_OPT\n-5\nextxyz\n133\n0.13\n10\nCG\n133\n10\nLBFGS\n0\ny\n\n'
        run_interactive(str(self.source), -1, str(output), replace(self.settings, write_json=True),
                        stdin=TTY(lines), stdout=log, plain=True)
        self.assertIn('Invalid menu number', log.getvalue())
        self.assertIn('-5. Trajectory format:', log.getvalue())
        self.assertIn('133. TRUST_RADIUS [angstrom]:', log.getvalue())
        m = json.loads(Path(str(output)+'.json').read_text())
        self.assertEqual(m['settings']['trajectory_format'], 'EXTXYZ')
        self.assertEqual(m['settings']['trust_radius'], .13)
        self.assertIn('&LBFGS\n      TRUST_RADIUS [angstrom] 0.13', output.read_text())

    def test_main_menu_format_numeric_choices(self):
        for number, fmt in ((1, 'PDB'), (2, 'XYZ'), (3, 'EXTXYZ')):
            output = self.root/f'format-{number}.inp'
            run_interactive(str(self.source), -1, str(output), replace(self.settings, run_type='GEO_OPT'),
                            stdin=TTY(f'-5\n{number}\n0\ny\n\n'), stdout=TTY(), plain=True)
            self.assertIn('FORMAT '+fmt+'\n', output.read_text())
