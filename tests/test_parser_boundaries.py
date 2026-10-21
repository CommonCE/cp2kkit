"""Synthetic ENERGY token boundaries, not CP2K runtime validation."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from itertools import product
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from cp2kkit.cli import main
from cp2kkit.errors import ParseError
from cp2kkit.parser import parse_output
from cp2kkit.quality import quality_report


class EnergyBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'synthetic.out'

    def output(self, token, suffix='', terminated=True, unit='a.u.'):
        line = f' ENERGY| Total FORCE_EVAL ( QS ) energy [{unit}] : '+token+suffix
        text = ('PROGRAM STARTED AT synthetic\nCP2K| version string: synthetic\n'
                'GLOBAL| Run type ENERGY\nSCF run converged in 5 steps\n'+line)
        if terminated:
            text += '\nPROGRAM ENDED AT synthetic\n'
        self.path.write_text(text)
        return line

    def test_whitespace_comments_and_numeric_forms_preserve_evidence(self):
        for unit, (token, value) in product(('a.u.', 'hartree', 'HARTREE'),
                (('-17.123', -17.123), ('0', 0.), ('+.25', .25),
                 ('-1.25D+01', -12.5), ('1.2e-3', .0012))):
            for suffix in ('', ' ', '   ', '\t', '  # synthetic annotation', '\ttrailing text'):
                with self.subTest(unit=unit, token=token, suffix=suffix):
                    line = self.output(token, suffix, unit=unit)
                    run = parse_output(self.path)
                    energy = run.segments[0].final_energy
                    self.assertIsNotNone(energy)
                    self.assertEqual(energy.value, value)
                    self.assertEqual(energy.unit, 'hartree')
                    self.assertEqual(energy.source.text, line)
                    self.assertEqual(energy.source.line, 5)
                    self.assertEqual(run.source['sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
                    self.assertEqual(quality_report(run)['status'], 'passed')

    def test_adjacent_garbage_and_malformed_numbers_are_not_prefix_parsed(self):
        for unit, token in product(('a.u.', 'hartree'),
                ('1.2broken', '1.2D+', '1.2D+3garbage', '1.2.3', '1e', '+', '.',
                 'NaN', 'Inf', '-Infinity', r'1.2\s')):
            with self.subTest(unit=unit, token=token):
                self.output(token, unit=unit)
                run = parse_output(self.path)
                self.assertIsNone(run.segments[0].final_energy)
                self.assertEqual(len(run.segments[0].unparsed_energy_records), 1)
                self.assertEqual(quality_report(run)['status'], 'not_passed')

    def test_energy_at_eof_does_not_infer_termination(self):
        for unit in ('a.u.', 'hartree'):
            with self.subTest(unit=unit):
                self.output('-17.123', terminated=False, unit=unit)
                run = parse_output(self.path)
                self.assertEqual(run.segments[0].final_energy.value, -17.123)
                self.assertEqual(quality_report(run)['status'], 'not_passed')

    def test_strict_cli_and_overflow_exit_codes(self):
        for unit, (token, suffix, expected) in product(('a.u.', 'hartree'),
                (('-17.123', '\t', 0), ('1.2broken', '', 7), ('1e999', '', 4))):
            with self.subTest(unit=unit, token=token):
                self.output(token, suffix, unit=unit)
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(main(['report', str(self.path), '--strict']), expected)
        for unit in ('a.u.', 'hartree'):
            self.output('1e999', unit=unit)
            with self.assertRaises(ParseError):
                parse_output(self.path)

    def test_unsupported_units_are_not_assumed_hartree(self):
        for unit in ('eV', 'Ry', 'Ha', 'hartrees', 'hartree/atom', '', 'a.u'):
            with self.subTest(unit=unit):
                self.output('-17.123', unit=unit)
                run = parse_output(self.path)
                self.assertIsNone(run.segments[0].final_energy)
                self.assertEqual(len(run.segments[0].unparsed_energy_records), 1)
                self.assertEqual(quality_report(run)['status'], 'not_passed')

    def test_native_style_spacing_and_separators(self):
        for unit, separator in product(('a.u.', 'hartree'), (' ', '   ', '\t', ': ', '= ')):
            with self.subTest(unit=unit, separator=separator):
                line = self.output('-5.768648458111624', unit=unit)
                native = line.replace(f'[{unit}] : ', f'[{unit}]'+separator)
                self.path.write_text(self.path.read_text().replace(line, native))
                run = parse_output(self.path)
                self.assertEqual(run.segments[0].final_energy.value, -5.768648458111624)
                self.assertEqual(run.segments[0].final_energy.source.text, native)
                self.assertFalse(run.segments[0].unparsed_energy_records)

    def test_mixed_labels_preserve_scf_association_and_bad_final_record(self):
        self.path.write_text(
            'CP2K| version string: synthetic\nGLOBAL| Run type ENERGY\n'
            'SCF run converged in 5 steps\n'
            'ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.] -1.0\n'
            'ENERGY| Total FORCE_EVAL ( QS ) energy [hartree] -2.0\n'
            'ENERGY| Total FORCE_EVAL ( QS ) energy [hartree] -3.0broken\n'
            'PROGRAM ENDED AT synthetic\n')
        run = parse_output(self.path)
        self.assertEqual([e.quantity.value for e in run.segments[0].energies], [-1., -2.])
        self.assertEqual([e.scf_converged for e in run.segments[0].energies], [True, None])
        self.assertEqual(len(run.segments[0].unparsed_energy_records), 1)
        self.assertFalse(quality_report(run)['segments'][0]['energy_usable'])

    def test_hartree_energy_after_end_starts_incomplete_segment(self):
        self.output('-1.0')
        with self.path.open('a') as stream:
            stream.write('ENERGY| Total FORCE_EVAL ( QS ) energy [hartree] -2.0\n')
        run = parse_output(self.path)
        self.assertEqual(len(run.segments), 2)
        self.assertTrue(run.segments[0].completed)
        self.assertFalse(run.segments[1].completed)
        self.assertEqual(run.segments[1].final_energy.value, -2.)
        self.assertIsNone(run.segments[1].energies[0].scf_converged)
        self.assertEqual(quality_report(run)['status'], 'not_passed')

    def test_hartree_cli_subprocess_json_preserves_unit_and_evidence(self):
        line = self.output('-1.25D+01', unit='hartree')
        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, 'PYTHONPATH': str(root/'src')}
        result = subprocess.run([sys.executable, '-m', 'cp2kkit', 'parse', str(self.path)],
                                cwd=self.tmp.name, env=env, capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        energy = data['segments'][0]['final_energy']
        self.assertEqual(energy['value'], -12.5)
        self.assertEqual(energy['unit'], 'hartree')
        self.assertEqual(energy['source']['text'], line)
        self.assertEqual(data['quality']['status'], 'passed')
