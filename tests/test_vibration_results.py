"""Synthetic native-format tests; no CP2K binary or private output needed."""
import csv
import errno
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cp2kkit.errors import KitError, OutputExists, ParseError
from cp2kkit.io import json_text
from cp2kkit.main_tui import run_main_menu
from cp2kkit.vibration_results import AmbiguousVibration, export_vibration, parse_vibration, write_vibration
from tests.test_input_tui import FIXTURES, TTY

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'vibration-results'
SOURCE = EXAMPLE / 'molecular.txt'
TEXT = SOURCE.read_text(encoding='utf-8')
HEAD = 'NORMAL MODES - CARTESIAN DISPLACEMENTS'
FIRST = '-1.2345678901E+02   -5.0000000000E-01    0.0000000000E+00'
END = ' **** **** ******  **  PROGRAM ENDED AT                  synthetic\n'


class VibrationResultTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def source(self, text):
        path = self.root / 'test.out'
        path.write_bytes(text.encode('utf-8'))
        return path

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'cp2kkit', 'vibration', *map(str, args)],
                              capture_output=True, text=True, timeout=10)

    def test_public_observations_and_provenance(self):
        report = parse_vibration(SOURCE, zero_threshold_cm_1=0.5)
        data = report.to_dict()
        expected = json.loads((EXAMPLE/'expected-selected.json').read_text(encoding='utf-8'))
        self.assertEqual({key: data[key] for key in expected}, expected)
        self.assertEqual(data['schema_version'], '0.1.0')
        self.assertEqual(data['operation'], 'vibration_observation')
        self.assertIs(data['complete'], True)
        self.assertEqual(data['source']['sha256'], hashlib.sha256(SOURCE.read_bytes()).hexdigest())
        self.assertEqual(data['source']['size_bytes'], len(SOURCE.read_bytes()))
        self.assertEqual(data['source']['path'], str(SOURCE))
        self.assertEqual([m.mode_id for m in report.modes], [1, 2, 3, 4])
        self.assertEqual([m.frequency.value for m in report.modes], [-123.45678901, -0.5, 0.0, 2345.6789012])
        first = report.modes[0]
        self.assertEqual(first.frequency.source.text, TEXT.splitlines()[first.frequency.source.line - 1])
        self.assertEqual(first.mode_source.text, TEXT.splitlines()[first.mode_source.line - 1])
        self.assertEqual(first.frequency.unit, 'cm^-1')
        self.assertEqual(first.token, '-1.2345678901E+02')
        self.assertEqual(report.count_source.text.strip(), 'VIB| Internal  Low frequencies ---')
        self.assertEqual(parse_vibration(SOURCE).counts, dict(observed=4, raw_negative=2, negative=2,
                                                              near_zero=1, positive=1))

    def test_numeric_forms_and_threshold_boundary(self):
        path = self.source(TEXT.replace(FIRST, '-.5D+0 +.5d0 -0.0000E+00'))
        report = parse_vibration(path, zero_threshold_cm_1=0.5)
        self.assertTrue(report.strict_passed)
        self.assertEqual(report.counts, dict(observed=4, raw_negative=1, negative=0, near_zero=3, positive=1))
        self.assertEqual(math.copysign(1, report.modes[2].frequency.value), -1)
        for bad in (-1, True, '0', None, float('inf'), float('nan'), 10**1000):
            with self.subTest(bad=bad), self.assertRaises(KitError):
                parse_vibration(path, zero_threshold_cm_1=bad)

    def test_invalid_tokens_retain_other_columns_without_numeric_salvage(self):
        for token in ('NaN', 'Inf', '1E+9999', '***', '10i', '5.0junk', '1e-', '1_0', '1e-9999'):
            with self.subTest(token=token):
                report = parse_vibration(self.source(TEXT.replace('-5.0000000000E-01', token)))
                self.assertFalse(report.strict_passed)
                self.assertFalse(report.complete)
                self.assertEqual([m.mode_id for m in report.modes], [1, 3, 4])
                self.assertEqual([m.ordinal for m in report.modes], [1, 2, 3])
                self.assertTrue(any(token in e.text for e in report.diagnostics))
                self.assertIn('frequency token', '\n'.join(report.warnings))
                json_text(report.to_dict())  # deterministic finite serialization

    def test_missing_duplicate_and_mismatched_ids(self):
        id_row = ' VIB|                         1                    2                    3\n'
        for replacement, ids in (('', [None]*3), (' VIB| 1 1 3\n', [1, 1, 3]),
                                 (' VIB| 1 3\n', [None]*3), (' VIB| 2 1 3\n', [2, 1, 3]),
                                 (' VIB| 0 2 3\n', [None, 2, 3])):
            with self.subTest(replacement=replacement):
                report = parse_vibration(self.source(TEXT.replace(id_row, replacement)))
                self.assertFalse(report.complete)
                self.assertEqual([m.mode_id for m in report.modes], ids+[4])
                self.assertEqual([m.mode_source is not None for m in report.modes],
                                 [mode_id is not None for mode_id in ids+[4]])

    def test_text_completion_is_separate_from_program_end_and_scf(self):
        block_only = TEXT.removesuffix(END)
        report = parse_vibration(self.source(block_only))
        self.assertTrue(report.complete)
        self.assertFalse(report.strict_passed)
        self.assertIsNone(report.program_end)
        report = parse_vibration(self.source(TEXT.replace(' VIB| REPLICA',
            ' SCF run NOT converged\n SCF run converged in 13 steps\n VIB| REPLICA', 1)))
        self.assertTrue(report.strict_passed)
        self.assertEqual(report.scf_summaries, {'converged': 1, 'not_converged': 1})
        self.assertIsNone(report.to_dict()['electronic_converged'])
        report = parse_vibration(self.source(TEXT[TEXT.index(' VIB|                        '+HEAD):]))
        self.assertTrue(report.complete)
        self.assertFalse(report.strict_passed)
        self.assertIsNone(report.software_version)

    def test_truncation_or_missing_whole_group(self):
        last_group = TEXT.index(' VIB|                         4\n')
        for damaged, count in ((TEXT[:last_group], 3), (TEXT[:last_group] + END, 3),
                               (TEXT[:TEXT.index(' VIB|Red.Masses')], 3),
                               (TEXT.removesuffix('\n'+END), 4),
                               (TEXT[:TEXT.index('     3  O', last_group)]+'\n'+END, 4)):
            with self.subTest(count=count, tail=damaged[-80:]):
                report = parse_vibration(self.source(damaged))
                self.assertEqual(report.counts['observed'], count)
                self.assertFalse(report.complete)
                self.assertFalse(report.strict_passed)
        stripped = TEXT[TEXT.index(' VIB|                        '+HEAD):last_group]
        self.assertFalse(parse_vibration(self.source(stripped)).complete)
        self.assertEqual(parse_vibration(self.source(stripped)).counts['observed'], 3)

    def test_one_mode_and_native_footer_without_diagnostic(self):
        start = TEXT.index(' VIB|                        '+HEAD)
        final_group = TEXT[TEXT.index(' VIB|                         4\n'):].removesuffix(END)
        # Projected linear two-atom layout: no implicit translation/rotation zeros.
        final_group = final_group.replace('                         4', '                         1')
        final_group = final_group.replace('     3  O               0.00  0.00  0.00\n', '')
        final_group = final_group.replace(' VIB|Red.Masses', ' VIB|IR int (KM/Mole)  1.0000000000E+00\n VIB|Red.Masses')
        path = self.source(TEXT[:TEXT.index(' VIB| REPLICA')] + ' ROT| Number of rotovibrational vectors     5\n'
                           + TEXT[start:TEXT.index(' VIB|                         1')]
                           + final_group + ' -                                DBCSR STATISTICS                             -\n')
        report = parse_vibration(path)
        self.assertTrue(report.complete, report.warnings)
        self.assertIsNone(report.expected_mode_count_from_diagnostic)
        self.assertEqual([m.mode_id for m in report.modes], [1])
        self.assertIsNone(report.program_end)

    def test_unsupported_inputs_and_recognizable_empty_partial(self):
        for text in (TEXT.replace('cm^-1', 'THz'), TEXT.replace('2026.2', '2026.1'),
                     TEXT.replace('VIBRATIONAL_ANALYSIS', 'MODE_SELECTIVE'), TEXT.replace('NONE', 'XYZ'),
                     TEXT.replace(' VIB| REPLICA', ' ROT| Number of rotovibrational vectors     3\n VIB| REPLICA'),
                     TEXT.split(HEAD)[0], ' "' + HEAD + '"\n VIB|Frequency (cm^-1) 12\n',
                     ' VIB|Frequency (cm^-1) 12\n'):
            with self.subTest(text=text[:100]), self.assertRaises(ParseError):
                parse_vibration(self.source(text))
        path = self.source(TEXT[:TEXT.index(HEAD)+len(HEAD)])
        report = parse_vibration(path)
        self.assertFalse(report.complete)
        self.assertEqual(report.modes, [])
        stream = io.StringIO()
        write_vibration(stream, report, 'csv')
        rows = list(csv.DictReader(io.StringIO(stream.getvalue())))
        self.assertEqual([(row['record'], row['frequency_cm_1']) for row in rows], [('block', '')])
        self.assertEqual(rows[0]['source_text'], report.heading.text)

    def test_multiple_and_concatenated_analyses(self):
        partial = TEXT[:TEXT.index(' VIB|Red.Masses')]
        path = self.source(partial + TEXT + TEXT)
        with self.assertRaises(AmbiguousVibration) as caught:
            parse_vibration(path, block=1)
        self.assertEqual([c[:2] for c in caught.exception.choices], [(1, 1), (2, 1), (3, 1)])
        self.assertFalse(parse_vibration(path, segment=1).complete)
        self.assertIsNone(parse_vibration(path, segment=1).program_end)
        self.assertTrue(parse_vibration(path, segment=2).strict_passed)
        start = TEXT.index(' VIB| Frequencies after removal')
        path = self.source(TEXT.removesuffix(END) + TEXT[start:])
        with self.assertRaises(AmbiguousVibration) as caught:
            parse_vibration(path, segment=1)
        self.assertEqual([c[:2] for c in caught.exception.choices], [(1, 1), (1, 2)])
        self.assertTrue(parse_vibration(path, segment=1, block=1).complete)
        self.assertTrue(parse_vibration(path, block=2).complete)
        for selectors in (dict(block=3), dict(segment=2), dict(block=0), dict(segment=True), dict(block=1.0)):
            with self.subTest(selectors=selectors), self.assertRaises(KitError) as error:
                parse_vibration(path, **selectors)
            self.assertEqual(error.exception.code, 2)

    def test_cli_json_csv_strict_and_error_channels(self):
        report = parse_vibration(SOURCE, zero_threshold_cm_1=0.5)
        args = SOURCE, '--zero-threshold-cm-1', '5D-1', '--strict'
        result = self.cli(*args)
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertEqual(result.stdout, json_text(report.to_dict()))
        csv_result = self.cli(*args, '--format', 'csv')
        self.assertEqual((csv_result.returncode, csv_result.stderr), (0, ''))
        rows = list(csv.DictReader(io.StringIO(csv_result.stdout)))
        self.assertEqual([row['printed_token'] for row in rows], [m.token for m in report.modes])
        self.assertEqual([row['mode_id'] for row in rows], ['1', '2', '3', '4'])
        self.assertTrue(all(row['source_sha256'] == report.source['sha256'] for row in rows))
        self.assertEqual(rows[0]['source_text'], report.modes[0].frequency.source.text)
        for extra, expected in (((), 0), (('--strict',), 7)):
            result = self.cli(self.source(TEXT[:TEXT.index(' VIB|Red.Masses')]), *extra)
            self.assertEqual(result.returncode, expected)
            self.assertEqual(json.loads(result.stdout)['status'], 'incomplete')
            self.assertIn('WARNING:', result.stderr)
        out = self.root/'report.json'
        result = self.cli(self.root/'test.out', '--strict', '-o', out)
        self.assertEqual((result.returncode, result.stdout), (7, ''))
        self.assertEqual(json.loads(out.read_text())['status'], 'incomplete')
        for path, extra, code in ((SOURCE, ('--zero-threshold-cm-1=nan',), 2),
                                  (SOURCE, ('--zero-threshold-cm-1=-0.01',), 2),
                                  (SOURCE, ('--block', '2'), 2), (self.root, (), 2),
                                  (self.source(TEXT+TEXT), (), 3), (FIXTURES/'normal.out', (), 4),
                                  (SOURCE, ('-o', SOURCE), 5)):
            with self.subTest(code=code, extra=extra):
                result = self.cli(path, *extra)
                self.assertEqual((result.returncode, result.stdout), (code, ''), result.stderr)
                self.assertIn('cp2kkit:', result.stderr)

    def test_exclusive_exports_and_source_bytes(self):
        path = self.source(TEXT.replace('\n', '\r\n'))
        original = path.read_bytes()
        report = parse_vibration(path)
        self.assertEqual(report.source['sha256'], hashlib.sha256(original).hexdigest())
        out = self.root/'new.inp'
        export_vibration(out, report, 'csv')
        stream = io.StringIO()
        write_vibration(stream, report, 'csv')
        self.assertEqual(out.read_bytes(), stream.getvalue().encode())
        hardlink = self.root/'hardlink'
        hardlink.hardlink_to(path)
        for destination in (out, path, hardlink):
            with self.assertRaises(OutputExists):
                export_vibration(destination, report)
        for target in (path, self.root/'absent'):
            link = self.root/f'sym-{target.name}'
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                continue  # platforms without symlink privileges still check direct/alias collisions
            with self.assertRaises(OutputExists):
                export_vibration(link, report)
            self.assertTrue(link.is_symlink())
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse((self.root/'absent').exists())
        with self.assertRaises(KitError):
            export_vibration(self.root/'invalid', report, 'xlsx')
        self.assertFalse((self.root/'invalid').exists())

    def test_failed_single_export_removes_its_partial_file(self):
        report = parse_vibration(SOURCE)
        out = self.root/'interrupted.json'

        def interrupt(stream, *_):
            stream.write('{')
            raise KeyboardInterrupt

        with patch('cp2kkit.vibration_results.write_vibration', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                export_vibration(out, report)
        self.assertFalse(out.exists())

    def test_menu_back_ambiguity_and_parity(self):
        path = self.source(TEXT+TEXT)
        log = TTY()
        inputs = f'5\n0\n6\nback\n7\n{path}\n.5\n1/9\n2/1\nd\n\n7\ncancel\n0\n'
        code = run_main_menu(FIXTURES/'trajectory.xyz', stdin=TTY(inputs), stdout=log, plain=True)
        text = ' '.join(log.getvalue().split())
        self.assertEqual(code, 0)
        self.assertIn('Multiple normal-mode blocks (segment/block)', text)
        self.assertIn('Choose a listed segment/block', text)
        self.assertIn('Segment 2, block 1: complete', text)
        self.assertIn('raw negatives: 2', text)
        self.assertGreaterEqual(text.count('Formula: H2'), 4)
        self.assertIn('Cancelled', text)
        self.assertNotIn('CUBE path', text)
        self.assertEqual(list(self.root.iterdir()), [path])
        out, csv_path = self.root/'report.json', self.root/'report.csv'
        log = TTY()
        inputs = f'7\n{SOURCE}\n.5\nj\n{out}\nc\n{csv_path}\n\n0\n'
        self.assertEqual(run_main_menu(stdin=TTY(inputs), stdout=log, plain=True), 0)
        self.assertIn('No structure loaded', log.getvalue())
        report = parse_vibration(SOURCE, zero_threshold_cm_1=0.5)
        self.assertEqual(out.read_bytes(), json_text(report.to_dict()).encode())
        stream = io.StringIO()
        write_vibration(stream, report, 'csv')
        self.assertEqual(csv_path.read_bytes(), stream.getvalue().encode())

    def test_menu_refuses_selection_if_source_changes(self):
        path = self.source(TEXT+TEXT)

        class ChangingTTY(TTY):
            def readline(self):
                line = super().readline()
                if line == '2/1\n':
                    path.write_text(TEXT+TEXT+'\n', encoding='utf-8')
                return line

        log = TTY()
        self.assertEqual(run_main_menu(stdin=ChangingTTY(f'7\n{path}\n\n2/1\n\n0\n'), stdout=log, plain=True), 0)
        self.assertIn('Output changed while selecting a block', log.getvalue())
        self.assertNotIn('Segment 2, block 1: complete', log.getvalue())

    @unittest.skipUnless(os.name == 'posix', 'PTY smoke requires POSIX')
    def test_real_pty_narrow_and_unsized(self):
        import fcntl
        import pty
        import select
        import struct
        import termios
        import time

        for width in (0, 36):
            with self.subTest(width=width):
                master, slave = pty.openpty()
                try:
                    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24 if width else 0, width, 0, 0))
                    env = {k: v for k, v in os.environ.items() if k != 'COLUMNS'}
                    with subprocess.Popen([sys.executable, '-m', 'cp2kkit', '--plain'], env=env,
                                          stdin=slave, stdout=slave, stderr=slave) as proc:
                        os.close(slave)
                        slave = None
                        try:
                            os.write(master, f'7\n{SOURCE}\n\n\n0\n'.encode())
                            data = bytearray()
                            deadline = time.monotonic() + 10
                            while time.monotonic() < deadline:
                                if not select.select([master], [], [], 0.1)[0]:
                                    continue
                                try:
                                    received = os.read(master, 65536)
                                except OSError as exc:
                                    if exc.errno != errno.EIO:
                                        raise
                                    break
                                if not received:
                                    break
                                data.extend(received)
                            self.assertEqual(proc.wait(timeout=1), 0, data.decode())
                        finally:
                            if proc.poll() is None:
                                proc.kill()
                    rendered = ' '.join(data.decode().split())
                    self.assertIn('Segment 1, block 1: complete', rendered)
                    self.assertIn('Observed frequencies: 4', rendered)
                finally:
                    os.close(master)
                    if slave is not None:
                        os.close(slave)
