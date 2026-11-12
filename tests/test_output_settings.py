"""Hand-written format fixtures based on tagged CP2K printing routines, not runs."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

from cp2kkit import __version__
from cp2kkit.cli import main
from cp2kkit.parser import parse_output
from cp2kkit.quality import quality_report

HEADER = 'CP2K| version string: synthetic\nGLOBAL| Run type  GEO_OPT\n'
UKS = 'DFT| Spin unrestricted (spin-polarized) Kohn-Sham calculation'
RKS = 'DFT| Spin restricted Kohn-Sham (RKS) calculation'
ROKS = 'DFT| Spin restricted open Kohn-Sham calculation'


def setting(label, value):
    # CP2K writes labels at column 2 and right-aligned values near column 80.
    return ' ' + label.ljust(60) + str(value).rjust(19) + '\n'


class OutputSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'synthetic.out'

    def parse(self, text):
        self.path.write_text(HEADER + text)
        return parse_output(self.path)

    def test_exact_printed_fields_preserve_zero_and_line_evidence(self):
        run = self.parse(setting('DFT| Charge', 0) + setting('DFT| Multiplicity', 3)
                         + setting(UKS, 'UKS') + setting('QS| Method:', 'GPW'))
        seg = run.segments[0]
        fields = seg.normalized_settings
        for name, expected in [('charge', 0), ('multiplicity', 3), ('uks', True),
                               ('spin_treatment', 'UKS'), ('qs_method', 'GPW')]:
            with self.subTest(name=name):
                self.assertEqual(fields[name]['value'], expected)
                self.assertEqual(fields[name]['status'], 'parsed')
                self.assertEqual(fields[name]['sources'][0]['path'], str(self.path.resolve()))
        self.assertEqual(fields['charge']['unit'], 'elementary_charge')
        self.assertEqual(fields['charge']['sources'][0]['line'], 3)
        self.assertEqual(seg.settings['DFT|Charge']['value'], '0')
        self.assertEqual(len(seg.settings_records), 5)  # includes GLOBAL run type
        self.assertEqual(seg.settings_records[1]['source'], fields['charge']['sources'][0])
        self.assertEqual(run.to_dict(), parse_output(self.path).to_dict())

    def test_spin_branches_are_not_multiplicity_or_magnetization(self):
        for label, spin, uks in [(UKS, 'UKS', True), (RKS, 'RKS', False), (ROKS, 'ROKS', False)]:
            with self.subTest(spin=spin):
                seg = self.parse(setting(label, spin)).segments[0]
                self.assertEqual(seg.normalized_settings['uks']['value'], uks)
                self.assertEqual(seg.normalized_settings['spin_treatment']['value'], spin)
                self.assertIsNone(seg.normalized_settings['multiplicity']['value'])
        seg = self.parse(setting('DFT| Multiplicity', 1)
                         + setting('DFT| Number of spin states', 2)
                         + setting('DFT| Total magnetization', 1)
                         + setting('DFT| Electron number difference', 1)).segments[0]
        self.assertIsNone(seg.normalized_settings['uks']['value'])
        self.assertIsNone(seg.normalized_settings['charge']['value'])
        self.assertNotIn('magnetization', seg.normalized_settings)

    def test_absent_fields_are_missing_not_defaults(self):
        fields = self.parse('').segments[0].normalized_settings
        self.assertEqual(set(fields), {'charge', 'multiplicity', 'uks', 'spin_treatment', 'qs_method'})
        for field in fields.values():
            self.assertIsNone(field['value'])
            self.assertEqual(field['status'], 'missing')
            self.assertEqual(field['sources'], [])

    def test_unsupported_tokens_do_not_prefix_parse_or_fill_defaults(self):
        cases = [('DFT| Charge', 'charge', ['0.0', 'NaN', '1e999', '1junk', '--1']),
                 ('DFT| Multiplicity', 'multiplicity', ['0', '-1', '2.5', 'auto']),
                 ('QS| Method:', 'qs_method', ['XTB', 'UNKNOWN', 'GPW trailing']),
                 (UKS, 'spin_treatment', ['T', 'RKS', 'unknown'])]
        for label, name, values in cases:
            for value in values:
                with self.subTest(label=label, value=value):
                    run = self.parse(setting(label, value))
                    field = run.segments[0].normalized_settings[name]
                    self.assertIsNone(field['value'])
                    self.assertEqual(field['status'], 'unsupported')
                    self.assertIn(value, field['sources'][0]['text'])
                    self.assertTrue(any(f'setting {name}' in w for w in run.parser_warnings))

    def test_conflicts_and_repetitions_preserve_all_raw_records(self):
        run = self.parse(setting('DFT| Charge', 0) + setting('DFT| Charge', 1)
                         + setting(RKS, 'RKS') + setting(UKS, 'UKS'))
        seg = run.segments[0]
        self.assertEqual(seg.settings['DFT|Charge']['value'], '1')  # legacy last-write behavior
        for name in ['charge', 'spin_treatment', 'uks']:
            field = seg.normalized_settings[name]
            self.assertEqual(field['status'], 'conflicting')
            self.assertIsNone(field['value'])
            self.assertEqual(len(field['sources']), 2)
        seg = self.parse(setting('DFT| Charge', '+1') + setting('DFT| Charge', '1')).segments[0]
        self.assertEqual(seg.normalized_settings['charge']['value'], 1)
        self.assertEqual(len(seg.normalized_settings['charge']['sources']), 2)
        seg = self.parse(setting('DFT| Charge', '0') + setting('DFT| Charge', 'bad')).segments[0]
        self.assertEqual(seg.normalized_settings['charge']['status'], 'unsupported')
        self.assertIsNone(seg.normalized_settings['charge']['value'])

    def test_method_is_only_qs_representation_not_an_xc_model(self):
        run = self.parse(setting('QS| Method:', 'GAPW') + setting('XC| Functional', 'PBE'))
        seg = run.segments[0]
        self.assertEqual(seg.normalized_settings['qs_method']['value'], 'GAPW')
        self.assertEqual(seg.settings['XC|Functional']['value'], 'PBE')
        self.assertNotIn('method', seg.normalized_settings)
        seg = self.parse(setting('XC| Functional', 'PBE')).segments[0]
        self.assertIsNone(seg.normalized_settings['qs_method']['value'])

    def test_segment_resets_and_starts_do_not_inherit_settings(self):
        for boundary in ['OPTIMIZATION STEP: 1\n', 'PROGRAM STARTED AT synthetic\n']:
            with self.subTest(boundary=boundary):
                prefix = 'PROGRAM STARTED AT synthetic\n' if boundary.startswith('PROGRAM') else ''
                run = self.parse(prefix + setting('DFT| Charge', -1) + 'OPTIMIZATION STEP: 1\n' + boundary)
                self.assertEqual(len(run.segments), 2)
                self.assertEqual(run.segments[0].normalized_settings['charge']['value'], -1)
                self.assertIsNone(run.segments[1].normalized_settings['charge']['value'])
                self.assertEqual(run.segments[1].settings_records, [])

    def test_settings_after_end_do_not_contaminate_completed_segment(self):
        run = self.parse(setting('DFT| Charge', 0) + 'PROGRAM ENDED AT synthetic\n'
                         + setting('DFT| Charge', 1))
        self.assertEqual(len(run.segments), 2)
        self.assertEqual(run.segments[0].normalized_settings['charge']['value'], 0)
        self.assertEqual(run.segments[1].normalized_settings['charge']['value'], 1)
        self.assertFalse(run.segments[1].completed)

    def test_settings_are_not_scientific_quality_certification(self):
        run = self.parse(setting('DFT| Charge', 0) + setting('DFT| Charge', 1)
                         + 'OPTIMIZATION STEP: 1\nSCF run converged in 2 steps\n'
                         + 'ENERGY| Total FORCE_EVAL ( QS ) energy [hartree] -1\n'
                         + 'GEOMETRY OPTIMIZATION COMPLETED\nPROGRAM ENDED AT synthetic\n')
        self.assertEqual(run.segments[0].normalized_settings['charge']['status'], 'conflicting')
        self.assertEqual(quality_report(run)['status'], 'passed')  # text checks, not model validation

    def test_cli_exports_new_fields_and_legacy_raw_settings(self):
        self.parse(setting('DFT| Charge', 0) + setting(RKS, 'RKS'))
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = main(['parse', str(self.path), '--format', 'json'])
        self.assertEqual(status, 0)
        data = json.loads(stdout.getvalue())
        seg = data['segments'][0]
        self.assertEqual(data['schema_version'], '0.1.0')
        self.assertEqual(data['parser']['version'], __version__)
        self.assertIs(seg['normalized_settings']['uks']['value'], False)
        self.assertEqual(seg['settings']['DFT|Charge']['value'], '0')
        self.assertEqual(seg['normalized_settings']['charge']['value'], 0)
        self.assertEqual(len(seg['settings_records']), 3)
