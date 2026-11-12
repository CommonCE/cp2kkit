"""Public contract checks using hand-written strings, never CP2K calculations."""
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
from cp2kkit.structure import read_structure

HEADER = ('CP2K| version string: synthetic\nPROGRAM STARTED AT synthetic\n'
          'GLOBAL| Run type GEO_OPT\n')
STEP = 'OPTIMIZATION STEP: 1\n'
SCF = 'SCF run converged in 4 steps\n'
ENERGY = 'ENERGY| Total FORCE_EVAL ( QS ) energy [hartree] -1.0\n'
END = 'GEOMETRY OPTIMIZATION COMPLETED\nPROGRAM ENDED AT synthetic\n'


class GeoOptContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'synthetic.out'

    def parse(self, body):
        self.path.write_text(HEADER + body)
        return parse_output(self.path)

    def test_complete_observation_is_not_a_final_state_claim(self):
        run = self.parse(STEP + SCF + ENERGY + END)
        data = run.to_dict()
        segment = data['segments'][0]
        observed = segment['last_observed_energy']
        self.assertEqual(data['parser'], {'name': 'cp2kkit', 'version': __version__})
        self.assertEqual(data['schema_version'], '0.1.0')
        self.assertEqual(data['software_version'], 'synthetic')
        self.assertEqual(observed['quantity'], segment['final_energy'])
        self.assertEqual((observed['segment'], observed['index'], observed['step']), (0, 1, 1))
        self.assertEqual(observed['scf_source']['line'], 5)
        self.assertEqual(observed['step_source']['line'], 4)
        self.assertEqual(observed['scf_association'], 'preceding_summary')
        self.assertEqual(observed['quantity']['source']['line'], 6)
        self.assertIsNone(data['exit_status'])
        self.assertNotIn('final_candidate_energy', segment)
        self.assertEqual(quality_report(run)['status'], 'passed')
        self.assertEqual(data['source']['path'], str(self.path.resolve()))
        self.assertEqual(data['source']['size_bytes'], len(self.path.read_bytes()))
        self.assertEqual(data['source']['sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(data, parse_output(self.path).to_dict())

    def test_failure_and_unknown_states_remain_independent(self):
        cases = {
            'truncated': (STEP + SCF + ENERGY, False, True, None, True),
            'scf_failure': (STEP + 'SCF run NOT converged\n' + ENERGY + END,
                            True, False, True, True),
            'exhausted': (STEP + SCF + ENERGY + 'MAXIMUM NUMBER OF OPTIMIZATION STEPS\n' + END,
                          True, True, False, True),
            'no_energy': (STEP + SCF + END, True, True, True, False),
            'unknown_scf': (STEP + ENERGY + END, True, None, True, True),
        }
        for name, (body, completed, scf, geometry, has_energy) in cases.items():
            with self.subTest(name=name):
                run = self.parse(body)
                seg = run.segments[0]
                self.assertEqual(seg.completed, completed)
                self.assertEqual(seg.scf_converged, scf)
                self.assertEqual(seg.geometry_converged, geometry)
                self.assertEqual(seg.last_observed_energy is not None, has_energy)
                self.assertFalse(quality_report(run)['segments'][0]['energy_usable'])

    def test_damaged_tail_retains_observation_and_context(self):
        bad = ENERGY.replace('-1.0', '-2.0broken')
        run = self.parse(STEP + SCF + ENERGY + 'OPTIMIZATION STEP: 2\n' + SCF + bad + END)
        seg = run.segments[0]
        self.assertEqual(seg.last_observed_energy.step, 1)
        self.assertEqual(seg.final_energy.value, -1.)
        context = seg.unparsed_energy_context[0]
        self.assertEqual(context['step'], 2)
        self.assertEqual(context['scf_evidence'][0]['line'], 8)
        self.assertEqual(context['source'], seg.unparsed_energy_records[0].__dict__)
        self.assertTrue(run.parser_warnings)
        self.assertFalse(quality_report(run)['segments'][0]['energy_usable'])

    def test_bad_record_consumes_scf_and_bad_record_after_end_splits(self):
        bad = ENERGY.replace('[hartree]', '[eV]')
        run = self.parse(STEP + SCF + bad + ENERGY + END + bad)
        self.assertEqual(len(run.segments), 2)
        self.assertIsNone(run.segments[0].last_observed_energy.scf_source)
        self.assertIsNone(run.segments[0].last_observed_energy.scf_converged)
        self.assertFalse(run.segments[1].completed)
        self.assertEqual(len(run.segments[1].unparsed_energy_records), 1)

    def test_multiple_summaries_do_not_claim_unique_association(self):
        run = self.parse(STEP + SCF + SCF + ENERGY + END)
        observed = run.segments[0].last_observed_energy
        self.assertEqual(observed.scf_association, 'ambiguous')
        self.assertIsNone(observed.scf_source)
        self.assertEqual(len(observed.scf_evidence), 2)
        self.assertFalse(quality_report(run)['segments'][0]['energy_usable'])

    def test_resets_and_concatenation_do_not_merge_settings_or_scf(self):
        body = ('DFT| Charge  0\nXC| Functional  PBE\n' + STEP + SCF + ENERGY
                + STEP + ENERGY + END + HEADER + STEP + ENERGY + END)
        run = self.parse(body)
        self.assertEqual(len(run.segments), 3)
        self.assertIn('DFT|Charge', run.segments[0].settings)
        self.assertEqual(run.segments[0].settings['DFT|Charge']['value'], '0')
        self.assertEqual(run.segments[1].settings, {})
        for segment in run.segments[1:]:
            self.assertIsNone(segment.last_observed_energy.scf_source)
        self.assertTrue(any('no inferred restart continuity' in w for w in run.parser_warnings))

    def test_structure_reader_does_not_establish_output_association(self):
        xyz = Path(self.tmp.name) / 'synthetic-pos.xyz'
        xyz.write_text('1\ni = 1, E = -1\nHe 0 0 0\n1\ni = 2, E = -2\nHe 1 0 0\n')
        structure = read_structure(xyz, frame=1).to_dict()
        self.assertEqual(structure['frame'], 1)
        self.assertEqual(structure['coordinate_unit'], 'angstrom')
        self.assertIsNone(structure['cell'])
        self.assertIsNone(structure['pbc'])
        self.assertEqual(structure['source']['sha256'], hashlib.sha256(xyz.read_bytes()).hexdigest())
        self.assertNotIn('step', structure)
        run = self.parse(STEP + SCF + ENERGY + END)
        self.assertNotIn('structure', run.to_dict())

    def test_public_cli_json(self):
        self.parse(STEP + SCF + ENERGY + END)
        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, 'PYTHONPATH': str(root / 'src')}
        result = subprocess.run([sys.executable, '-m', 'cp2kkit', 'parse', str(self.path),
                                 '--format', 'json'], env=env, capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['segments'][0]['last_observed_energy']['step'], 1)
        self.assertEqual(data['quality']['status'], 'passed')
        self.assertIsNone(data['exit_status'])
