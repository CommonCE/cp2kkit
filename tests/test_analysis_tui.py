"""Application-menu parity using synthetic output/fields; no CP2K execution."""
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import main
from cp2kkit.main_tui import run_main_menu
from cp2kkit.parser import parse_output
from cp2kkit.quality import quality_report
from tests.test_cube import synthetic_cube
from tests.test_interface_operations import FIXTURES, TTY


class AnalysisMenuTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.output = self.root/'run.out'
        text = (FIXTURES/'normal.out').read_text().replace(
            ' Total wall time', ' ENERGY| Total FORCE_EVAL ( QS ) energy [unsupported]: -1\n Total wall time')
        self.output.write_text(text)
        self.structure = FIXTURES/'trajectory.xyz'
        self.cube = self.root/'field.cube'
        self.cube.write_text(synthetic_cube([1, 2, 3, 4]))

    def session(self, *commands, loaded=False):
        log = TTY()
        with patch('cp2kkit.presentation.shutil.get_terminal_size', return_value=os.terminal_size((120, 24))):
            status = run_main_menu(self.structure if loaded else None,
                                   stdin=TTY('\n'.join(map(str, commands))+'\n'), stdout=log, plain=True)
        self.assertEqual(status, 0, log.getvalue())
        return log.getvalue()

    def test_parse_summary_details_and_exclusive_exports(self):
        json_path, csv_path = self.root/'run.json', self.root/'run.csv'
        log = self.session('5', '2', self.root, 'd', 'j', json_path, 'c', csv_path, 'back', '0', loaded=True)
        for expected in ('Software: CP2K; version: CP2K version 2026.1', 'project: demo',
                         'Segments: 1; observed records: energy=1, SCF=1',
                         'Unsupported or malformed energy record', '"quality":', str(self.output),
                         str(json_path), str(csv_path)):
            self.assertIn(expected, log)
        self.assertGreaterEqual(log.count(self.structure.name), 2)
        run = parse_output(self.output)
        self.assertEqual(json.loads(json_path.read_text()), {**run.to_dict(), 'quality': quality_report(run)})
        with csv_path.open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([row['record'] for row in rows], ['energy', 'scf_iterations'])
        for action, path in (('j', json_path), ('c', csv_path)):
            with self.subTest(action=action):
                before = path.read_bytes()
                log = self.session('5', '2', self.output, action, path, '', '0')
                self.assertIn('Refusing to overwrite', log)
                self.assertEqual(path.read_bytes(), before)

    def test_parse_is_read_only_on_details_return_cancel_and_ambiguity(self):
        before = set(self.root.iterdir())
        for choice in ('', '0', 'back', 'cancel', 'q'):
            self.session('5', '2', self.output, 'd', choice, '0')
        self.session('5', '2', self.output, 'j', '0', '0')
        self.session('5', '2', self.output, 'c', 'back', '0')
        self.session('5', '2', self.output, 'd')  # EOF
        self.assertEqual(set(self.root.iterdir()), before)
        second = self.root/'other.out'
        second.write_bytes(self.output.read_bytes())
        for action in ('2', '3'):
            log = self.session('5', action, self.root, '', '0')
            self.assertIn('Ambiguous output', log)
            self.assertNotIn('observed records:', log)
            self.assertNotIn('Plot kind', log)
        self.assertEqual(set(self.root.iterdir()), before | {second})

    @unittest.skipUnless(find_spec('matplotlib'), 'matplotlib optional')
    def test_plot_energy_default_and_scf_and_sidecar_collision(self):
        for kind in ('energy', 'scf'):
            with self.subTest(kind=kind):
                png = self.root/f'{kind}.png'
                log = self.session('5', '3', self.output, '' if kind == 'energy' else kind, png, '', '0')
                for target in (png, png.with_suffix('.csv'), png.with_suffix('.json')):
                    self.assertIn(str(target), log)
                    self.assertTrue(target.is_file())
                self.assertTrue(png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertEqual(json.loads(png.with_suffix('.json').read_text())['kind'], kind)
                self.assertIn('Text quality status:', log)
                self.assertIn('Unsupported or malformed energy record', log)
        occupied = self.root/'occupied.json'
        occupied.write_text('existing')
        png = occupied.with_suffix('.png')
        log = self.session('5', '3', self.output, '', png, '', '0')
        self.assertIn('Refusing to overwrite', log)
        self.assertEqual(occupied.read_text(), 'existing')
        self.assertFalse(png.exists())
        self.assertFalse(png.with_suffix('.csv').exists())

    def test_plot_caps_terminal_parser_warnings_but_passes_all_to_writer(self):
        text = self.output.read_text()
        damaged = ' ENERGY| Total FORCE_EVAL ( QS ) energy [unsupported]: -2\n'
        self.output.write_text(text.replace(' Total wall time', damaged * 9 + ' Total wall time'))
        warnings = parse_output(self.output).parser_warnings
        self.assertEqual(len(warnings), 10)
        png = self.root/'plot.png'
        with patch('cp2kkit.plot.plot_run', return_value=[png, png.with_suffix('.csv'), png.with_suffix('.json')]) as plot:
            log = self.session('5', '3', self.output, '', png, '', '0')
        self.assertEqual(plot.call_args.args[0].parser_warnings, warnings)
        self.assertEqual(log.count('Warning: '), 8)
        for warning in warnings[:8]:
            self.assertIn(f'Warning: {warning}\n', log)
        for warning in warnings[8:]:
            self.assertNotIn(warning, log)
        self.assertIn('Additional warnings are available in the plot JSON sidecar.', log)

    def test_missing_matplotlib_returns_to_menu_without_outputs(self):
        before = set(self.root.iterdir())
        with patch.dict(sys.modules, {'matplotlib.figure': None}):
            log = self.session('5', '3', self.output, '', self.root/'new.png', '', '2', '', '0', loaded=True)
        self.assertIn('Plotting requires matplotlib', log)
        self.assertIn('Full path:', log)
        self.assertEqual(set(self.root.iterdir()), before)

    def test_interrupt_at_new_output_prompt_returns_without_publication(self):
        class InterruptedTTY(TTY):
            def readline(self):
                line = super().readline()
                if line == 'interrupt\n':
                    raise KeyboardInterrupt
                return line

        before = set(self.root.iterdir())
        log = TTY()
        commands = f'5\n2\n{self.output}\nj\ninterrupt\n6\n3\n{self.cube}\n\n\ninterrupt\n0\n'
        self.assertEqual(run_main_menu(self.structure, stdin=InterruptedTTY(commands), stdout=log, plain=True), 0)
        self.assertEqual(log.getvalue().count('Cancelled; returning to the main menu.'), 2)
        self.assertGreaterEqual(log.getvalue().count(self.structure.name), 3)
        self.assertEqual(set(self.root.iterdir()), before)

    def test_planar_axis_assertions_and_skew_profile(self):
        self.cube.write_text(synthetic_cube([1, 2, 3, 4], shape=(-2, -1, -2), comments=('generic', 'field'),
                                            vectors=((1, 0, 0), (1, 2, 0), (1, 1, -3))))
        csv_path = self.root/'planes.csv'
        sidecar = Path(str(csv_path)+'.json')
        log = self.session('6', '3', self.cube, 'bad-axis', 'y', 'a', 'signed', 'angstrom',
                           'electron-density', 'e/angstrom^3', csv_path, 'd', '', '0', loaded=True)
        for expected in ('Native grid index axis (not necessarily Cartesian)', 'Choose x or y or z',
                         'Native grid axis: y; planes: 1', 'Cumulative integral includes each full slab',
                         '"normal_cartesian":', str(csv_path), str(sidecar)):
            self.assertIn(expected, log)
        self.assertGreaterEqual(log.count(self.structure.name), 2)
        report = json.loads(sidecar.read_text())
        self.assertEqual(report['axis'], 'y')
        self.assertEqual(report['input']['length_unit'], 'angstrom')
        self.assertEqual(report['input']['scalar_unit'], 'e/angstrom^3')
        self.assertEqual(report['input']['scalar_type'], 'electron-density')
        self.assertAlmostEqual(report['total_integral_electrons'], 60)
        with csv_path.open(newline='') as stream:
            self.assertAlmostEqual(float(next(csv.DictReader(stream))['cumulative_electrons']), 60)

    def test_cube_adapters_report_the_normalized_sidecar_path(self):
        fragment = self.root/'fragment.cube'
        fragment.write_text(synthetic_cube([0, 0, 0, 0]))
        for command, paths, menu, suffix in (
                ('cube-diff', [str(self.cube), str(fragment)], ('6', '2', self.cube, fragment, ''), 'cube'),
                ('cube-planar', [str(self.cube)], ('6', '3', self.cube, '', ''), 'csv')):
            with self.subTest(command=command):
                cli_raw = f'{self.root}/./cli.{suffix}/'
                cli_output = Path(cli_raw)
                cli_sidecar = Path(str(cli_output)+'.json')
                with redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(main([command, *paths, '-o', cli_raw]), 0, err.getvalue())
                self.assertEqual(err.getvalue().splitlines()[0], f'Wrote {cli_output} and {cli_sidecar}')
                self.assertTrue(cli_sidecar.is_file())
                tui_raw = f'{self.root}/./tui.{suffix}/'
                tui_output = Path(tui_raw)
                tui_sidecar = Path(str(tui_output)+'.json')
                args = (*menu, tui_raw, '', '', '0') if command == 'cube-diff' else (*menu, tui_raw, '', '0')
                log = self.session(*args)
                self.assertIn(f'Generated path: {tui_sidecar.resolve()}\n', log)
                self.assertTrue(tui_sidecar.is_file())

    def test_planar_invalid_collision_and_cancel_leave_no_new_files(self):
        dest = self.root/'profile.csv'
        sidecar = Path(str(dest)+'.json')
        sidecar.write_text('existing')
        before = set(self.root.iterdir())
        log = self.session('6', '3', self.cube, '', '', dest, '', '0')
        self.assertIn('Refusing to overwrite', log)
        self.assertEqual(sidecar.read_text(), 'existing')
        self.session('6', '0', '0')
        self.session('6', '3', self.cube, 'back', '0')
        self.session('6', '3', self.cube, '', 'a', 'cancel', '0')
        self.session('6', '3', self.cube, '', '', 'cancel', '0')
        self.session('5', '3', self.output, '', 'back', '0')
        for text in (synthetic_cube([1, 2, 3, 4], vectors=((1, 0, 0), (1, 0, 0), (0, 0, 1))),
                     synthetic_cube([1, 2])):
            self.cube.write_text(text)
            log = self.session('6', '3', self.cube, '', '', self.root/'invalid.csv', '', '0')
            self.assertIn('Error:', log)
            self.assertNotIn('Generated path:', log)
        self.assertEqual(set(self.root.iterdir()), before)

    @unittest.skipUnless(os.name == 'posix', 'PTY smoke requires POSIX')
    def test_real_pty_analysis_and_return_to_loaded_structure(self):
        import errno
        import pty
        import select
        import time

        output, planar, plot = self.root/'pty.json', self.root/'pty.csv', self.root/'plot.png'
        commands = ('5', '2', self.output, 'j', output, '', '5', '3', self.output, 'scf', plot, '',
                    '6', '3', self.cube, '', '', planar, '', '2', '', 'q')
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        try:
            proc = subprocess.Popen([sys.executable, '-m', 'cp2kkit', '--plain', str(self.structure)],
                                    stdin=slave, stdout=slave, stderr=slave)
        finally:
            os.close(slave)
        try:
            os.write(master, ('\n'.join(map(str, commands))+'\n').encode())
            data = bytearray()
            deadline = time.monotonic()+20
            while time.monotonic() < deadline and select.select([master], [], [], max(0, deadline-time.monotonic()))[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break  # Slave closed on Linux.
                if not chunk:
                    break
                data.extend(chunk)
            self.assertEqual(proc.wait(timeout=1), 0, data.decode())
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        log = data.decode()
        self.assertNotIn('\x1b', log)
        self.assertIn('observed records: energy=1, SCF=1', log)
        self.assertIn('Native grid axis: z; planes: 2', log)
        self.assertIn(f'Full path: {self.structure.resolve()}', log)
        self.assertTrue(output.is_file())
        self.assertTrue(planar.is_file())
        if find_spec('matplotlib'):
            self.assertTrue(plot.is_file())
        else:
            self.assertIn('Plotting requires matplotlib', log)
            self.assertFalse(plot.exists())
