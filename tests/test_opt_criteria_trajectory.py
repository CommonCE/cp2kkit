"""Synthetic optimization and trajectory contracts; no CP2K or X11 execution."""
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import patch

from cp2kkit import __version__
from cp2kkit.cli import main
from cp2kkit.errors import AmbiguousProject, KitError, ParseError
from cp2kkit.main_tui import run_main_menu
from cp2kkit.parser import parse_output
from cp2kkit.plot import _convergence_axes
from cp2kkit.quality import quality_report
from cp2kkit.structure import read_structure, read_xyz
from cp2kkit.trajectory import match_trajectory, parse_trajectory_comment, select_matched_frame
from cp2kkit.viewer import view_matched_structure
from tests.test_interface_operations import TTY
from tests.test_viewer_integration import _make_mock_viewer, _read_invocations

HEADER = 'CP2K| version string: synthetic 2026.2\nPROGRAM STARTED AT synthetic\nGLOBAL| Run type GEO_OPT\n'
SCF = 'SCF run converged in 4 steps\n'
END = 'GEOMETRY OPTIMIZATION COMPLETED\nPROGRAM ENDED AT synthetic\n'
LABELS = ('Maximum step size', 'RMS step size', 'Maximum gradient', 'RMS gradient')
LATTICE = 'Lattice="4 0 0 0 4 0 0 0 4" pbc="T T T" Properties=species:S:1:pos:R:3'


def force_eval(value):
    return SCF + f'ENERGY| Total FORCE_EVAL ( QS ) energy [hartree] {value}\n'


def criteria(flag='YES', value='0.0001'):
    return ''.join(f' OPT| {label} {value}\n OPT| Convergence limit for {label} 0.001\n'
                   f' OPT| {label} is converged {flag}\n' for label in LABELS)


def evaluation(step, value, records=''):
    return (f'OPTIMIZATION STEP: {step}\n' + force_eval(value)
            + f'OPT| Step number {step}\nOPT| Optimization method LBFGS\n'
              f'OPT| Total energy [hartree] {value}\n' + records)


def xyz_frame(comment, coordinate=0):
    return f'1\n{comment}\nHe {coordinate} 0 0\n'


class OptimizationTrajectoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.out = self.root / 'opt.out'
        self.xyz = self.root / 'pos.xyz'
        self.body = (force_eval(-1) + 'OPT| Step number 0\nOPT| Total energy [a.u.] -1\n'
                     + evaluation(1, -2, criteria('NO')) + evaluation(2, -3, criteria('NO'))
                     + evaluation(3, -4, criteria(value='0.0')))
        self.out.write_text(HEADER + self.body + END)
        self.xyz.write_text(''.join(xyz_frame(f'i = {i}, time = 0.0, E = {-1-i}', i) for i in range(5)))

    def parse(self, body, *, cell=False):
        self.out.write_text((HEADER.replace('GEO_OPT', 'CELL_OPT') if cell else HEADER) + body)
        return parse_output(self.out)

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(list(map(str, args)))
        return code, stdout.getvalue(), stderr.getvalue()

    def match_cli(self, *args):
        return self.cli('match-trajectory', self.out, self.xyz, *args)

    def tui(self, *commands):
        log = TTY()
        with patch('cp2kkit.presentation.shutil.get_terminal_size', return_value=os.terminal_size((132, 30))):
            code = run_main_menu(stdin=TTY('\n'.join(map(str, commands)) + '\n'), stdout=log, plain=True)
        self.assertEqual(code, 0, log.getvalue())
        return log.getvalue()

    def test_opt_zero_banners_flags_and_evidence(self):
        run = parse_output(self.out)
        self.assertEqual(len(run.segments), 1)
        seg = run.segments[0]
        self.assertEqual([e.step for e in seg.energies], [None, 1, 2, 3])
        self.assertEqual([o.step for o in seg.optimization_steps], [0, 1, 2, 3])
        zero, first, _, last = seg.optimization_steps
        self.assertEqual((zero.energy_hartree, zero.index), (-1.0, 1))
        self.assertIsNone(zero.all_observed_converged)
        self.assertFalse(first.all_cartesian_converged)
        self.assertIs(seg.last_optimization_step, last)
        self.assertEqual(last.method, 'LBFGS')
        self.assertTrue(last.all_observed_converged)
        self.assertEqual(last.max_step.value, 0.0)
        self.assertEqual(last.max_step.unit, 'bohr')
        self.assertEqual(last.max_gradient.unit, 'hartree/bohr')
        self.assertIn('Maximum step size 0.0', last.max_step.source.text)
        self.assertIn('limit', last.max_step.limit_source.text)
        self.assertIn('YES', last.max_step.converged_source.text)
        quality = quality_report(run)['segments'][0]
        self.assertEqual((quality['optimization_step_count'], quality['status']), (4, 'passed'))

    def test_cell_pressure_and_missing_pressure(self):
        pressure = ('OPT| Internal pressure [bar] -2.5D+0\nOPT| Pressure deviation [bar] 0.0\n'
                    'OPT| Pressure tolerance [bar] 10\nOPT| Conv. for PRESSURE YES\n')
        run = self.parse(evaluation(1, -1, criteria() + pressure) + END, cell=True)
        opt = run.segments[0].last_optimization_step
        self.assertEqual((opt.internal_pressure_bar, opt.pressure.unit, opt.pressure.value), (-2.5, 'bar', 0))
        self.assertTrue(opt.all_observed_converged)
        run = self.parse(evaluation(1, -1, criteria()) + END, cell=True)
        opt = run.segments[0].last_optimization_step
        self.assertTrue(opt.all_cartesian_converged)
        self.assertIsNone(opt.all_observed_converged)

    def test_legacy_and_partial_sources(self):
        records = ('Convergence check : Max. step size = 0.002\nConv. limit for step size = 0.1\n'
                   'Convergence in step size = YES\n'
                   'RMS step size = 0.0\nConv. limit for RMS step = 0.1\nConvergence in RMS step = YES\n'
                   'Max. gradient = 0.02\nConv. limit for gradients = 0.1\nConv. for gradients = NO\n'
                   'RMS gradient = 0.05\nConv. limit for RMS grad. = 0.1\nConv. for RMS grad. = YES\n'
                   'Internal Pressure [bar] = -4\nPressure Deviation [bar] = 1\n'
                   'Pressure Tolerance [bar] = 3\nConv. for PRESSURE = YES\n')
        run = self.parse(records, cell=True)
        opt = run.segments[0].last_optimization_step
        self.assertIsNone(opt.step)
        self.assertEqual(opt.max_step.value, 0.002)
        self.assertIn('Convergence check', opt.max_step.source.text)
        self.assertFalse(opt.all_observed_converged)
        self.assertEqual((opt.pressure.value, opt.pressure.limit, opt.internal_pressure_bar), (1, 3, -4))
        # Missing value retains limit_source as primary source evidence.
        run = self.parse('Conv. limit for step size = 0.1\nConvergence in step size = YES\n')
        partial = run.segments[0].last_optimization_step
        self.assertIsNone(partial.max_step.value)
        self.assertEqual(partial.max_step.source, partial.max_step.limit_source)
        run = self.parse(evaluation(1, -1, 'OPT| Maximum gradient is converged YES\n') + END)
        self.xyz.write_text(xyz_frame('i = 1, E = -1'))
        self.assertEqual(quality_report(run)['status'], 'passed')
        self.assertIsNone(match_trajectory(run, self.xyz).converged_final_step)

    def test_malformed_and_unrepresentable_criteria(self):
        bad = ('OPT| Maximum step size 0.001broken\nOPT| Convergence limit for RMS step size NaN\n'
               'OPT| Maximum gradient Inf\nOPT| RMS gradient is converged MAYBE\n'
               'OPT| Pressure deviation [bar]\n')
        run = self.parse(evaluation(1, -1, bad) + END)
        seg = run.segments[0]
        opt = seg.last_optimization_step
        self.assertEqual(len(seg.unparsed_optimization_records), 5)
        for evidence in seg.unparsed_optimization_records:
            self.assertTrue(any(f'line {evidence.line}' in w for w in run.parser_warnings))
        self.assertTrue(all(value is None for value in (opt.max_step.value, opt.rms_step.limit,
                                                       opt.max_gradient.value, opt.rms_gradient.converged,
                                                       opt.pressure.value)))
        self.assertIn('Unsupported or malformed optimization criteria record in segment',
                      quality_report(run)['segments'][0]['reasons'])
        for token in ('1e999', '1d-999'):
            with self.subTest(token=token), self.assertRaises(ParseError):
                self.parse(evaluation(1, -1, f'OPT| Maximum step size {token}\n'))

    def test_quality_contradiction_last_criteria_and_incomplete(self):
        run = self.parse(evaluation(1, -1, criteria('NO')) + evaluation(2, -2) + END)
        report = quality_report(run)['segments'][0]
        self.assertTrue(report['geometry_converged'])
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['last_optimization_criteria']['step'], 1)
        self.assertIn('Observed optimization criteria are not converged despite completion marker', report['reasons'])
        run = self.parse(evaluation(1, -1, criteria()))
        self.assertTrue(run.segments[0].last_optimization_step.all_observed_converged)
        self.assertNotEqual(quality_report(run)['status'], 'passed')

    def test_reset_repeat_decrease_and_post_termination(self):
        for second in ('OPT| Step number 2\n', 'OPT| Step number 1\n', 'OPTIMIZATION STEP: 2\n'):
            with self.subTest(second=second):
                run = self.parse(evaluation(2, -2) + second)
                self.assertEqual(len(run.segments), 2)
                self.assertTrue(any('no inferred restart continuity' in w for w in run.parser_warnings))
        for line in ('OPT| Maximum gradient 1\n', 'Max. gradient = 1\n', 'OPT| Total energy [hartree] -1\n'):
            with self.subTest(line=line):
                run = self.parse(evaluation(1, -1) + END + line)
                self.assertEqual([s.completed for s in run.segments], [True, False])
                self.assertIsNone(run.segments[1].last_optimization_step.step)

    def test_comment_tokens_quotes_aliases_and_overflow(self):
        source = {'source_path': self.xyz, 'line': 9}
        self.assertEqual(parse_trajectory_comment('i = 0, time = 1D-2, E = 0.0', **source), (0, 0, []))
        self.assertEqual(parse_trajectory_comment('Note="Step=7 Energy=2" Step=1 energy=-3', **source), (1, -3, []))
        self.assertEqual(parse_trajectory_comment('Note=\'i = 8\' E=-1', **source), (None, -1, []))
        for comment in ('i=bad E=NaN', 'i=1broken E=1broken', 'i= E=Inf',
                        'i=1 Step=5 E=', 'i=1"broken" E=2"broken"'):
            with self.subTest(comment=comment):
                step, energy, warnings = parse_trajectory_comment(comment, **source)
                self.assertEqual((step, energy), (None, None))
                self.assertTrue(all(':9' in w for w in warnings))
                self.assertEqual(len(warnings), 2)
        for token in ('1e999', '1e-999'):
            with self.assertRaises(ParseError):
                parse_trajectory_comment(f'E={token}', **source)

    def test_cp2k_2026_2_extxyz_time_metadata(self):
        comment = ('Lattice="4 0 0 0 4 0 0 0 4" Properties=species:S:1:pos:R:3 pbc="T T T" '
                   'Step=9 Time=0.000 Energy=-32.0758315957')
        source = {'source_path': self.xyz, 'line': 2}
        expected = (9, -32.0758315957)
        self.assertEqual(parse_trajectory_comment(comment, **source), (*expected, []))
        for text, issue in ((comment.replace('Time=0.000', 'Time=NaN'), 'Malformed'),
                            (comment + ' Time=0.000', 'Duplicate'),
                            (comment + ' time=0.000', 'Duplicate')):
            with self.subTest(text=text):
                step, energy, warnings = parse_trajectory_comment(text, **source)
                self.assertEqual((step, energy), expected)
                self.assertEqual(warnings, [f'{issue} trajectory time metadata at {self.xyz}:2'])

    def test_matching_exact_xyz_extxyz_and_extra_frame(self):
        report = match_trajectory(self.out, self.xyz)
        self.assertTrue(report.strict_passed)
        self.assertEqual([m['status'] for m in report.matches], ['matched'] * 4)
        self.assertEqual(report.matches[0]['output_energy_count'], 0)
        self.assertEqual(report.matches[0]['output_energy_selection'], 'opt_summary')
        self.assertEqual(report.matches[1]['output_energy_selection'], 'force_eval')
        self.assertIsNone(report.output_atom_count)
        self.assertEqual(report.output_atom_count_sources, [])
        self.assertIsNone(report.matches[0]['atom_count_matches'])
        self.assertIn('[a.u.]', report.matches[0]['output_energy_source']['text'])
        self.assertEqual(report.unmatched_trajectory_frames[0]['trajectory_step'], 4)
        self.assertTrue(report.warnings)
        frame, match = select_matched_frame(report)
        self.assertEqual((frame.frame_index, match['step'], match['energy_diff_hartree']), (3, 3, 0))
        self.assertEqual(frame.structure, read_xyz(self.xyz, frame=3))
        self.assertEqual(read_structure(self.xyz).frame, 4)
        ext = self.root / 'pos.extxyz'
        ext.write_text(xyz_frame(LATTICE + ' Step=3 Energy=-4', 3))
        report = match_trajectory(self.out, ext)
        data = report.to_dict()
        self.assertEqual((data['schema_version'], data['operation']), ('0.1.0', 'trajectory_step_match'))
        self.assertEqual(data['frames'][0]['line_end'], 3)
        self.assertNotIn('structure', data['frames'][0])
        self.assertTrue(data['frames'][0]['has_cell'])
        self.assertTrue(data['frames'][0]['has_pbc'])
        self.assertTrue(data['strict_passed'])  # Earlier output steps need not have frames.

    def test_unavailable_mismatch_duplicate_missing_and_no_fallback(self):
        run = self.parse(self.body + 'OPTIMIZATION STEP: 4\n' + END)
        self.xyz.write_text(xyz_frame('i = 0, E = -1') + xyz_frame('i = 1, E = -1')
                            + xyz_frame('i = 2') + xyz_frame('i = 3, E = -4') * 2
                            + xyz_frame('i = 4, E = -5') + xyz_frame('arbitrary comment')
                            + xyz_frame('i = 99, E = -6'))
        report = match_trajectory(run, self.xyz, requested_step=0)
        self.assertFalse(report.strict_passed)
        self.assertEqual(report.duplicate_trajectory_steps, [{'step': 3, 'frame_indices': [3, 4]}])
        self.assertEqual(report.frames_missing_step[0]['frame_index'], 6)
        self.assertEqual([m['status'] for m in report.matches], ['matched', 'energy_mismatch',
                         'energy_unavailable_in_trajectory', 'energy_unavailable_in_output'])
        self.assertEqual(report.matches[1]['energy_diff_hartree'], 1)
        self.assertEqual(report.matches[-1]['output_energy_selection'], 'unavailable')
        for step, reason in ((None, 'Converged final step unavailable'), (1, 'energy mismatch'),
                             (2, 'energy unavailable in trajectory'), (3, 'duplicate in trajectory'),
                             (4, 'energy unavailable in output'), (99, 'missing from output')):
            with self.subTest(step=step), self.assertRaisesRegex(KitError, reason):
                select_matched_frame(report, step=step)
        self.assertEqual(select_matched_frame(report, step=0)[0].frame_index, 0)
        self.assertEqual(report.converged_final_status, 'unavailable')

    def test_tolerance_boundary_and_refusal_when_the_candidate_mismatches(self):
        self.xyz.write_text(xyz_frame('i = 3, E = -3.875') + xyz_frame('i = 4, E = -5'))
        report = match_trajectory(self.out, self.xyz, energy_tol_hartree=0.125)
        self.assertTrue(report.strict_passed)
        self.assertEqual(report.converged_final_step['energy_diff_hartree'], 0.125)
        report = match_trajectory(self.out, self.xyz, energy_tol_hartree=0.0)
        self.assertFalse(report.strict_passed)
        self.assertIsNone(report.converged_final_step)
        self.assertIn('Step 3: energy mismatch', report.converged_final_reasons)
        self.assertEqual(report.unmatched_output_steps[0], {'step': 0, 'reason': 'missing_in_trajectory'})
        self.assertEqual(self.match_cli('--strict')[0], 7)

    def test_repeated_force_eval_must_agree_pairwise(self):
        for same, repeated in ((True, -4.0000005), (False, -4.000002)):
            with self.subTest(same=same):
                run = self.parse(self.body + force_eval(repeated) + END)
                report = match_trajectory(run, self.xyz)
                final = report.matches[-1]
                self.assertEqual(final['output_energy_count'], 2)
                self.assertEqual(final['output_energy_ambiguous'], not same)
                self.assertEqual(final['output_energy_selection'], 'force_eval' if same else 'ambiguous')
                self.assertEqual(final['output_energy_hartree'], -4 if same else None)
                self.assertEqual(final['status'], 'matched' if same else 'energy_unavailable_in_output')
                self.assertEqual(report.converged_final_step is not None, same)
        run = self.parse(self.body + force_eval(-4.0000008) + force_eval(-3.9999992) + END)
        self.assertTrue(match_trajectory(run, self.xyz).matches[-1]['output_energy_ambiguous'])

    def test_cell_opt_line_search_requires_preceding_agreement_and_no_later_conflict(self):
        ext = self.root / 'pos.extxyz'
        accepted = -32.0758315957
        ext.write_text(xyz_frame(LATTICE + f' Step=9 Time=0.000 Energy={accepted}'))
        summary = (f'OPT| Step number 9\nOPT| Optimization method CG\nOPT| Total energy [hartree] {accepted}\n'
                   + criteria() + 'OPT| Conv. for PRESSURE YES\n')
        for preceding, later, verified in ((accepted + 5e-7, None, True), (accepted, accepted, True),
                                            (-31, None, False), (-31, accepted, False),
                                            (accepted, -30, False)):
            with self.subTest(preceding=preceding, later=later):
                body = 'OPTIMIZATION STEP: 9\n' + force_eval(-32) + force_eval(preceding) + summary
                self.parse(body + (force_eval(later) if later is not None else '') + END, cell=True)
                report = match_trajectory(self.out, ext)
                match, = report.matches
                self.assertEqual(match['status'], 'matched' if verified else 'energy_unavailable_in_output')
                self.assertEqual(match['output_energy_selection'],
                                 'opt_summary_line_search' if verified else 'ambiguous')
                self.assertIs(match['output_energy_ambiguous'], not verified)
                self.assertEqual(match['output_energy_hartree'], accepted if verified else None)
                self.assertEqual(report.converged_final_step, match if verified else None)
                if verified:
                    self.assertIn('OPT| Total energy [hartree]', match['output_energy_source']['text'])

    def test_output_atom_count_checked_for_path_and_refuses_mismatch(self):
        record = '  - Atoms: 1'
        run = self.parse(record + '\n' + self.body + END)
        report = match_trajectory(self.out, self.xyz)
        self.assertEqual(report.output_atom_count, 1)
        self.assertEqual(report.output_atom_count_sources,
                         [{'path': str(self.out.resolve()), 'line': 4, 'text': record}])
        self.assertTrue(all(m['atom_count_matches'] is True for m in report.matches))
        self.assertTrue(report.strict_passed)
        report = match_trajectory(run, self.xyz)
        self.assertIsNone(report.output_atom_count)
        self.assertEqual(report.output_atom_count_sources, [])
        self.assertIsNone(report.matches[-1]['atom_count_matches'])

        self.parse('  - Atoms: 3\n' + self.body + END)
        self.xyz.write_text(xyz_frame('Step=3'))  # Count mismatch takes precedence over missing energy.
        report = match_trajectory(self.out, self.xyz)
        match, = report.matches
        self.assertEqual(report.output_atom_count, 3)
        self.assertIs(match['atom_count_matches'], False)
        self.assertEqual(match['status'], 'atom_count_mismatch')
        self.assertIsNone(report.converged_final_step)
        self.assertFalse(report.strict_passed)
        for step in (None, 3):
            with self.subTest(step=step), self.assertRaisesRegex(KitError, 'atom count mismatch'):
                select_matched_frame(report, step=step)
        self.xyz.write_text(xyz_frame('Step=3 Energy=-4'))  # Even agreeing energy is insufficient.
        code, stdout, stderr = self.match_cli('--strict')
        self.assertEqual(code, 7)
        self.assertEqual(json.loads(stdout)['matches'][0]['status'], 'atom_count_mismatch')
        self.assertIn('trajectory has 1, output reports 3', stderr)
        dest = self.root / 'mismatch.extxyz'
        with (patch('cp2kkit.cli.view_matched_structure') as view,
              patch('cp2kkit.cli.view_structure') as view_export):
            for args in (('--view',), ('--export-structure', dest), ('--view', '--export-structure', dest)):
                code, _, stderr = self.match_cli(*args)
                self.assertEqual(code, 2)
                self.assertIn('atom count mismatch', stderr)
            view.assert_not_called()
            view_export.assert_not_called()
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_suffix('.extxyz.json').exists())

    def test_output_atom_count_uses_only_valid_agreement_in_selected_segment(self):
        for extra, expected, warning, valid_records in (
                ('Total number of - Atoms: 1', 1, None, 2),
                ('- Atoms: 3', None, 'Conflicting output - Atoms:', 2),
                ('- Atoms: 1broken', None, 'Malformed output - Atoms:', 1)):
            with self.subTest(extra=extra):
                self.parse(f'- Atoms: 1\n{extra}\n' + self.body + END
                           + HEADER + '- Atoms: 8\n' + self.body + END)
                report = match_trajectory(self.out, self.xyz, segment=1)
                self.assertEqual(report.output_atom_count, expected)
                self.assertEqual(len(report.output_atom_count_sources), valid_records)
                self.assertIs(report.matches[-1]['atom_count_matches'], True if expected else None)
                count_warnings = [w for w in report.warnings if '- Atoms:' in w]
                if warning:
                    self.assertEqual(len(count_warnings), 1)
                    self.assertIn(warning, count_warnings[0])
                else:
                    self.assertEqual(count_warnings, [])
                self.assertEqual(match_trajectory(self.out, self.xyz, segment=2).output_atom_count, 8)

    def test_explicit_step_can_pass_without_converged_final(self):
        run = self.parse(self.body)
        report = match_trajectory(run, self.xyz, requested_step=2)
        self.assertTrue(report.strict_passed)
        self.assertIsNone(report.converged_final_step)
        self.assertEqual(select_matched_frame(report, step=2)[0].structure.positions[0][0], 2)
        with self.assertRaises(KitError):
            select_matched_frame(report)
        self.assertEqual(self.match_cli('--strict')[0], 7)
        self.assertEqual(self.match_cli('--step', 2, '--strict')[0], 0)

    def test_segment_validation_and_cli_subprocess(self):
        run = self.parse(self.body + END + HEADER + self.body + END)
        with self.assertRaisesRegex(AmbiguousProject, '1, 2'):
            match_trajectory(run, self.xyz)
        for invalid in (0, -1, 3, True, 1.5):
            with self.assertRaises(KitError):
                match_trajectory(run, self.xyz, segment=invalid)
        self.assertEqual(self.match_cli()[0], 3)
        self.assertEqual(self.match_cli('--segment', 0)[0], 2)
        for invalid in ('nan', 'inf', '-1'):
            self.assertEqual(self.match_cli('--segment', 2, '--energy-tol', invalid)[0], 2)
        root = Path(__file__).resolve().parents[1]
        command = [sys.executable, '-m', 'cp2kkit', 'match-trajectory', str(self.out), str(self.xyz),
                   '--segment', '2', '--strict']
        result = subprocess.run(command, env={**os.environ, 'PYTHONPATH': str(root / 'src')},
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual((report['segment'], report['segment_id']), (2, 1))
        self.assertEqual(report['parser'], {'name': 'cp2kkit', 'version': __version__})
        self.assertIn('WARNING:', result.stderr)

    def test_cli_exclusive_outputs_and_option_validation(self):
        dest, out = self.root / 'verified.extxyz', self.root / 'report.json'
        sidecar = Path(str(dest) + '.json')
        for args in (('--viewer', 'fake'), ('--allow-cell-loss',), ('--structure-format', 'xyz')):
            self.assertEqual(self.match_cli(*args)[0], 2)
        out.write_text('reserved report')
        self.assertEqual(self.match_cli('-o', out, '--export-structure', dest)[0], 5)
        self.assertFalse(dest.exists())
        self.assertEqual(out.read_text(), 'reserved report')
        out.unlink()
        sidecar.write_text('reserved sidecar')
        self.assertEqual(self.match_cli('-o', out, '--export-structure', dest)[0], 5)
        self.assertFalse(dest.exists())
        self.assertFalse(out.exists())
        self.assertEqual(sidecar.read_text(), 'reserved sidecar')
        sidecar.unlink()
        before = (self.out.read_bytes(), self.xyz.read_bytes())
        self.assertEqual(self.match_cli('--strict', '-o', out, '--export-structure', dest)[0], 0)
        self.assertEqual(read_xyz(dest).positions[0][0], 3)
        self.assertEqual(json.loads(out.read_text())['converged_final_step']['step'], 3)
        self.assertEqual(self.match_cli('--export-structure', dest)[0], 5)
        self.assertEqual((self.out.read_bytes(), self.xyz.read_bytes()), before)

    def test_cli_reserves_report_before_structure_export(self):
        dest = self.root / 'verified.extxyz'
        out = self.root / 'nonexistent' / 'report.json'
        code, stdout, stderr = self.match_cli('-o', out, '--export-structure', dest)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, '')
        self.assertIn('Cannot create', stderr)
        self.assertFalse(out.parent.exists())
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_suffix('.extxyz.json').exists())

        dangling = self.root / 'report.json'
        dangling.symlink_to(out)
        self.assertEqual(self.match_cli('-o', dangling, '--export-structure', dest)[0], 5)
        self.assertTrue(dangling.is_symlink())
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_suffix('.extxyz.json').exists())

    def test_viewer_only_stages_verified_geometry(self):
        paths = []

        def inspect(path, **kwargs):
            paths.append(path)
            self.assertEqual(path.name, 'step-3.xyz')
            self.assertEqual(read_xyz(path).positions, [[3.0, 0.0, 0.0]])
            self.assertEqual(len(path.read_text().splitlines()), 3)
            self.assertEqual(kwargs['executable'], 'mock-viewer')
            return 0

        with patch('cp2kkit.viewer.launch_viewer', side_effect=inspect) as viewer:
            self.assertEqual(self.match_cli('--view', '--viewer', 'mock-viewer')[0], 0)
            self.assertFalse(paths[0].parent.exists())
            for text in (xyz_frame('i=3 E=-3'), xyz_frame('i=3 E=-4') * 2):
                self.xyz.write_text(text)
                self.assertEqual(self.match_cli('--step', 3, '--view')[0], 2)
            viewer.assert_called_once()
        self.xyz.write_text(xyz_frame(LATTICE + ' Step=3 E=-4', 3))
        frame, _ = select_matched_frame(match_trajectory(self.out, self.xyz))
        with patch('cp2kkit.viewer.launch_viewer', return_value=0) as viewer:
            self.assertEqual(view_matched_structure(frame.structure), 0)
            staged = viewer.call_args.args[0]
            self.assertEqual(staged.suffix, '.extxyz')
            self.assertFalse(staged.exists())
        dest = self.root / 'selected.extxyz'
        with patch('cp2kkit.cli.view_structure', return_value=0) as viewer:
            self.assertEqual(self.match_cli('--view', '--export-structure', dest)[0], 0)
            viewer.assert_called_once_with(dest, executable=None)
            self.assertEqual(read_xyz(dest).pbc, [True, True, True])

    @unittest.skipUnless(find_spec('matplotlib'), 'Matplotlib optional')
    def test_convergence_plot_scales_pressure_and_rollback(self):
        from matplotlib.figure import Figure

        for cell in (False, True):
            with self.subTest(cell=cell):
                pressure = 'OPT| Pressure deviation [bar] 0\nOPT| Pressure tolerance [bar] 2\n' if cell else ''
                run = self.parse(evaluation(1, -1, criteria(value='0') + pressure) + END, cell=cell)
                fig = Figure()
                _convergence_axes(fig, run)
                self.assertEqual(len(fig.axes), 2 if cell else 1)
                self.assertEqual(fig.axes[0].get_yscale(), 'linear')
                output = self.root / f'criteria-{cell}.png'
                code, _, err = self.cli('plot', self.out, '--kind', 'convergence', '-o', output)
                self.assertEqual(code, 0, err)
                self.assertTrue(output.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
                with output.with_suffix('.csv').open(newline='') as stream:
                    rows = list(csv.DictReader(stream))
                self.assertEqual(len(rows), 5 if cell else 4)
                self.assertTrue(all(float(row['value']) == 0 for row in rows))
                manifest = json.loads(output.with_suffix('.json').read_text())
                self.assertEqual(manifest['kind'], 'convergence')
                self.assertFalse(manifest['segments_connected'])
        fig = Figure()
        run = self.parse(self.body + END)
        _convergence_axes(fig, run)
        self.assertEqual(fig.axes[0].get_yscale(), 'log')
        self.assertIn('Nonpositive', fig.axes[0].texts[0].get_text())
        output = self.root / 'occupied.png'
        manifest = output.with_suffix('.json')
        manifest.write_text('occupied')
        self.assertEqual(self.cli('plot', self.out, '--kind', 'convergence', '-o', output)[0], 5)
        self.assertEqual(manifest.read_text(), 'occupied')
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix('.csv').exists())
        self.parse(evaluation(1, -1) + END)
        code, _, stderr = self.cli('plot', self.out, '--kind', 'convergence', '-o', output)
        self.assertEqual(code, 2)
        self.assertIn('No convergence criteria records to plot', stderr)

    def test_missing_matplotlib(self):
        output = self.root / 'missing.png'
        with patch.dict(sys.modules, {'matplotlib.figure': None}):
            self.assertEqual(self.cli('plot', self.out, '--kind', 'convergence', '-o', output)[0], 6)
        self.assertFalse(output.exists())

    def test_output_analysis_menu_integration(self):
        quality = self.tui(5, 1, self.out, '', 0)
        self.assertIn('Observed optimization steps: 4', quality)
        self.assertIn('max_step: value=0.0', quality)
        parsed = self.tui(5, 2, self.out, '', 0)
        self.assertIn('Segments: 1; observed records: energy=4, SCF=4', parsed)
        self.assertIn('Optimization criteria steps: 4', parsed)
        png = self.root / 'menu.png'
        with patch('cp2kkit.plot.plot_run', return_value=[png]) as plot:
            self.assertIn(str(png), self.tui(5, 3, self.out, 'convergence', png, '', 0))
            self.assertEqual(plot.call_args.args[2], 'convergence')
        self.parse(self.body + END + HEADER + self.body + END)
        dest, out = self.root / 'menu.extxyz', self.root / 'menu.json'
        with patch('cp2kkit.main_tui.view_matched_structure') as view:
            log = self.tui(5, 4, self.out, self.xyz, '2', 'd', 'j', out, 'e', '', dest, 'v', 0, '', 0)
            self.assertEqual(view.call_args.args[0].frame, 0)
            self.assertEqual(view.call_args.kwargs['stem'], 'step-0')
        for text in ('Select 1-based segment', 'matched=4', 'unmatched trajectory frames=1',
                     'converged_final_step: 3', '"operation": "trajectory_step_match"'):
            self.assertIn(text, log)
        self.assertEqual(json.loads(out.read_text())['segment'], 2)
        self.assertEqual(read_xyz(dest).positions[0][0], 3)
        before = out.read_bytes(), dest.read_bytes()
        log = self.tui(5, 4, self.out, self.xyz, '2', 'j', out, 'e', '', dest, '', 0)
        self.assertEqual(log.count('Refusing to overwrite'), 2)
        self.assertEqual((out.read_bytes(), dest.read_bytes()), before)

    def test_duplicate_malformed_criterion_invalidates_prior_value(self):
        body = evaluation(1, -1, criteria('YES', '0.0001') + 'OPT| Maximum step size 0.0002broken\n') + END
        run = self.parse(body)
        seg = run.segments[0]
        self.assertIsNone(seg.last_optimization_step.max_step.value)
        self.assertEqual(len(seg.unparsed_optimization_records), 1)
        report = quality_report(run)['segments'][0]
        self.assertNotEqual(report['status'], 'passed')
        self.assertIn(seg.unparsed_optimization_records[0].__dict__, report['evidence'])

    def test_out_of_order_frames_overlapping_targets_and_invalid_inputs(self):
        # Out-of-order trajectory frames still match strictly by explicit step number.
        self.xyz.write_text(xyz_frame('i = 3, E = -4', 3) + xyz_frame('i = 1, E = -2', 1)
                            + xyz_frame('i = 2, E = -3', 2))
        report = match_trajectory(self.out, self.xyz)
        self.assertTrue(report.strict_passed)
        self.assertEqual([(m['step'], m['frame_index']) for m in report.matches], [(1, 1), (2, 2), (3, 0)])
        self.assertEqual(select_matched_frame(report)[0].structure.positions[0][0], 3.0)

        # Overlapping -o and --export-structure (or its .json sidecar) refuse cleanly with rollback.
        same = self.root / 'overlap.extxyz'
        sidecar = Path(str(same) + '.json')
        for target_out in (same, sidecar):
            with self.subTest(target_out=target_out.name):
                code, _, _ = self.match_cli('-o', target_out, '--export-structure', same)
                self.assertEqual(code, 5)
                self.assertFalse(same.exists())
                self.assertFalse(sidecar.exists())

        # Missing file (2), unsupported trajectory suffix (2), and truncated XYZ (4).
        self.assertEqual(self.cli('match-trajectory', self.root / 'missing.out', self.xyz)[0], 2)
        restart = self.root / 'water.restart'
        restart.write_text('&GLOBAL\n&END GLOBAL\n')
        self.assertEqual(self.cli('match-trajectory', self.out, restart)[0], 2)
        broken_xyz = self.root / 'broken.xyz'
        broken_xyz.write_text('2\ni = 1, E = -2\nHe 0 0 0\n')
        self.assertEqual(self.cli('match-trajectory', self.out, broken_xyz)[0], 4)

    @unittest.skipUnless(find_spec('matplotlib'), 'Matplotlib optional')
    def test_signed_pressure_and_multisegment_disconnected_plot(self):
        from matplotlib.figure import Figure

        p_neg = ('OPT| Pressure deviation [bar] -12.5\nOPT| Pressure tolerance [bar] 10.0\n'
                 'OPT| Pressure is converged NO\n')
        p_pos = ('OPT| Pressure deviation [bar] 4.0\nOPT| Pressure tolerance [bar] 10.0\n'
                 'OPT| Pressure is converged YES\n')
        body = (evaluation(1, -1, criteria('NO', '0.005') + p_neg) + END
                + HEADER.replace('GEO_OPT', 'CELL_OPT')
                + evaluation(1, -2, criteria('YES', '0.0002') + p_pos) + END)
        run = self.parse(body, cell=True)
        fig = Figure()
        _convergence_axes(fig, run)
        self.assertEqual(len(fig.axes), 2)
        self.assertEqual(fig.axes[1].get_yscale(), 'linear')
        # Two segments plotted as separate pressure series (not connected across segments).
        pressure_series = [line for line in fig.axes[1].lines if line.get_label().startswith('segment ')]
        self.assertEqual(len(pressure_series), 2)
        self.assertEqual(list(pressure_series[0].get_ydata()), [-12.5])
        self.assertEqual(list(pressure_series[1].get_ydata()), [4.0])

    def test_match_trajectory_view_real_mock_executable_and_display_guard(self):
        log_path = self.root / 'viewer-calls.jsonl'
        mock_viewer = _make_mock_viewer(self.root, log_path)
        with patch.dict(os.environ, {'DISPLAY': ''}, clear=False):
            code, _, err = self.match_cli('--view', '--viewer', mock_viewer)
            self.assertEqual(code, 2)
            self.assertIn('DISPLAY', err)
            self.assertEqual(_read_invocations(log_path), [])
        with patch.dict(os.environ, {'DISPLAY': ':0'}, clear=False):
            code, out, err = self.match_cli('--view', '--viewer', mock_viewer)
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)['converged_final_step']['step'], 3)
        calls = _read_invocations(log_path)
        self.assertEqual(len(calls), 1)
        staged = Path(calls[0]['args'][0])
        self.assertEqual(staged.name, 'step-3.xyz')
        self.assertFalse(staged.exists())
        self.assertIn('He 3 0 0', calls[0]['snapshot'])
