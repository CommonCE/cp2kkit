"""Synthetic ENERGY token boundaries, not CP2K runtime validation."""
import hashlib
import io
import tempfile
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

    def output(self, token, suffix='', terminated=True):
        line = ' ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.] : '+token+suffix
        text = ('PROGRAM STARTED AT synthetic\nCP2K| version string: synthetic\n'
                'GLOBAL| Run type ENERGY\nSCF run converged in 5 steps\n'+line)
        if terminated:
            text += '\nPROGRAM ENDED AT synthetic\n'
        self.path.write_text(text)
        return line

    def test_whitespace_comments_and_numeric_forms_preserve_evidence(self):
        for token, value in (('-17.123', -17.123), ('0', 0.), ('+.25', .25),
                             ('-1.25D+01', -12.5), ('1.2e-3', .0012)):
            for suffix in ('', ' ', '   ', '\t', '  # synthetic annotation', '\ttrailing text'):
                with self.subTest(token=token, suffix=suffix):
                    line = self.output(token, suffix)
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
        for token in ('1.2broken', '1.2D+', '1.2D+3garbage', '1.2.3', '1e', '+', '.',
                      'NaN', 'Inf', '-Infinity', r'1.2\s'):
            with self.subTest(token=token):
                self.output(token)
                run = parse_output(self.path)
                self.assertIsNone(run.segments[0].final_energy)
                self.assertEqual(len(run.segments[0].unparsed_energy_records), 1)
                self.assertEqual(quality_report(run)['status'], 'not_passed')

    def test_energy_at_eof_does_not_infer_termination(self):
        self.output('-17.123', terminated=False)
        run = parse_output(self.path)
        self.assertEqual(run.segments[0].final_energy.value, -17.123)
        self.assertEqual(quality_report(run)['status'], 'not_passed')

    def test_strict_cli_and_overflow_exit_codes(self):
        for token, suffix, expected in (('-17.123', '\t', 0), ('1.2broken', '', 7), ('1e999', '', 4)):
            with self.subTest(token=token):
                self.output(token, suffix)
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(main(['report', str(self.path), '--strict']), expected)
        self.output('1e999')
        with self.assertRaises(ParseError):
            parse_output(self.path)
