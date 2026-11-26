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
from cp2kkit.vibration_results import (
    AmbiguousVibration,
    build_viewer_scene,
    export_vibration,
    export_viewer_scene,
    parse_vibration,
    write_vibration,
)
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

    def test_displacement_tokens_must_be_finite_numbers_at_full_row_width(self):
        row = next(line for line in TEXT.splitlines() if line.startswith('     1  O '))
        prefix = row.rsplit(maxsplit=1)[0]
        accepted = self.source(TEXT.replace(row, f'{prefix} -.25D+0', 1))
        self.assertTrue(parse_vibration(accepted).strict_passed)
        for token in ('NaN', '****', 'damaged', '1e+', '1e999', '1e-999'):
            with self.subTest(token=token):
                damaged = f'{prefix} {token}'
                self.assertEqual(len(damaged.split()), len(row.split()))
                path = self.source(TEXT.replace(row, damaged, 1))
                report = parse_vibration(path)
                self.assertFalse(report.complete)
                self.assertFalse(report.strict_passed)
                self.assertEqual([m.mode_id for m in report.modes], [1, 2, 3, 4])
                self.assertEqual([e.text for e in report.diagnostics], [damaged])
                self.assertTrue(any('displacement token' in warning for warning in report.warnings))
        result = self.cli(path, '--strict')
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertFalse(json.loads(result.stdout)['strict_passed'])

    def test_distinct_displacement_atom_orders_mark_block_incomplete(self):
        start = TEXT.index(' VIB|                         4\n')
        report = parse_vibration(self.source(TEXT[:start] + TEXT[start:].replace('2  C', '2  O')))
        self.assertEqual(report.displacement_atoms, [(1, 'O'), (2, 'C'), (3, 'O')])
        self.assertFalse(report.strict_passed)
        self.assertTrue(any('displacement atom indices or elements' in w for w in report.warnings))
        for bad_row in (TEXT.replace('     2  C ', '     1  C ', 1), TEXT.replace('     1  O ', '     0  O ', 1)):
            bad = parse_vibration(self.source(bad_row))
            self.assertFalse(bad.complete)
            self.assertTrue(any('Invalid or duplicate displacement atom index' in w for w in bad.warnings))

    def test_periodic_surface_partial_hessian_output_observation(self):
        surface = (
            ' **** **** ******  **  PROGRAM STARTED AT                synthetic\n'
            ' CP2K| version string:                                      CP2K version 2026.2\n'
            ' GLOBAL| Run type                                            VIBRATIONAL_ANALYSIS\n'
            ' CELL| Periodicity                                                           XYZ\n'
            ' DFT| Multiplicity                                                             1\n'
            ' DFT| Charge                                                                   0\n'
            ' POISSON| Periodicity                                                        XYZ\n'
            ' VIB| Internal  Low frequencies ---\n'
            ' VIB| 1.0E+00 2.0E+00 3.0E+00\n'
            ' VIB|                        NORMAL MODES - CARTESIAN DISPLACEMENTS\n'
            ' VIB|\n'
            ' VIB|                         1                    2                    3\n'
            ' VIB|Frequency (cm^-1)  5.6081757307E+01    3.2525299057E+02    1.5862967520E+03\n'
            ' VIB|Red.Masses (a.u.)  1.0000000000E+00    1.0000000000E+00    1.0000000000E+00\n'
            ' VIB|Frc consts (a.u.)  1.0000000000E-02    2.0000000000E-02    3.0000000000E-01\n'
            '  ATOM  EL               X     Y     Z       X     Y     Z       X     Y     Z\n'
            '   181  O              -0.03 -0.02 -0.01    0.22 -0.03  0.08   -0.10 -0.34 -0.03\n'
            '\n'
            ' -                                DBCSR STATISTICS                             -\n'
            + END
        )
        path = self.source(surface)
        report = parse_vibration(path)
        self.assertTrue(report.complete)
        self.assertTrue(report.strict_passed)
        self.assertEqual(report.periodicity, 'XYZ')
        self.assertEqual(len(report.periodicity_sources), 2)
        self.assertIsNone(report.rotovibrational_vectors)
        self.assertEqual(report.displacement_atoms, [(181, 'O')])
        self.assertIsNone(report.reference_electronic_energy)
        self.assertEqual(report.expected_mode_count_from_diagnostic, 3)
        data = report.to_dict()
        self.assertEqual(data['periodicity'], 'XYZ')
        self.assertEqual(data['displacement_atoms'], [[181, 'O']])
        result = self.cli(path, '--strict')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['periodicity'], 'XYZ')

        rows = 'H 0 0 0\n' * 180 + 'O 2 2 2\n'
        geom = self.root / 'slab.extxyz'
        geom.write_text('181\nLattice="10 0 0 0 10 0 0 0 15" pbc="T T T"\n' + rows, encoding='utf-8')
        scene = build_viewer_scene(report, geom, fixed_atoms='1-180')
        self.assertEqual(scene['pbc'], [True] * 3)
        self.assertEqual([d['atom_index'] for d in scene['modes'][0]['displacements']], [181])
        self.assertTrue(scene['atoms'][179]['fixed'])
        plain = self.root / 'slab.xyz'
        plain.write_text('181\nno lattice\n' + rows, encoding='utf-8')
        with self.assertRaisesRegex(KitError, 'reference structure with a cell and XYZ periodicity'):
            build_viewer_scene(report, plain)

    def test_reference_energy_is_only_from_selected_native_footer(self):
        heading = ' VIB| NORMAL MODES - THERMOCHEMICAL DATA\n'
        row = ' VIB| Electronic energy (U) [kJ/mol]: -2625.49961710\n'
        ordinary = ' ENERGY| Total FORCE_EVAL ( QS ) energy [hartree] -2.0\n'
        text = TEXT.replace(' VIB| Minimum Structure', ordinary + ' VIB| Minimum Structure')
        self.assertIsNone(parse_vibration(self.source(text)).reference_electronic_energy)
        native = text.replace(END, heading + '\n' + row + END)
        report = parse_vibration(self.source(native + text), segment=1, block=1)
        energy = report.reference_electronic_energy
        self.assertEqual((energy.value, energy.unit, energy.source.text),
                         (-2625.49961710, 'kJ/mol', row.rstrip()))
        self.assertEqual(native.splitlines()[energy.source.line - 1], energy.source.text)
        self.assertIsNone(parse_vibration(self.source(native + text), segment=2).reference_electronic_energy)
        for bad in (row + row, row.replace('kJ/mol', 'hartree'),
                    row.replace('-2625.49961710', '1e-999'), row.replace('-2625.49961710', '***')):
            with self.subTest(bad=bad):
                report = parse_vibration(self.source(text.replace(END, heading + bad + END)))
                self.assertIsNone(report.reference_electronic_energy)
                self.assertTrue(report.strict_passed)
                self.assertTrue(any('Unusable thermochemical reference energy' in w for w in report.warnings))

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
                     TEXT.replace('VIBRATIONAL_ANALYSIS', 'MODE_SELECTIVE'), TEXT.replace('NONE', 'XY'),
                     TEXT.replace('NONE', 'XY extra'),
                     TEXT.replace('NONE', 'NONE trailing'),
                     TEXT.replace('POISSON| Periodicity                                        NONE', 'POISSON| Periodicity: XY'),
                     TEXT.replace('POISSON| Periodicity                                        NONE', 'POISSON| Periodicity: NONE'),
                     TEXT.replace('POISSON| Periodicity                                        NONE', 'CELL| Periodicity: XYZ'),
                     TEXT.replace('POISSON| Periodicity                                        NONE', 'POISSON| Periodicity'),
                     TEXT.replace('POISSON| Periodicity                                        NONE', 'CELL| Periodicity XYZ extra'),
                     TEXT.replace('POISSON| Periodicity', 'CELL| Periodicity XYZ\n POISSON| Periodicity'),
                     TEXT.replace('NONE', 'XYZ').replace(' VIB| REPLICA', ' ROT| Number of rotovibrational vectors     6\n VIB| REPLICA'),
                     TEXT.replace(' VIB| REPLICA', ' ROT| Number of rotovibrational vectors     3\n VIB| REPLICA'),
                     TEXT.replace(' VIB| REPLICA', ' ROT| Number of rotovibrational vectors: 6\n VIB| REPLICA'),
                     TEXT.replace(' VIB| REPLICA', ' ROT| Number of rotovibrational vectors     6 extra\n VIB| REPLICA'),
                     TEXT.replace(' VIB| REPLICA', ' ROT| Number of rotovibrational vectors     bad\n VIB| REPLICA'),
                     TEXT.split(HEAD)[0], ' "' + HEAD + '"\n VIB|Frequency (cm^-1) 12\n',
                     ' VIB|Frequency (cm^-1) 12\n'):
            with self.subTest(text=text[:100]), self.assertRaises(ParseError):
                parse_vibration(self.source(text))
        # Damaged periodicity returns CLI exit code 4 (ParseError), not null/strict pass.
        bad_pbc_path = self.source(TEXT.replace('POISSON| Periodicity                                        NONE',
                                                'POISSON| Periodicity: XY'))
        cli_bad = self.cli(bad_pbc_path, '--strict')
        self.assertEqual((cli_bad.returncode, cli_bad.stdout), (4, ''), cli_bad.stderr)
        # Genuinely absent periodicity remains null (and still passes strict with version/run-type/end).
        no_pbc = parse_vibration(self.source(TEXT.replace(' POISSON| Periodicity                                        NONE\n', '')))
        self.assertIsNone(no_pbc.periodicity)
        self.assertEqual(no_pbc.periodicity_sources, [])
        self.assertTrue(no_pbc.strict_passed)
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

    def test_viewer_scene_export_alignment_fixed_atoms_and_protections(self):
        # Reference geometry matching examples/vibration-results/molecular.txt (O1, C2, O3)
        geom = self.root / 'co2.xyz'
        geom.write_text('3\nco2\nO -1.16 0.0 0.0\nC 0.0 0.0 0.0\nO 1.16 0.0 0.0\n', encoding='utf-8')
        report = parse_vibration(SOURCE)
        scene = build_viewer_scene(report, geom, fixed_atoms='1')
        self.assertEqual(scene['schema'], 'cp2kkit-viewer-scene-v1')
        self.assertEqual(len(scene['atoms']), 3)
        self.assertTrue(scene['atoms'][0]['fixed'])
        self.assertFalse(scene['atoms'][1]['fixed'])
        self.assertEqual(len(scene['modes']), 4)
        self.assertEqual([m['mode_id'] for m in scene['modes']], [1, 2, 3, 4])
        self.assertAlmostEqual(scene['modes'][0]['frequency_cm_1'], -123.45678901)
        self.assertEqual(len(scene['modes'][0]['displacements']), 3)
        self.assertEqual(scene['modes'][0]['displacements'][0]['atom_index'], 1)
        self.assertEqual(scene['provenance']['fixed_atoms'], '1')
        # Standard to_dict() remains unchanged (no private displacement vectors leaked)
        self.assertNotIn('_mode_displacements', report.to_dict())

        # CLI export to exclusive new file + overwrite protection (exit 5)
        out_json = self.root / 'co2-scene.json'
        res = self.cli(SOURCE, '--format', 'viewer-scene', '--geometry', geom, '-o', out_json)
        self.assertEqual(res.returncode, 0, res.stderr)
        loaded = json.loads(out_json.read_text(encoding='utf-8'))
        self.assertEqual(loaded['schema'], 'cp2kkit-viewer-scene-v1')
        self.assertEqual(len(loaded['modes']), 4)
        res_dup = self.cli(SOURCE, '--format', 'viewer-scene', '--geometry', geom, '-o', out_json)
        self.assertEqual(res_dup.returncode, 5)

        # Missing --geometry for viewer-scene or stray --geometry for json fails with exit 2
        self.assertEqual(self.cli(SOURCE, '--format', 'viewer-scene').returncode, 2)
        self.assertEqual(self.cli(SOURCE, '--format', 'json', '--geometry', geom).returncode, 2)

        # Element mismatch and out-of-bounds indices are rejected
        bad_geom = self.root / 'bad.xyz'
        bad_geom.write_text('3\nbad\nN -1.16 0 0\nC 0 0 0\nO 1.16 0 0\n', encoding='utf-8')
        with self.assertRaises(KitError):
            build_viewer_scene(report, bad_geom)
        short_geom = self.root / 'short.xyz'
        short_geom.write_text('2\nshort\nO 0 0 0\nC 1 0 0\n', encoding='utf-8')
        with self.assertRaises(KitError):
            build_viewer_scene(report, short_geom)

        # Reject matching prefixes of larger molecular structures and known PBC conflicts.
        large_geom = self.root / 'larger.xyz'
        large_geom.write_text('4\nlarger molecule\nO -1.16 0 0\nC 0 0 0\nO 1.16 0 0\nH 1 2 3\n', encoding='utf-8')
        with self.assertRaisesRegex(KitError, 'cover every atom'):
            build_viewer_scene(report, large_geom)
        periodic_geom = self.root / 'periodic.extxyz'
        periodic_geom.write_text('3\nLattice="8 0 0 0 8 0 0 0 8" pbc="T T T"\n'
                                 'O -1.16 0 0\nC 0 0 0\nO 1.16 0 0\n', encoding='utf-8')
        self.assertEqual(self.cli(SOURCE, '--format', 'viewer-scene', '--geometry', periodic_geom).returncode, 2)
        with self.assertRaisesRegex(KitError, 'cannot be paired with a periodic reference'):
            build_viewer_scene(report, periodic_geom)

        # Incomplete vibration report cannot be exported to viewer-scene
        broken = parse_vibration(self.source(TEXT.replace('-5.0000000000E-01', 'NaN')))
        with self.assertRaises(KitError):
            export_viewer_scene(self.root / 'broken.json', broken, geom)
