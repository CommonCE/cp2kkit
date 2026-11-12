"""Public, synthetic observation baseline; no consumer models or calculations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cp2kkit import __version__
from cp2kkit.parser import parse_output
from cp2kkit.quality import quality_report

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples' / 'geo-opt-contract'


class ContractExampleTests(unittest.TestCase):
    def assert_selected_fields(self, actual, expected, location='$'):
        """Check documented fields without freezing unknown future additions."""
        if isinstance(expected, dict):
            self.assertIsInstance(actual, dict, location)
            for key, value in expected.items():
                self.assertIn(key, actual, location)
                self.assert_selected_fields(actual[key], value, f'{location}.{key}')
        elif isinstance(expected, list):
            self.assertIsInstance(actual, list, location)
            self.assertEqual(len(actual), len(expected), location)
            for index, (value, wanted) in enumerate(zip(actual, expected)):
                self.assert_selected_fields(value, wanted, f'{location}[{index}]')
        else:
            # In particular, false must not compare equal to numerical zero.
            self.assertIs(type(actual), type(expected), location)
            self.assertEqual(actual, expected, location)

    def test_public_example_matches_selected_contract_fields(self):
        path = EXAMPLE / 'observation.txt'
        data = parse_output(path).to_dict()
        expected = json.loads((EXAMPLE / 'expected-fields.json').read_text())
        self.assert_selected_fields(data, expected)
        self.assertEqual(data['parser']['version'], __version__)
        self.assertEqual(data['source'], {
            'path': str(path.resolve()), 'size_bytes': len(path.read_bytes()),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        })
        segment = data['segments'][0]
        self.assertEqual(segment['last_observed_energy'], segment['energies'][0])
        self.assertEqual(segment['final_energy'], segment['energies'][0]['quantity'])
        self.assertEqual(len(segment['settings_records']), 5)
        for record in segment['settings_records']:
            self.assertEqual(record['source']['path'], str(path.resolve()))
        self.assertEqual(quality_report(parse_output(path))['status'], 'passed')

    def test_legacy_fields_remain_present(self):
        data = parse_output(EXAMPLE / 'observation.txt').to_dict()
        self.assertTrue({
            'schema_version', 'software', 'software_version', 'project', 'source',
            'segments', 'settings', 'parser_warnings', 'exit_status',
        } <= data.keys())
        self.assertTrue({
            'id', 'started', 'completed', 'scf_converged', 'geometry_converged',
            'run_type', 'evidence', 'energies', 'scf_iterations', 'final_energy',
            'wall_time', 'diagnostics', 'unparsed_energy_records', 'settings',
        } <= data['segments'][0].keys())
        self.assertTrue({'segment', 'index', 'step', 'quantity', 'scf_converged'}
                        <= data['segments'][0]['energies'][0].keys())

    def test_missing_and_conflicting_settings_do_not_become_defaults(self):
        original = (EXAMPLE / 'observation.txt').read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'observation.txt'
            for body, status in [
                (original.replace('DFT| Charge  0\n', ''), 'missing'),
                (original.replace('DFT| Charge  0\n', 'DFT| Charge  0\nDFT| Charge  1\n'),
                 'conflicting'),
            ]:
                with self.subTest(status=status):
                    path.write_text(body)
                    run = parse_output(path)
                    charge = run.to_dict()['segments'][0]['normalized_settings']['charge']
                    self.assertIsNone(charge['value'])
                    self.assertEqual(charge['status'], status)
                    self.assertEqual(len(charge['sources']), 0 if status == 'missing' else 2)
                    # Text quality is independent of settings identity.
                    self.assertEqual(quality_report(run)['status'], 'passed')

    def test_cli_matches_api_and_strict_report_rejects_truncation(self):
        original = (EXAMPLE / 'observation.txt').read_text()
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'observation.txt'
            for truncated in (False, True):
                with self.subTest(truncated=truncated):
                    path.write_text(original.split('GEOMETRY OPTIMIZATION COMPLETED')[0]
                                    if truncated else original)
                    before = path.read_bytes()
                    result = subprocess.run(
                        [sys.executable, '-m', 'cp2kkit', 'parse', str(path), '--format', 'json'],
                        env=env, capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    exported = json.loads(result.stdout)
                    run = parse_output(path)
                    self.assertEqual(exported.pop('quality'), quality_report(run))
                    self.assertEqual(exported, run.to_dict())
                    strict = subprocess.run(
                        [sys.executable, '-m', 'cp2kkit', 'report', str(path), '--strict'],
                        env=env, capture_output=True, text=True, timeout=10)
                    self.assertEqual(strict.returncode, 7 if truncated else 0, strict.stderr)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(list(Path(directory).iterdir()), [path])
