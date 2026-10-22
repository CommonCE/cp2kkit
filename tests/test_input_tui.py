"""Behavior-based scrolling menu regressions; never runs CP2K or Multiwfn."""
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import build_parser, main
from cp2kkit.errors import KitError
from cp2kkit.input_tui import GROUPS, Field, command_arguments, parse_value, run_interactive
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.main_tui import ACTIONS, run_main_menu, structure_summary
from cp2kkit.presentation import Presenter
from cp2kkit.structure import Structure, read_structure

FIXTURES = Path(__file__).parent / 'fixtures'
WRITE = '0\n\n'


class TTY(io.StringIO):
    def isatty(self):
        return True


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.path = self.dir/'water.xyz'
        self.path.write_text('3\nsynthetic water\nO 0 0 0\nH .76 0 .58\nH -.76 0 .58\n')
        self.output = self.dir/'water.inp'
        self.settings = InputSettings(periodic='NONE', write_json=True)

    def session(self, lines, **kwargs):
        log = TTY()
        code = run_interactive(str(self.path), -1, str(self.output), self.settings,
                               stdin=TTY(lines), stdout=log, plain=True, **kwargs)
        return code, log.getvalue()

    def manifest(self):
        return json.loads(Path(str(self.output)+'.json').read_text())

    def test_shared_field_schema_and_ranges(self):
        fields = [f for _, group in GROUPS for f in group]
        self.assertEqual(len(fields), len({f.name for f in fields}))
        self.assertEqual({f.name for f in fields}, set(InputSettings.__dataclass_fields__) | {'path', 'frame', 'output'})
        self.assertEqual(parse_value(Field('p', 'periodic', choices=('NONE', 'XYZ')), 'xyz'), 'XYZ')
        for f, raw in ((Field('a', 'a', 'int', minimum=1), '0'),
                       (Field('a', 'a', 'int3', minimum=1), '1 0 2'),
                       (Field('a', 'a', 'float', positive=True), 'nan'),
                       (Field('a', 'a', 'float', positive=True), 'inf'),
                       (Field('a', 'a', 'float', positive=True), '-1'),
                       (Field('a', 'a', 'float3'), '1 2'),
                       (Field('a', 'a', 'bool'), 'maybe'),
                       (Field('a', 'a'), 'bad\x00path')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_value(f, raw)
        self.assertIsNone(parse_value(Field('p', 'p', optional=True), 'auto'))
        self.assertFalse(parse_value(Field('b', 'b', 'bool'), '0'))
        self.assertEqual(parse_value(Field('a', 'a', 'float3'), '1.5 2 3'), (1.5, 2., 3.))

    def test_default_write_equals_batch_generator(self):
        code, log = self.session(WRITE)
        self.assertEqual(code, 0)
        text, expected = generate_input(read_structure(self.path), self.settings)
        self.assertEqual(self.output.read_text(), text)
        self.assertEqual(self.manifest(), json.loads(json.dumps(expected)))
        self.assertIn('Success:', log)
        self.assertIn('Success:', log)
        self.assertIn(str(self.output.resolve()), log)
        self.assertIn(str(Path(str(self.output)+'.json').resolve()), log)

    def test_compact_common_shortcuts_and_unexpanded_categories(self):
        from cp2kkit.input_editor import NUMBERED_FIELDS
        _, log = self.session('-10\n')
        self.assertNotIn('Step 1/', log)
        self.assertNotIn('Enter for next', log)
        rows = re.findall(r'^\s+(-?\d+)\. (.*)', log, re.M)
        self.assertEqual({int(number) for number, _ in rows},
                         {-10, 0, -7, -3, -1, 1, 2, 3, 4, 8, 100, 200, 300, 500, 600})
        self.assertNotIn('101. Total charge', log)
        self.assertNotIn('602. Charge-density', log)
        self.assertEqual({f.name for _, f in NUMBERED_FIELDS},
                         (set(InputSettings.__dataclass_fields__) | {'path', 'frame', 'output'}) - {
                             'custom_basis_name', 'custom_potential_name', 'hf_memory', 'hf_cutoff_radius', 'pbeh_fraction',
                             'admm_purification', 'aux_basis_files', 'fragment_a_indices',
                             'fragment_a_charge', 'fragment_a_multiplicity', 'fragment_b_charge', 'fragment_b_multiplicity'})
        self.assertIn('generator default', log)
        self.assertFalse(self.output.exists())

    def test_edit_task_method_charge_spin_and_density(self):
        lines = '-1\nGEO_OPT\n101\n1\n102\n2\n1\nBLYP\n603\ny\n605\n2 3 4\n'+WRITE
        self.assertEqual(self.session(lines)[0], 0)
        expected = replace(self.settings, run_type='GEO_OPT', functional='BLYP', charge=1,
                           multiplicity=2, spin_density=True, cube_stride=(2, 3, 4))
        self.assertEqual(self.output.read_text(), generate_input(read_structure(self.path), expected)[0])
        self.assertFalse(self.manifest()['runtime_validated'])

    def test_conflict_is_reported_after_edit_and_fix_is_explicit(self):
        _, log = self.session('603\ny\nw\n101\n1\n102\n2\n'+WRITE)
        self.assertIn('Spin density requires UKS', log)
        self.assertIn('Values retained; no automatic changes', log)
        self.assertEqual(self.manifest()['settings']['charge'], 1)
        self.assertEqual(self.manifest()['settings']['multiplicity'], 2)

    def test_unknown_periodicity_stays_unknown_until_selected(self):
        self.settings = InputSettings(write_json=True)
        _, log = self.session('w\n-7\nNONE\n'+WRITE)
        self.assertIn('Periodicity is unknown', log)
        self.assertEqual(self.manifest()['settings']['periodic'], 'NONE')

    def test_parameter_back_and_enter_keep_edits(self):
        _, log = self.session('-1\nGEO_OPT\n-1\nback\n-1\n\n'+WRITE)
        self.assertEqual(self.manifest()['settings']['run_type'], 'GEO_OPT')
        self.assertIn('[user edit]', log)

    def test_parameter_zero_is_not_navigation(self):
        self.settings = replace(self.settings, charge=1, multiplicity=2)
        self.session('101\n0\n102\n1\n'+WRITE)
        self.assertEqual(self.manifest()['settings']['charge'], 0)
        self.assertEqual(self.manifest()['settings']['multiplicity'], 1)

    def test_explicit_scf_conflict_is_not_silently_repaired(self):
        self.settings = replace(self.settings, kpoints=(2, 2, 2), smearing=300)
        _, log = self.session('w\n-10\n')
        self.assertIn('Non-Gamma kpoints require XYZ', log)
        self.assertIn('Fix the draft', log)
        self.assertFalse(self.output.exists())
        self.settings = replace(self.settings, cell=(20., 20., 20.))
        self.session('-7\nXYZ\n4\ndiag\n'+WRITE)
        actual = self.manifest()['settings']
        self.assertEqual(actual['kpoints'], [2, 2, 2])
        self.assertEqual(actual['smearing'], 300)
        self.assertEqual(actual['scf'], 'diag')
        self.assertEqual(actual['periodic'], 'XYZ')

    def test_hidden_conflicting_overrides_are_retained_until_explicitly_removed(self):
        self.settings = replace(self.settings, smearing=300, added_mos=30)
        # Hidden choices cannot be selected; switch to diag to remove the overrides.
        _, log = self.session('6\n341\n4\ndiag\n300\n6\nauto\n341\n0\n4\not\n0\n'+WRITE)
        self.assertGreaterEqual(log.count('Invalid menu number'), 2)
        self.assertIn('Smearing [K]: 300', log)
        self.assertIn('ADDED_MOS: 30', log)
        self.assertEqual(self.manifest()['settings']['scf'], 'ot')
        self.assertIsNone(self.manifest()['settings']['smearing'])
        self.assertEqual(self.manifest()['settings']['added_mos'], 0)

    def test_field_numbers_stay_fixed_after_task_and_scf_changes(self):
        _, log = self.session('300\n-1\nCELL_OPT\n4\ndiag\n0\n400\n0\n-10\n')
        displays = log.split('=== 300. Numerical accuracy and SCF ===')[1:]
        self.assertEqual(len(displays), 3)
        for index, display in enumerate(displays):
            display = display.split('===')[0]
            self.assertIn('301. CUTOFF [Ry]:', display)
            self.assertEqual('324. ALGORITHM:' in display, index < 2)
            self.assertEqual('322. Maximum outer SCF steps:' in display, index < 2)
            self.assertEqual('341. ADDED_MOS:' in display, index == 2)
        self.assertIn('420. Fixed atoms:', log)
        self.assertIn('430. CELL_OPT pressure [bar]:', log)

    def test_conditional_fields_follow_task_pbc_and_scf(self):
        for task in ('ENERGY', 'GEO_OPT', 'CELL_OPT'):
            for periodic in (None, 'NONE', 'XYZ', 'XY'):
                for scf in ('ot', 'diag'):
                    with self.subTest(task=task, periodic=periodic, scf=scf):
                        self.settings = InputSettings(run_type=task, periodic=periodic, scf=scf, write_json=True)
                        _, log = self.session('200\n300\n0\n-10\n')
                        self.assertEqual('12. CELL_OPT pressure' in log, task == 'CELL_OPT')
                        self.assertEqual('212. Isolated box padding' in log, periodic == 'NONE')
                        self.assertEqual('6. Smearing' in log, scf == 'diag')
                        self.assertEqual('341. ADDED_MOS' in log, scf == 'diag')
                        self.assertEqual('322. Maximum outer SCF' in log, scf == 'ot')
        # Auto inherits actual source PBC, rather than assuming NONE for a missing cell.
        for periodic, padding in ((None, False), ('NONE', True)):
            log = TTY()
            run_interactive(str(FIXTURES/'water.restart'), -1, str(self.output),
                            InputSettings(periodic=periodic), stdin=TTY('200\n0\n-10\n'), stdout=log, plain=True)
            self.assertEqual('212. Isolated box padding' in log.getvalue(), padding)
        # Applicability updates in the same session; inactive values are not reset.
        _, log = self.session('200\n211\nNONE\n211\nXYZ\n211\nNONE\n0\n-10\n')
        displays = log.split('=== 200. Structure, boundary and basis ===')[1:]
        self.assertEqual(['212. Isolated box padding' in d for d in displays], [False, True, False, True])

    def test_review_omits_ot_only_inapplicable_occupations(self):
        _, log = self.session('r\n\n-10\n')
        self.assertNotIn('Smearing', log)
        self.assertNotIn('ADDED_MOS', log)
        self.assertNotIn('CELL_OPT pressure', log)
        self.settings = replace(self.settings, scf='diag', smearing=300)
        _, log = self.session('r\n\n-10\n')
        self.assertIn('Smearing: 300 K', log)
        self.assertIn('ADDED_MOS=30 (auto)', log)

    def test_optional_auto_and_diag_smearing_defaults(self):
        self.settings = replace(self.settings, scf='diag', eps_scf=1e-8, smearing=300)
        self.session('303\nauto\n6\nauto\n'+WRITE)
        self.assertIsNone(self.manifest()['settings']['eps_scf'])
        self.assertIsNone(self.manifest()['settings']['smearing'])

    def test_bad_local_values_retry(self):
        _, log = self.session('99\n300\n301\nnan\n-5\n450\n0\n-10\n')
        self.assertGreaterEqual(log.count('Invalid'), 3)
        self.assertIn('450.0', log)
        self.assertFalse(self.output.exists())

    def test_preview_review_cancel_and_decline_never_write(self):
        with patch('cp2kkit.input_editor.write_input') as writer:
            _, log = self.session('p\n\nr\n\nw\n\n-10\n')
        writer.assert_not_called()
        self.assertIn('&FORCE_EVAL', log)
        self.assertIn('Reproducible command', log)
        self.assertIn('Not confirmed', log)
        self.assertIn('Cancelled', log)
        self.assertEqual(list(self.dir.iterdir()), [self.path])

    def test_json_or_non_inp_collision_recoverable_by_changing_path(self):
        self.output = self.dir/'protected.out'
        for target in (self.output, Path(str(self.output)+'.json')):
            with self.subTest(target=target):
                target.write_text('existing user data')
                alternate = self.dir/(target.name+'.new.inp')
                _, log = self.session(f'w\ny\n{alternate}\n'+WRITE)
                self.assertIn('Refusing to overwrite', log)
                self.assertEqual(target.read_text(), 'existing user data')
                self.assertTrue(alternate.exists())
                if target != self.output:
                    self.assertFalse(self.output.exists())
                target.unlink()

    def test_cancel_eof_and_interrupt_are_clean(self):
        for lines in ('', 'q\n', 'cancel\n', '-10\n', 'back\n', 'w\nq\n', 'w\ncancel\n'):
            self.assertEqual(self.session(lines)[0], 0)
            self.assertFalse(self.output.exists())
        with patch.object(TTY, 'readline', side_effect=KeyboardInterrupt):
            self.assertEqual(self.session('')[0], 0)
        with patch('cp2kkit.inputgen.json_text', side_effect=KeyboardInterrupt):
            self.assertEqual(self.session('w\ny\n')[0], 0)
        self.assertFalse(self.output.exists())
        self.assertFalse(Path(str(self.output)+'.json').exists())

    def test_source_header_and_direct_only_setting_rows(self):
        from cp2kkit.input_editor import NUMBERED_FIELDS
        _, log = self.session('-10\n')
        names = {f.name for _, f in NUMBERED_FIELDS}
        self.assertTrue({'path', 'frame', 'output', 'project', 'cp2k_version'} <= names)
        self.assertNotIn('502. Input output path:', log)
        self.assertNotIn('503. PROJECT name:', log)
        self.assertIn(f'Structure: {self.path}; frame: -1', log)
        self.assertNotIn('Project name:', log)
        self.assertNotIn('Target CP2K version:', log)
        self.assertNotIn('New input path (+ .json):', log)

    def test_missing_source_uses_header_control_and_default_output(self):
        log = TTY()
        with patch('pathlib.Path.cwd', return_value=self.dir):
            code = run_interactive(None, -1, None, self.settings,
                                   stdin=TTY('w\n-10\n'), stdout=log, plain=True)
        self.assertEqual(code, 0)
        self.assertIn('use s to load a structure', ' '.join(log.getvalue().split()))
        self.assertIn('No structure loaded', log.getvalue())

    def test_source_and_frame_edits_preserve_previous_on_failure(self):
        _, log = self.session('s\nmissing.xyz\nf\n99\ns\nback\n-10\n')
        self.assertIn('Previous source retained', log)
        self.assertIn(f'Structure: {self.path}; frame: -1', log)

    def test_common_aliases_and_new_full_function_ids(self):
        from cp2kkit.menu_registry import BY_TOKEN
        expected = {-7: 'periodic', -5: 'trajectory_format', -3: 'electron_density', -1: 'run_type',
                    1: 'functional', 2: 'basis', 3: 'dispersion', 4: 'scf', 6: 'smearing',
                    8: 'kpoints', 9: 'fixed_atoms', 10: 'optimizer', 12: 'pressure',
                    101: 'charge', 102: 'multiplicity', 112: 'dft_plus_u', 324: 'ot_algorithm', 341: 'added_mos'}
        for number, name in expected.items():
            self.assertEqual(BY_TOKEN[str(number)].field, name)
        for old in ('105', '124', '125', '126', '128', '132', '133'):
            self.assertNotIn(old, BY_TOKEN)
        _, log = self.session('w\n\n-10\n')
        self.assertIn('Not confirmed', log)
        self.assertFalse(self.output.exists())

    def test_main_zero_writes_without_confirmation_or_review(self):
        _, log = self.session('0\n\n')
        self.assertTrue(self.output.exists())
        self.assertNotIn('? [y/N]', log)
        self.assertNotIn('Sidecar path:', log)
        self.assertNotIn('Enter to return to the menu; q exits:', log)
        self.assertIn('Success:', log)

    def test_direct_zero_and_review_write_generate_identical_input(self):
        self.session('0\n\n')
        direct = self.output.read_text()
        self.settings = replace(self.settings, write_json=False)
        _, log = self.session('w\ny\n\n')
        self.assertEqual(self.output.read_text(), direct)
        self.assertIn('? [y/N]', log)

    def test_automatic_spin_display_and_manual_override(self):
        self.path.write_text('1\nneutral radical\nH 0 0 0\n')
        _, log = self.session('100\n0\n0\n\n')
        self.assertIn('2 (auto: electron parity)', log)
        self.assertEqual(self.manifest()['settings']['multiplicity'], 2)
        self.settings = replace(self.settings, write_json=False)
        _, log = self.session('102\n2\n102\nauto\n100\n0\n0\n\n')
        self.assertIn('MULTIPLICITY 2', self.output.read_text())
        self.assertIn('auto: electron parity', log)

    def test_nonterminal_stdin_or_stdout_refuses_without_reading(self):
        for stdin, stdout in ((io.StringIO(), TTY()), (TTY(), io.StringIO())):
            with patch.object(stdin, 'readline') as reader, self.assertRaises(KitError) as cm:
                run_interactive(str(self.path), -1, str(self.output), self.settings, stdin=stdin, stdout=stdout)
            self.assertEqual(cm.exception.code, 2)
            reader.assert_not_called()

    def test_replay_command_spaces_optional_values_and_all_fields(self):
        settings = replace(self.settings, scf='diag', charge=1, multiplicity=2, electron_density=True,
                           spin_density=True, cube_stride=(1, 2, 3), smearing=200, eps_scf=1e-7,
                           cell=(18., 19., 20.), dispersion='d3bj')
        argv = command_arguments(self.dir/'structure with spaces.xyz', 0, '-output with spaces.inp', settings)
        self.assertEqual(shlex.split(shlex.join(argv)), argv)
        args = build_parser().parse_args(argv[3:])
        for name, value in settings.__dict__.items():
            actual = getattr(args, name)
            self.assertEqual(tuple(actual) if isinstance(value, tuple) else actual, value, name)
        self.assertFalse(args.interactive)


class ApplicationTests(unittest.TestCase):
    setUp = MenuTests.setUp
    def app(self, lines, path=None):
        log = TTY()
        return run_main_menu(path, stdin=TTY(lines), stdout=log, plain=True), log.getvalue()

    def test_stable_actions_grouped_continuous_numbers(self):
        self.assertEqual(len(ACTIONS), len({a.id for a in ACTIONS}))
        _, log = self.app('0\n')
        for number, action in enumerate(ACTIONS, 1):
            self.assertIn(f'{number}. {action.label}', log)
        self.assertIn('Requires a structure', log)
        self.assertIn('Select [0-7]', log)
        self.assertIn('No structure loaded', log)

    def test_summary_hill_formula_and_triclinic_angles(self):
        structure = Structure(['O', 'H', 'H'], [[0., 0., 0.]]*3,
                              [[4., 0., 0.], [2., 3.464101615, 0.], [0., 0., 6.]], [True, True, False], {})
        summary = dict(structure_summary(structure, '/long/path/water.extxyz'))
        self.assertEqual(summary['Formula'], 'H2O')
        self.assertEqual(summary['File'], 'water.extxyz')
        self.assertEqual(summary['Periodicity'], 'XY')
        self.assertIn('60.000', summary['Angles [degrees]'])
        unknown = dict(structure_summary(read_structure(self.path), self.path))
        self.assertEqual(unknown['Periodicity'], 'Unknown')
        self.assertEqual(unknown['Cell lengths [angstrom]'], 'Unknown')
        carbon = replace(structure, symbols=['H', 'O', 'C', 'H'])
        self.assertEqual(dict(structure_summary(carbon, 'x'))['Formula'], 'CH2O')

    def test_failed_replacement_keeps_previous_structure(self):
        _, log = self.app('1\nmissing.xyz\nback\n0\n', str(self.path))
        self.assertIn('Previous structure retained', log)
        self.assertGreaterEqual(log.count('Formula: H2O'), 2)

    def test_structure_dependent_action_loads_and_resumes(self):
        _, log = self.app(f'2\n{self.path}\n\n0\n')
        self.assertIn('Full path:', log)
        self.assertIn('Success: Structure loaded', log)

    def test_analysis_without_structure_summary_then_details(self):
        _, log = self.app(f'5\n{FIXTURES/"truncated.out"}\nd\n\n0\n')
        self.assertIn('Success: Output parsed', log)
        self.assertIn('Warning: Text quality status: not_passed', log)
        self.assertIn('Missing normal-termination', log)
        self.assertIn('"schema_version"', log)
        self.assertIn('No structure loaded', log)

    def test_cube_check_without_structure(self):
        cube = self.dir/'unknown.cube'
        cube.write_text('unknown\nscalar\n0 0 0 0\n1 1 0 0\n1 0 1 0\n1 0 0 1\n2\n')
        _, log = self.app(f'6\n{cube}\n\n\n0\n')
        self.assertIn('Success: Scalar CUBE', log)
        self.assertIn('raw_numerical_integral', log)
        self.assertIn('not electron count', log)

    def test_cube_meaning_and_units_can_be_asserted_explicitly(self):
        cube = self.dir/'generic.cube'
        cube.write_text('unknown\nscalar\n0 0 0 0\n1 1 0 0\n1 0 1 0\n1 0 0 1\n2\n')
        _, log = self.app(f'6\n{cube}\na\n\nbohr\nelectron-density\ne/bohr^3\n\n0\n')
        self.assertIn('scalar_type: electron-density', log)
        self.assertIn('electron_number', log)

    def test_export_collision_and_success_preserve_source(self):
        old_source = self.path.read_bytes()
        out = self.dir/'water.extxyz'
        out.write_text('existing')
        _, log = self.app(f'3\n{out}\n\n0\n', str(self.path))
        self.assertIn('Refusing to overwrite', log)
        self.assertEqual(out.read_text(), 'existing')
        new = self.dir/'new.extxyz'
        _, log = self.app(f'3\n{new}\n\n0\n', str(self.path))
        self.assertIn(str(new.resolve()), log)
        self.assertTrue(Path(str(new)+'.json').exists())
        self.assertEqual(self.path.read_bytes(), old_source)

    def test_cube_difference_and_cancellation_are_non_destructive(self):
        first, fragment, out = (self.dir/n for n in ('ab.cube', 'a.cube', 'diff.cube'))
        header = '-Quickstep-\nELECTRON DENSITY\n0 0 0 0\n1 1 0 0\n1 0 1 0\n1 0 0 1\n'
        first.write_text(header+'2\n')
        fragment.write_text(header+'1\n')
        _, log = self.app(f'7\n{first}\n0\n0\n')
        self.assertIn('Cancelled', log)
        self.assertFalse(out.exists())
        _, log = self.app(f'7\n{first}\n{fragment}\n\n{out}\n\n\n0\n')
        self.assertTrue(out.exists(), log)
        self.assertTrue(Path(str(out)+'.json').exists())
        self.assertIn('not fragment net charge transfer', ' '.join(log.split()))
        self.assertIn(str(out.resolve()), log)
        data = out.read_bytes()
        _, log = self.app(f'7\n{first}\n{fragment}\n\n{out}\n\n\n0\n')
        self.assertIn('Refusing to overwrite', log)
        self.assertEqual(out.read_bytes(), data)

    def test_q_in_submenu_exits_session_not_main(self):
        _, log = self.app('4\nq\n0\n', str(self.path))
        self.assertEqual(log.count('cp2kkit Main menu'), 1)
        _, log = self.app('2\nq\n', str(self.path))
        self.assertEqual(log.count('cp2kkit Main menu'), 1)

    def test_cancel_operation_and_ctrl_c_main(self):
        _, log = self.app('4\ncancel\n0\n', str(self.path))
        self.assertGreaterEqual(log.count('cp2kkit Main menu'), 2)
        with patch.object(TTY, 'readline', side_effect=["1\n", KeyboardInterrupt(), "0\n"]):
            _, log = self.app('')
        self.assertIn('Cancelled; returning', log)
        with patch.object(TTY, 'readline', side_effect=KeyboardInterrupt):
            self.assertEqual(self.app('')[0], 0)
        with patch.object(TTY, 'readline', side_effect=['5\n', 'missing.out\n', KeyboardInterrupt(), '0\n']):
            _, log = self.app('')
        self.assertGreaterEqual(log.count('cp2kkit Main menu'), 2)
        with patch('cp2kkit.main_tui.read_structure', side_effect=KeyboardInterrupt):
            _, log = self.app('0\n', str(self.path))
        self.assertIn('Cancelled initial load', log)


class CLIInteractiveTests(unittest.TestCase):
    def call(self, args, lines, tty=True):
        log, error = TTY(), io.StringIO()
        with patch('sys.stdin', TTY(lines) if tty else io.StringIO(lines)), redirect_stdout(log), redirect_stderr(error):
            code = main(args)
        return code, log.getvalue(), error.getvalue()

    def test_cli_seed_and_plain_before_or_after_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i, plain in enumerate((['--plain', 'generate-input'], ['generate-input', '--plain'])):
                out = Path(tmp)/f'seed{i}.inp'
                code, log, error = self.call([*plain, str(FIXTURES/'trajectory.xyz'), '--write-json', '--tui', '-o', str(out),
                                             '--periodic', 'NONE', '--run-type', 'GEO_OPT',
                                             '--project', 'custom', '--cp2k-version', '2024.1'], WRITE)
                self.assertEqual(code, 0, error)
                manifest = json.loads(Path(str(out)+'.json').read_text())
                self.assertEqual(manifest['settings']['run_type'], 'GEO_OPT')
                self.assertEqual(manifest['settings']['project'], 'custom')
                self.assertEqual(manifest['target_version'], '2024.1')
                self.assertNotIn('Project name:', log)
                self.assertNotIn('Target CP2K version:', log)
                self.assertNotIn('New input path (+ .json):', log)
                self.assertNotIn('\x1b', log)

    def test_bare_generate_loads_source_and_defaults_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'trajectory.inp'
            source = (FIXTURES/'trajectory.xyz').resolve()
            lines = f's\n{source}\nf\n0\n-7\nNONE\n'+WRITE
            previous = Path.cwd()
            try:
                os.chdir(tmp)
                code, _, error = self.call(['generate-input', '--plain', '--write-json'], lines)
            finally:
                os.chdir(previous)
            self.assertEqual(code, 0, error)
            self.assertTrue(out.exists())
            manifest = json.loads(Path(str(out)+'.json').read_text())
            self.assertEqual(manifest['source_structure']['frame'], 0)
            self.assertEqual(manifest['settings']['project'], 'trajectory')

    def test_batch_stays_noninteractive_and_json_unchanged(self):
        with patch('cp2kkit.input_tui.run_interactive') as menu:
            code, log, _ = self.call(['report', str(FIXTURES/'normal.out')], '')
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(log)['status'], 'passed')
            menu.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'batch.inp'
            with patch('cp2kkit.input_tui.run_interactive') as menu:
                code, log, _ = self.call(['generate-input', str(FIXTURES/'trajectory.xyz'), '-o', str(out), '--periodic', 'NONE'], '')
                self.assertEqual(code, 0)
                self.assertEqual(log, '')
                menu.assert_not_called()

    def test_nonterminal_subprocesses_never_wait_for_menu(self):
        for args in ([], ['--plain'], ['generate-input', '--tui'], ['generate-input', str(FIXTURES/'trajectory.xyz'), '--tui']):
            result = subprocess.run([sys.executable, '-m', 'cp2kkit', *args], input='', capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn('TTY', result.stderr)
            self.assertNotIn('Select [', result.stdout)
        p = subprocess.run([sys.executable, '-m', 'cp2kkit', 'parse', str(FIXTURES/'normal.out'), '--format', 'csv'], capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 0)
        self.assertNotIn('\x1b', p.stdout)
        self.assertIn('hartree', p.stdout)

    @unittest.skipUnless(os.name == 'posix', 'PTY smoke requires POSIX')
    def test_real_pty_session_generation_and_return(self):
        import pty
        import select
        import time
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'pty.inp'
            master, slave = pty.openpty()
            try:
                with subprocess.Popen([sys.executable, '-m', 'cp2kkit', 'generate-input',
                                       str(FIXTURES/'trajectory.xyz'), '--plain', '--tui',
                                       '--periodic', 'NONE', '-o', str(out)], stdin=slave, stdout=slave, stderr=slave) as proc:
                    os.close(slave)
                    slave = None
                    os.write(master, ('p\n\n'+WRITE).encode())
                    data = b''
                    deadline = time.monotonic()+15
                    try:
                        while time.monotonic() < deadline:
                            if select.select([master], [], [], .1)[0]:
                                try:
                                    chunk = os.read(master, 65536)
                                except OSError:
                                    break
                                if not chunk:
                                    break
                                data += chunk
                            elif proc.poll() is not None:
                                break
                        proc.wait(timeout=1)
                    except BaseException:
                        proc.kill()
                        proc.wait()
                        raise
                    self.assertEqual(proc.returncode, 0, data.decode())
                    self.assertIn('Input preview', data.decode())
                    self.assertEqual(out.read_text(), generate_input(read_structure(FIXTURES/'trajectory.xyz'), InputSettings(periodic='NONE'))[0])
            finally:
                os.close(master)
                if slave is not None:
                    os.close(slave)


class PresentationTests(unittest.TestCase):
    def test_plain_no_color_and_missing_rich_have_no_escape_sequences(self):
        for plain, env in ((True, {}), (False, {'NO_COLOR': ''})):
            with patch.dict(os.environ, env, clear=True):
                stream = TTY()
                presenter = Presenter(stream, plain=plain, width=40)
                presenter.heading('Success: heading')
                presenter.show('Warning: literal [brackets] and /very/long/path/'+'x'*70)
                self.assertNotIn('\x1b', stream.getvalue())
                self.assertIn('[brackets]', stream.getvalue())
                self.assertTrue(all(len(line) <= 40 for line in stream.getvalue().splitlines()))
        with patch.dict(sys.modules, {'rich.console': None}), patch.dict(os.environ, {}, clear=True):
            stream = TTY()
            Presenter(stream).show('Success: fallback')
            self.assertEqual(stream.getvalue(), 'Success: fallback\n')

    def test_main_and_review_fold_on_narrow_terminal(self):
        with patch('cp2kkit.presentation.shutil.get_terminal_size', return_value=os.terminal_size((40, 24))):
            log = TTY()
            run_main_menu(str(FIXTURES/'trajectory.xyz'), stdin=TTY('0\n'), stdout=log, plain=True)
            # Prompts have no newline, so compare render-only lines separately.
            rendered = log.getvalue().split('Select [0-7]:')[0]
            self.assertTrue(all(len(line) <= 40 for line in rendered.splitlines()))
            self.assertIn('Unknown', rendered)
            log = TTY()
            from cp2kkit.input_tui import Menu
            from dataclasses import asdict
            values = {**asdict(InputSettings(periodic='NONE', write_json=True)), 'path': str(FIXTURES/'trajectory.xyz'),
                      'frame': -1, 'output': '/tmp/very-long-output-name-that-wraps-over-the-terminal.inp'}
            Menu(TTY(), log, plain=True).review(values)
            self.assertTrue(all(len(line) <= 40 for line in log.getvalue().splitlines()))
            self.assertIn('Warning:', log.getvalue())
            self.assertIn('Sidecar path:', log.getvalue())

    def test_rich_narrow_and_markup_literal(self):
        with patch.dict(os.environ, {}, clear=True):
            stream = TTY()
            presenter = Presenter(stream, width=32)
            presenter.show('Warning: [red] literal path /'+'x'*80)
            self.assertIn('[red]', stream.getvalue())
            visible = re.sub(r'\x1b\[[0-9;]*m', '', stream.getvalue())
            self.assertTrue(all(len(line) <= 32 for line in visible.splitlines()))
            self.assertNotIn('\x1b[2J', stream.getvalue())
            self.assertNotIn('\x1b[?1049', stream.getvalue())


if __name__ == '__main__':
    unittest.main()
