"""Tests for cp2kkit-viewer discovery, CLI/TUI integration, and temp-file cleanup."""
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import main
from cp2kkit.errors import KitError, MissingDependency
from cp2kkit.input_editor import run_editor
from cp2kkit.inputgen import InputSettings
from cp2kkit.main_tui import run_main_menu
from cp2kkit.viewer import (
    VIEWER_ENV_VAR,
    find_viewer_executable,
    launch_viewer,
    view_input_draft,
    view_vibration_scene,
)
from tests.test_cube import synthetic_cube
from tests.test_interface_operations import TTY

ROOT = Path(__file__).resolve().parents[1]
MOLECULAR_VIB = ROOT / 'examples' / 'vibration-results' / 'molecular.txt'


def _make_mock_viewer(directory: Path, log_path: Path, *, exit_code: int = 0, stderr_msg: str = '') -> Path:
    """Create a tiny Python mock viewer that records argv and inspected input bytes."""
    script = directory / 'mock-viewer'
    script.write_text(
        f'#!{sys.executable}\n'
        'import json, sys\n'
        'from pathlib import Path\n'
        f'log = Path({str(log_path)!r})\n'
        'args = sys.argv[1:]\n'
        'snapshot = None\n'
        'if args and not args[0].startswith("-") and Path(args[0]).is_file():\n'
        '    snapshot = Path(args[0]).read_text(encoding="utf-8", errors="replace")\n'
        'record = {"args": args, "snapshot": snapshot}\n'
        'with log.open("a", encoding="utf-8") as fh:\n'
        '    fh.write(json.dumps(record) + "\\n")\n'
        f'if {stderr_msg!r}:\n'
        f'    sys.stderr.write({stderr_msg!r} + "\\n")\n'
        f'sys.exit({exit_code})\n',
        encoding='utf-8',
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _read_invocations(log_path: Path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding='utf-8').splitlines() if line.strip()]


class ViewerModuleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.log = self.root / 'invocations.jsonl'
        self.mock_viewer = _make_mock_viewer(self.root, self.log)

    def test_executable_discovery_precedence_and_errors(self):
        self.assertEqual(find_viewer_executable(self.mock_viewer), self.mock_viewer.resolve())
        with self.assertRaises(KitError):
            find_viewer_executable(self.root / 'missing-viewer')

        with patch.dict(os.environ, {VIEWER_ENV_VAR: str(self.mock_viewer)}):
            self.assertEqual(find_viewer_executable(), self.mock_viewer.resolve())
        with patch.dict(os.environ, {VIEWER_ENV_VAR: str(self.root / 'bad-env')}):
            with self.assertRaises(KitError):
                find_viewer_executable()

        with patch.dict(os.environ, {VIEWER_ENV_VAR: ''}, clear=False), \
             patch('cp2kkit.viewer._env_viewer_candidates', return_value=(self.mock_viewer,)), \
             patch('cp2kkit.viewer.shutil.which', return_value=None):
            self.assertEqual(find_viewer_executable(), self.mock_viewer.resolve())

        with patch.dict(os.environ, {VIEWER_ENV_VAR: ''}, clear=False), \
             patch('cp2kkit.viewer.shutil.which', return_value=None), \
             patch('cp2kkit.viewer._env_viewer_candidates', return_value=(self.root / 'nope',)):
            with self.assertRaises(MissingDependency) as ctx:
                find_viewer_executable()
            self.assertEqual(ctx.exception.code, 6)

    def test_display_guard_and_nonzero_exit_error(self):
        with patch.dict(os.environ, {'DISPLAY': ''}, clear=False):
            with self.assertRaises(KitError) as ctx:
                launch_viewer(executable=self.mock_viewer)
            self.assertIn('DISPLAY', str(ctx.exception))
            # --version does not require an X11 display.
            self.assertEqual(launch_viewer(viewer_args=('--version',), executable=self.mock_viewer), 0)

        failing = _make_mock_viewer(self.root, self.root / 'fail.jsonl', exit_code=1, stderr_msg='bad cube header')
        with patch.dict(os.environ, {'DISPLAY': ':0'}, clear=False):
            with self.assertRaises(KitError) as ctx:
                launch_viewer(executable=failing)
            self.assertIn('bad cube header', str(ctx.exception))

    def test_temp_scene_and_draft_staging_and_cleanup(self):
        scene = {'schema': 'cp2kkit-viewer-scene-v1', 'title': 'demo', 'atoms': [], 'modes': []}
        with patch.dict(os.environ, {'DISPLAY': ':0'}, clear=False):
            self.assertEqual(view_vibration_scene(scene, executable=self.mock_viewer), 0)
            self.assertEqual(view_input_draft('&GLOBAL\n  PROJECT demo\n&END GLOBAL\n',
                                              stem='water', executable=self.mock_viewer), 0)
        calls = _read_invocations(self.log)
        self.assertEqual(len(calls), 2)
        scene_path = Path(calls[0]['args'][0])
        draft_path = Path(calls[1]['args'][0])
        self.assertEqual(json.loads(calls[0]['snapshot'])['schema'], 'cp2kkit-viewer-scene-v1')
        self.assertIn('PROJECT demo', calls[1]['snapshot'])
        self.assertEqual(draft_path.name, 'water.inp')
        self.assertFalse(scene_path.exists())
        self.assertFalse(scene_path.parent.exists())
        self.assertFalse(draft_path.exists())
        self.assertFalse(draft_path.parent.exists())


class ViewerCLITests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.log = self.root / 'cli.jsonl'
        self.mock_viewer = _make_mock_viewer(self.root, self.log)
        self.co2_xyz = self.root / 'co2.xyz'
        self.co2_xyz.write_text(
            '3\nco2\n'
            'O 0.0 0.0 -1.16\n'
            'C 0.0 0.0  0.00\n'
            'O 0.0 0.0  1.16\n',
            encoding='utf-8',
        )
        self.cube_ab = self.root / 'ab.cube'
        self.cube_a = self.root / 'a.cube'
        self.cube_pot = self.root / 'pot.cube'
        self.cube_ab.write_text(synthetic_cube([2, 3, 4, 5]), encoding='utf-8')
        self.cube_a.write_text(synthetic_cube([1, 2, 5, 4]), encoding='utf-8')
        self.cube_pot.write_text(synthetic_cube([0.1, -0.2, 0.3, -0.4]), encoding='utf-8')

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'DISPLAY': ':0'}, clear=False), \
             redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_view_subcommand_forwards_flags(self):
        code, _, err = self.run_cli([
            'view', str(self.cube_ab),
            '--viewer', str(self.mock_viewer),
            '--color-cube', str(self.cube_pot),
            '--colormap', 'rwb',
            '--flip-color-sign',
            '--iso', '0.002',
            '--iso-sign', 'both',
            '--cube-length-unit', 'bohr',
            '--fixed', '1-2',
            '--no-bond', 'Ga-Ga',
            '--dark',
            '--arrows',
        ])
        self.assertEqual(code, 0, err)
        args = _read_invocations(self.log)[0]['args']
        self.assertEqual(args[0], str(self.cube_ab))
        for flag in ('--color-cube', '--colormap', 'rwb', '--flip-color-sign',
                     '--iso', '0.002', '--iso-sign', 'both', '--cube-length-unit', 'bohr', '--fixed', '1-2',
                     '--no-bond', 'Ga-Ga', '--dark', '--arrows'):
            self.assertIn(flag, args)

    def test_view_accepts_negative_boundary_in_both_forms(self):
        boundary = '-0.05:1.05,-0.05:1.05,-0.1:0.4'
        for flags in (['--boundary', boundary], [f'--boundary={boundary}']):
            code, _, err = self.run_cli([
                '--plain', 'view', str(self.co2_xyz), '--viewer', str(self.mock_viewer), *flags,
            ])
            self.assertEqual(code, 0, err)
        self.assertEqual([call['args'] for call in _read_invocations(self.log)],
                         [[str(self.co2_xyz), '--boundary', boundary]] * 2)

    def test_cube_diff_and_cube_check_view_flags(self):
        diff_out = self.root / 'diff.cube'
        code, _, err = self.run_cli([
            'cube-diff', str(self.cube_ab), str(self.cube_a),
            '-o', str(diff_out), '--view', '--viewer', str(self.mock_viewer),
        ])
        self.assertEqual(code, 0, err)
        self.assertTrue(diff_out.is_file())
        calls = _read_invocations(self.log)
        self.assertEqual(calls[0]['args'], [str(diff_out), '--cube-length-unit', 'bohr', '--iso-sign', 'both'])

        code, out, err = self.run_cli([
            'cube-check', str(self.cube_ab), '--view', '--viewer', str(self.mock_viewer),
            '--color-cube', str(self.cube_pot), '--flip-color-sign', '--colormap', 'coolwarm',
        ])
        self.assertEqual(code, 0, err)
        self.assertIn('"statistics"', out)
        calls = _read_invocations(self.log)
        self.assertEqual(calls[1]['args'], [
            str(self.cube_ab), '--cube-length-unit', 'bohr', '--color-cube', str(self.cube_pot),
            '--flip-color-sign', '--colormap', 'coolwarm',
        ])

        # Reject view-only flags when --view is omitted.
        code, _, err = self.run_cli(['cube-check', str(self.cube_ab), '--colormap', 'rwb'])
        self.assertEqual(code, 2)
        self.assertIn('--view', err)

    def test_cube_writer_and_rust_reader_share_angstrom_fixture(self):
        grid = '1 0 0 0\n2 1 0 0\n2 0 1 0\n2 0 0 1\n1 0 0.25 0.5 0.75\n'
        source = 'synthetic CUBE\nindependent scalar field\n' + grid
        self.cube_ab.write_text(source + '0 0 0 0 1 1 1 1\n', encoding='utf-8')
        self.cube_a.write_text(source + '0 0 0 0 0 0 0 0\n', encoding='utf-8')
        diff_out = self.root / 'angstrom.cube'
        viewer = ['--view', '--viewer', str(self.mock_viewer)]
        code, _, err = self.run_cli([
            'cube-diff', str(self.cube_ab), str(self.cube_a), '-o', str(diff_out),
            '--length-unit', 'angstrom', '--scalar-type', 'electron-density',
            '--scalar-unit', 'e/angstrom^3', *viewer,
        ])
        self.assertEqual(code, 0, err)
        fixture = ROOT / 'tests' / 'fixtures' / 'cp2kkit-diff-angstrom.cube'
        self.assertEqual(diff_out.read_text(encoding='utf-8').strip(), fixture.read_text(encoding='utf-8').strip())
        code, out, err = self.run_cli(['cube-check', str(self.cube_ab), '--length-unit', 'angstrom', *viewer])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)['length_unit'], 'angstrom')
        self.assertEqual([call['args'] for call in _read_invocations(self.log)], [
            [str(diff_out), '--cube-length-unit', 'angstrom', '--iso-sign', 'both'],
            [str(self.cube_ab), '--cube-length-unit', 'angstrom'],
        ])

        signed = self.root / 'unsigned-units.cube'
        signed.write_text(source.replace('\n2 ', '\n-2 ') + '0 0 0 0 1 1 1 1\n', encoding='utf-8')
        code, out, err = self.run_cli(['cube-check', str(signed), *viewer])
        self.assertEqual(code, 2, err)
        self.assertIsNone(json.loads(out)['length_unit'])
        self.assertIn('unknown spatial unit', err)
        self.assertEqual(len(_read_invocations(self.log)), 2)

    def test_vibration_export_structure_and_generate_input_view_flags(self):
        # 1) vibration default json + --view -> temp scene staged & cleaned
        code, out, err = self.run_cli([
            'vibration', str(MOLECULAR_VIB),
            '--geometry', str(self.co2_xyz), '--view', '--viewer', str(self.mock_viewer),
        ])
        self.assertEqual(code, 0, err)
        self.assertIn('"modes"', out)
        vib_call = _read_invocations(self.log)[0]
        self.assertEqual(json.loads(vib_call['snapshot'])['schema'], 'cp2kkit-viewer-scene-v1')
        self.assertFalse(Path(vib_call['args'][0]).exists())

        # 2) vibration viewer-scene -o scene.json --view -> opens written file directly
        scene_out = self.root / 'co2-vib.json'
        code, _, err = self.run_cli([
            'vibration', str(MOLECULAR_VIB), '--geometry', str(self.co2_xyz),
            '--format', 'viewer-scene', '-o', str(scene_out),
            '--view', '--viewer', str(self.mock_viewer),
        ])
        self.assertEqual(code, 0, err)
        self.assertTrue(scene_out.is_file())
        self.assertEqual(_read_invocations(self.log)[1]['args'], [str(scene_out)])

        # 3) export-structure --view
        exported = self.root / 'co2.extxyz'
        code, _, err = self.run_cli([
            'export-structure', str(self.co2_xyz), '-o', str(exported),
            '--view', '--viewer', str(self.mock_viewer),
        ])
        self.assertEqual(code, 0, err)
        self.assertEqual(_read_invocations(self.log)[2]['args'], [str(exported)])

        # 4) generate-input --view
        inp = self.root / 'co2.inp'
        code, _, err = self.run_cli([
            'generate-input', str(self.co2_xyz), '-o', str(inp),
            '--periodic', 'NONE', '--view', '--viewer', str(self.mock_viewer),
        ])
        self.assertEqual(code, 0, err)
        self.assertTrue(inp.is_file())
        self.assertEqual(_read_invocations(self.log)[3]['args'], [str(inp)])

        # 5) vibration --view without --geometry fails cleanly
        code, _, err = self.run_cli(['vibration', str(MOLECULAR_VIB), '--view'])
        self.assertEqual(code, 2)
        self.assertIn('--geometry', err)


class ViewerTUITests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.log = self.root / 'tui.jsonl'
        self.mock_viewer = _make_mock_viewer(self.root, self.log)
        self.co2_xyz = self.root / 'co2.xyz'
        self.co2_xyz.write_text(
            '3\nco2\n'
            'O 0.0 0.0 -1.16\n'
            'C 0.0 0.0  0.00\n'
            'O 0.0 0.0  1.16\n',
            encoding='utf-8',
        )
        self.cube_ab = self.root / 'ab.cube'
        self.cube_a = self.root / 'a.cube'
        self.cube_pot = self.root / 'pot.cube'
        self.cube_ab.write_text(synthetic_cube([2, 3, 4, 5]), encoding='utf-8')
        self.cube_a.write_text(synthetic_cube([1, 2, 5, 4]), encoding='utf-8')
        self.cube_pot.write_text(synthetic_cube([0.1, -0.2, 0.3, -0.4]), encoding='utf-8')

    def run_menu(self, *commands, loaded=True):
        out = TTY()
        env = {'DISPLAY': ':0', VIEWER_ENV_VAR: str(self.mock_viewer)}
        with patch.dict(os.environ, env, clear=False), \
             patch('cp2kkit.presentation.shutil.get_terminal_size', return_value=os.terminal_size((120, 24))):
            status = run_main_menu(
                str(self.co2_xyz) if loaded else None,
                stdin=TTY('\n'.join(map(str, commands)) + '\n'),
                stdout=out,
                plain=True,
            )
        self.assertEqual(status, 0, out.getvalue())
        return out.getvalue()

    def test_tui_details_export_cube_and_vibration_open_viewer(self):
        exported = self.root / 'out.extxyz'
        diff_cube = self.root / 'diff.cube'
        text = self.run_menu(
            # 2. Structure details -> v -> Enter
            '2', 'v', '',
            # 3. Export structure -> v -> Enter
            '3', exported, 'v', '',
            # 6/1 Check scalar CUBE -> v with color-cube + flip -> Enter
            '6', '1', self.cube_ab, '', 'v', self.cube_pot, 'y', '',
            # 6/2 Subtract density CUBEs -> v -> Enter
            '6', '2', self.cube_ab, self.cube_a, '', diff_cube, '', 'v', '',
            # 7. Vibrational analysis -> v (Enter uses loaded co2.xyz, Enter frame -1, Enter fixed off) -> Enter
            '7', MOLECULAR_VIB, '', 'v', '', '', '', '',
            # 0. Exit
            '0',
            loaded=True,
        )
        self.assertIn('Opening viewer (close window to return)...', text)
        calls = _read_invocations(self.log)
        self.assertEqual(len(calls), 5, text)
        self.assertEqual(calls[0]['args'], [str(self.co2_xyz)])
        self.assertEqual(calls[1]['args'], [str(exported)])
        self.assertEqual(calls[2]['args'], [str(self.cube_ab), '--cube-length-unit', 'bohr',
                                           '--color-cube', str(self.cube_pot), '--flip-color-sign'])
        self.assertEqual(calls[3]['args'], [str(diff_cube), '--cube-length-unit', 'bohr', '--iso-sign', 'both'])
        self.assertEqual(json.loads(calls[4]['snapshot'])['schema'], 'cp2kkit-viewer-scene-v1')
        self.assertFalse(Path(calls[4]['args'][0]).exists())

    def test_tui_cube_check_refuses_unknown_spatial_unit_viewer_launch(self):
        unknown = self.root / 'unknown-unit.cube'
        unknown.write_text(
            'synthetic CUBE\nindependent scalar field\n'
            '1 0 0 0\n-2 1 0 0\n-2 0 1 0\n-2 0 0 1\n1 0 0.25 0.5 0.75\n'
            '0 0 0 0 1 1 1 1\n',
            encoding='utf-8',
        )
        text = self.run_menu(
            # 6/1 Check scalar CUBE -> default auto options -> v (blocked) -> Enter -> 0 Exit
            '6', '1', unknown, '', 'v', '', '0',
            loaded=False,
        )
        self.assertIn('Cannot view CUBE with unknown spatial unit', text)
        self.assertFalse(self.log.exists())

    def test_input_editor_v_previews_draft_without_writing_files(self):
        before = set(self.root.iterdir())
        out = TTY()
        env = {'DISPLAY': ':0', VIEWER_ENV_VAR: str(self.mock_viewer)}
        with patch.dict(os.environ, env, clear=False), \
             patch('cp2kkit.presentation.shutil.get_terminal_size', return_value=os.terminal_size((120, 24))):
            status = run_editor(
                str(self.co2_xyz), -1, str(self.root / 'never-written.inp'),
                InputSettings(periodic='NONE'),
                stdin=TTY('v\n-10\n'), stdout=out, plain=True,
            )
        self.assertEqual(status, 0, out.getvalue())
        self.assertEqual(set(self.root.iterdir()) - before, {self.log})
        calls = _read_invocations(self.log)
        self.assertEqual(len(calls), 1)
        self.assertIn('&FORCE_EVAL', calls[0]['snapshot'])
        self.assertFalse(Path(calls[0]['args'][0]).exists())
