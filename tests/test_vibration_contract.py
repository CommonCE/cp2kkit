"""Public synthetic generation contract; no native software or consumer repo."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from cp2kkit import __version__
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.structure import read_structure

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT/'examples'/'vibration-contract'


class VibrationContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = EXAMPLE/'water.xyz'
        self.original = self.source.read_bytes()
        self.structure = read_structure(self.source, frame=0)
        self.request = json.loads((EXAMPLE/'settings.json').read_text())
        self.settings = InputSettings.from_config(self.request)
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def assert_selected(self, actual, expected):
        if isinstance(expected, dict):
            self.assertIsInstance(actual, dict)
            for key, value in expected.items():
                self.assertIn(key, actual)
                self.assert_selected(actual[key], value)
        elif isinstance(expected, list):
            self.assertIsInstance(actual, list)
            self.assertEqual(len(actual), len(expected))
            for value, wanted in zip(actual, expected):
                self.assert_selected(value, wanted)
        else:
            self.assertIs(type(actual), type(expected))  # False is not zero.
            self.assertEqual(actual, expected)

    def cli(self, output, *extra, source=None):
        return subprocess.run(
            [sys.executable, '-m', 'cp2kkit', 'generate-input', str(source or self.source),
             '--frame', '0', '-o', str(output), '--project', 'vibration-contract',
             '--run-type', 'VIBRATIONAL_ANALYSIS', '--cp2k-version', '2026.2',
             '--method', 'DFT', '--functional', 'PBE', '--basis', 'molopt-sr-dzvp',
             '--periodic', 'NONE', '--charge', '0', '--scf', 'ot', '--ot-algorithm', 'STRICT',
             *extra],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, 'PYTHONPATH': str(ROOT/'src')})

    def test_example_selected_fields_types_and_runtime_provenance(self):
        text, manifest = generate_input(self.structure, self.settings)
        expected = json.loads((EXAMPLE/'expected-fields.json').read_text())
        exported = json.loads(json.dumps(manifest, allow_nan=False))
        self.assert_selected(exported, expected)
        self.assertEqual(manifest['generator']['version'], __version__)
        self.assertEqual(manifest['input_text'], text)
        self.assertEqual(manifest['input_sha256'], hashlib.sha256(text.encode('utf-8')).hexdigest())
        source = manifest['source_structure']['source']
        self.assertEqual(source['path'], str(self.source.resolve()))
        self.assertEqual(source['sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(source['size_bytes'], len(self.original))
        self.assertEqual((source['line_start'], source['line_end']), (1, 5))
        self.assertEqual((text, manifest), generate_input(self.structure, self.settings))
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_api_and_cli_publish_identical_input_and_json(self):
        api_output = self.root/'api.inp'
        output, sidecar, warnings = write_input(self.structure, self.settings, api_output)
        self.assertIsInstance(output, Path)
        self.assertEqual(output, api_output)
        self.assertEqual(sidecar, Path(str(api_output)+'.json'))
        self.assertTrue(warnings)
        cli_output = self.root/'cli.inp'
        result = self.cli(cli_output, '--write-json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(cli_output.read_bytes(), api_output.read_bytes())
        self.assertEqual(json.loads(Path(str(cli_output)+'.json').read_text()),
                         json.loads(sidecar.read_text()))
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_sidecar_replay_preserves_auto_origins_and_ignores_extra_metadata(self):
        text, manifest = generate_input(self.structure, self.settings)
        exported = json.loads(json.dumps(manifest))
        exported.pop('vibrational_analysis')  # Older producer metadata may be absent.
        exported['future_metadata'] = {'unrecognized': True}
        replayed = InputSettings.from_config(exported)
        actual, metadata = generate_input(self.structure, replayed)
        self.assertEqual(actual, text)
        self.assertEqual(metadata['vibrational_analysis'], manifest['vibrational_analysis'])
        self.assertIsNone(replayed.eps_scf)
        self.assertIsNone(replayed.vibration_displacement_bohr)
        self.assertIsNone(self.request['multiplicity'])
        self.assertEqual(manifest['settings']['multiplicity'], 1)  # Normalized settings.
        self.assertFalse(metadata['runtime_validated'])
        self.assertIsNone(metadata['runtime_version'])
        self.assertFalse(metadata['vibrational_analysis']['stationary_point_verified'])

    def test_absent_auto_and_explicit_parameters_are_distinct(self):
        auto_request = dict(self.request)
        auto_request.pop('vibration_displacement_bohr')
        auto_request.pop('eps_scf')
        auto = InputSettings.from_config(auto_request)
        _, auto_manifest = generate_input(self.structure, auto)
        explicit = replace(auto, vibration_displacement_bohr=.02, eps_scf=2e-9)
        _, explicit_manifest = generate_input(self.structure, explicit)
        vib = explicit_manifest['vibrational_analysis']
        self.assertEqual(vib['displacement_bohr'], .02)
        self.assertEqual(vib['eps_scf'], 2e-9)
        self.assertEqual(vib['displacement_origin'], 'user_explicit')
        self.assertEqual(vib['eps_scf_origin'], 'user_explicit')
        self.assertEqual(auto_manifest['vibrational_analysis']['displacement_origin'],
                         'native_default_explicit')
        self.assertEqual(auto_manifest['vibrational_analysis']['eps_scf_origin'], 'task_preset')
        self.assertEqual(InputSettings.from_config(explicit_manifest).vibration_displacement_bohr, .02)

    def test_invalid_requests_and_structures_do_not_publish(self):
        output = self.root/'invalid.inp'
        output.write_text('existing input')
        for options in (('--eps-scf', '1e-6'), ('--vibration-displacement-bohr', 'nan'),
                        ('--vibration-displacement-bohr', '0'), ('--scf', 'diag')):
            with self.subTest(options=options):
                result = self.cli(output, '--write-json', *options)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(output.read_text(), 'existing input')
                self.assertFalse(Path(str(output)+'.json').exists())
        damaged = self.root/'damaged.xyz'
        damaged.write_text('not an atom count\n')
        result = self.cli(output, '--write-json', source=damaged)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertEqual(output.read_text(), 'existing input')
        self.assertFalse(Path(str(output)+'.json').exists())
        for changes in ({'vibration_displacement_bohr': True}, {'eps_scf': float('inf')}):
            with self.subTest(changes=changes), self.assertRaises(KitError):
                write_input(self.structure, replace(self.settings, **changes), output)
        self.assertEqual(output.read_text(), 'existing input')

    def test_sidecar_collision_and_source_protection_have_distinct_errors(self):
        output = self.root/'collision.inp'
        output.write_text('old input')
        sidecar = Path(str(output)+'.json')
        sidecar.write_text('old metadata')
        with self.assertRaises(OutputExists):
            write_input(self.structure, self.settings, output)
        result = self.cli(output, '--write-json')
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertEqual(output.read_text(), 'old input')
        self.assertEqual(sidecar.read_text(), 'old metadata')
        copied_source = self.root/'source.xyz'
        copied_source.write_bytes(self.original)
        local_structure = read_structure(copied_source, frame=0)
        source_alias = self.root/'source-alias.inp'
        os.link(copied_source, source_alias)  # Test-owned files on one filesystem.
        with self.assertRaises(KitError) as caught:
            write_input(local_structure, self.settings, source_alias)
        self.assertEqual(caught.exception.code, 2)
        result = self.cli(source_alias, '--write-json', source=copied_source)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(source_alias.read_bytes(), self.original)
        self.assertEqual(copied_source.read_bytes(), self.original)
        self.assertFalse(Path(str(source_alias)+'.json').exists())

    def test_input_only_replacement_keeps_stale_sidecar_and_returns_none(self):
        output = self.root/'input-only.inp'
        output.write_text('replaceable input')
        sidecar = Path(str(output)+'.json')
        sidecar.write_text('stale metadata')
        returned, metadata, warnings = write_input(
            self.structure, replace(self.settings, write_json=False), output)
        self.assertEqual(returned, output)
        self.assertIsNone(metadata)
        self.assertEqual(sidecar.read_text(), 'stale metadata')
        self.assertTrue(any('sidecar' in warning for warning in warnings))
        self.assertEqual(output.read_text(), generate_input(self.structure, self.settings)[0])
        fresh = self.root/'cli-input-only.inp'
        result = self.cli(fresh)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(fresh.read_bytes(), output.read_bytes())
        self.assertFalse(Path(str(fresh)+'.json').exists())
