"""Source-format fixtures and mocked process boundaries; never run Shermo/CP2K."""
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from cp2kkit.cli import main
from cp2kkit.errors import AmbiguousProject, KitError, ParseError
from cp2kkit.main_tui import shermo_analysis
from cp2kkit.thermochemistry import read_shermo, run_shermo
from cp2kkit.vibration_results import parse_vibration
from tests.test_vibration_results import END, FIRST, TEXT

SHERMO = ''' Shermo: A general code for calculating molecular thermochemistry properties
 Version 2.6.2  Release date: 2026-May-19
 Running parameters:
 Temperature:     298.150 K
 Pressure:          1.000 atm
 Scale factor of vibrational frequencies for ZPE:        1.0000
 Scale factor of vibrational frequencies for U(T)-U(0):  1.0000
 Scale factor of vibrational frequencies for S(T):       1.0000
 Scale factor of vibrational frequencies for CV:         1.0000
 Low frequencies treatment: Grimme's interpolation for entropy
 Vibrational frequency threshold used in the interpolation is 100.00 cm^-1
 ======= Molecular information =======
 Electronic energy:        -1.00000000 a.u.
 Point group: C2v
 Rotational symmetry number:  2
 This is not a linear molecule
 There are     3 frequencies (cm^-1):
    512.0  1032.0  1958.0
 ========== Total ==========
 Zero point energy (ZPE):     21.004 kJ/mol,      5.020 kcal/mol    0.008000 a.u.
 Thermal correction to U:     28.880 kJ/mol      6.903 kcal/mol    0.011000 a.u.
 Thermal correction to H:     31.506 kJ/mol      7.530 kcal/mol    0.012000 a.u.
 Thermal correction to G:    -18.378 kJ/mol     -4.392 kcal/mol   -0.007000 a.u.
 Electronic energy:         -1.0000000 a.u.
 Sum of electronic energy and thermal correction to U:          -0.9890000 a.u.
 Sum of electronic energy and thermal correction to H:          -0.9880000 a.u.
 Sum of electronic energy and thermal correction to G:          -1.0070000 a.u.
'''
CP2K = (TEXT[:TEXT.index(' VIB|                         4\n')]
        .replace('0.0000000E+00 2.0000000E+00\n', '0.0000000E+00\n')
        .replace(FIRST, '512.0 1032.0 1958.0').replace('2  C ', '2  H ').replace('3  O ', '3  H ')
        + ' VIB| NORMAL MODES - THERMOCHEMICAL DATA\n\n'
        + ' VIB| Electronic energy (U) [kJ/mol]: -2625.49961710\n' + END)
XYZ = '3\nexplicit reference\nO 0 0 0\nH .8 .6 0\nH -.8 .6 0\n'
SINGLE_POINT = '''PROGRAM STARTED AT synthetic
CP2K| version string: CP2K version 2026.2
GLOBAL| Run type ENERGY
DFT| Multiplicity   1
SCF run converged in 10 steps
ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]: -2.000000000000000
PROGRAM ENDED AT synthetic
'''
SHERMO_SP = (SHERMO.replace('-1.000000', '-2.000000').replace('-0.9890000', '-1.9890000')
             .replace('-0.9880000', '-1.9880000').replace('-1.0070000', '-2.0070000'))


class ShermoTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cp2k = self.root / 'source.out'
        self.xyz = self.root / 'source.xyz'
        self.sp = self.root / 'single-point.out'
        self.sp.write_text(SINGLE_POINT)
        self.exe = self.root / 'Shermo with spaces'
        self.cp2k.write_text(CP2K)
        self.xyz.write_text(XYZ)
        self.exe.write_text('fixture: not a real executable')
        self.exe.chmod(0o700)
        self.settings = dict(executable=self.exe, frame=0, masses_amu=[16., 1., 1.],
                             multiplicity=1, confirm_reference=True)

    def fake(self, output=SHERMO, status=0):
        def invoke(args, **kwargs):
            self.args = args
            self.scratch = kwargs['cwd']
            self.exchange = (self.scratch / 'molecule.shm').read_bytes()
            self.assertEqual(args[:3], [str(self.exe), 'molecule.shm', '-noset'])
            self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
            self.assertFalse(kwargs.get('shell', False))
            kwargs['stdout'].write(output.encode())
            return subprocess.CompletedProcess(args, status)
        return invoke

    def test_explicit_run_exchange_provenance_and_results(self):
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake()):
            result = run_shermo(self.cp2k, self.xyz, **self.settings)
        rows = self.exchange.decode().splitlines()
        self.assertEqual(rows[0], '*E')
        self.assertAlmostEqual(float(rows[1]), -1., places=10)
        self.assertEqual(rows[2:7], ['*wavenum', '512.0', '1032.0', '1958.0', '*atoms'])
        self.assertEqual(rows[-2:], ['*elevel', '0 1'])
        self.assertFalse(self.scratch.exists())
        ref = result['cp2k_reference']
        self.assertEqual(ref['geometry_association'], 'caller_asserted')
        self.assertEqual(ref['exchange_sha256'], hashlib.sha256(self.exchange).hexdigest())
        self.assertEqual(result['zero_point_energy']['value'], .008)
        self.assertEqual(result['corrected_totals']['G']['value'], -1.007)
        self.assertEqual(result['thermal_corrections']['G']['unit'], 'hartree')
        self.assertEqual(result['low_frequency_cutoff']['value'], 100.)
        self.assertIn('10.1016/j.comptc.2021.113249', result['citation'])
        self.assertEqual(result['source']['sha256'], hashlib.sha256(SHERMO.encode()).hexdigest())
        self.assertEqual(self.cp2k.read_text(), CP2K)
        self.assertEqual(self.xyz.read_text(), XYZ)

    def test_single_point_replaces_only_electronic_energy_even_without_footer(self):
        for has_footer in (True, False):
            with self.subTest(has_footer=has_footer), patch('cp2kkit.thermochemistry.subprocess.run',
                                                            side_effect=self.fake(SHERMO_SP)):
                self.cp2k.write_text(CP2K if has_footer else CP2K.split(' VIB| NORMAL MODES - THERMOCHEMICAL DATA')[0] + END)
                result = run_shermo(self.cp2k, self.xyz, **self.settings, energy_output=self.sp)
            lines = self.exchange.decode().splitlines()
            self.assertEqual(float(lines[1]), -2.)
            self.assertEqual(lines[3:6], ['512.0', '1032.0', '1958.0'])
            ref = result['cp2k_reference']
            self.assertEqual(ref['printed_electronic_energy'] is not None, has_footer)
            self.assertEqual(ref['selected_electronic_energy']['kind'], 'cp2k_single_point')
            self.assertEqual(ref['selected_electronic_energy']['source']['sha256'],
                             hashlib.sha256(self.sp.read_bytes()).hexdigest())
            self.assertEqual(ref['selected_electronic_energy']['observation']['quantity']['source']['line'], 6)
            self.assertEqual(result['thermal_corrections']['G']['value'], -.007)
            self.assertEqual(result['corrected_totals']['G']['value'], -2.007)

    def test_single_point_ambiguity_explicit_selection_and_no_fallback(self):
        self.sp.write_text(SINGLE_POINT + SINGLE_POINT)
        with patch('cp2kkit.thermochemistry.subprocess.run') as run:
            with self.assertRaises(AmbiguousProject):
                run_shermo(self.cp2k, self.xyz, **self.settings, energy_output=self.sp)
            for text in (SINGLE_POINT.replace('ENERGY\n', 'GEO_OPT\n'),
                         SINGLE_POINT.replace('PROGRAM ENDED AT synthetic\n', ''),
                         SINGLE_POINT.replace('SCF run converged', 'SCF run NOT converged'),
                         SINGLE_POINT.replace('Multiplicity   1', 'Multiplicity   3'),
                         SINGLE_POINT.replace('PROGRAM ENDED', 'ENERGY| Total FORCE_EVAL (QS) energy [a.u.]: -3.0\nPROGRAM ENDED'),
                         SINGLE_POINT.replace('PROGRAM ENDED', 'ENERGY| Total FORCE_EVAL (QS) energy [a.u.]: broken\nPROGRAM ENDED')):
                self.sp.write_text(text)
                with self.subTest(text=text), self.assertRaises(KitError):
                    run_shermo(self.cp2k, self.xyz, **self.settings, energy_output=self.sp)
            run.assert_not_called()
        self.sp.write_text(SINGLE_POINT.replace('-2.000', '-3.000') + SINGLE_POINT)
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(SHERMO_SP)):
            result = run_shermo(self.cp2k, self.xyz, **self.settings, energy_output=self.sp, energy_segment=2)
        self.assertEqual(result['cp2k_reference']['selected_electronic_energy']['segment'], 2)

    def test_printed_reference_state_is_checked_before_launch(self):
        def vibration_state(fields):
            return CP2K.replace(' POISSON|', fields + ' POISSON|', 1)

        neutral = vibration_state(' DFT| Charge    0\n DFT| Multiplicity    1\n')
        with patch('cp2kkit.thermochemistry.subprocess.run') as run:
            for text, energy_output, message in (
                (vibration_state(' DFT| Multiplicity    3\n'), None, 'inconsistent printed spin'),
                (vibration_state(' DFT| Multiplicity    broken\n'), None, 'unusable printed multiplicity'),
                (vibration_state(' DFT| Charge    0\n DFT| Charge    1\n'), None, 'unusable printed charge'),
                (neutral, self.sp, 'different printed charge'),
            ):
                self.cp2k.write_text(text)
                self.sp.write_text(SINGLE_POINT.replace('DFT| Multiplicity', 'DFT| Charge   1\nDFT| Multiplicity'))
                with self.subTest(message=message), self.assertRaisesRegex(KitError, message):
                    run_shermo(self.cp2k, self.xyz, **self.settings, energy_output=energy_output)
            run.assert_not_called()

        self.cp2k.write_text(neutral)
        self.sp.write_text(SINGLE_POINT.replace('DFT| Multiplicity', 'DFT| Charge   0\nDFT| Multiplicity'))
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(SHERMO_SP)):
            result = run_shermo(self.cp2k, self.xyz, **self.settings, energy_output=self.sp)
        state = result['cp2k_reference']['reference_state']
        self.assertEqual(state['charge']['status'], 'parsed')
        self.assertEqual(state['charge']['value'], 0)
        self.assertEqual(state['multiplicity']['value'], 1)
        source = state['charge']['sources'][0]
        self.assertEqual(source['text'], neutral.splitlines()[source['line'] - 1])
        self.assertEqual(parse_vibration(self.cp2k).to_dict()['reference_state'], state)

    def test_missing_reference_wrong_geometry_negative_modes_and_unconfirmed_do_not_launch(self):
        cases = [(CP2K, XYZ, {'confirm_reference': False}),
                 (CP2K, XYZ, {'expected_source_sha256': 'stale'}),
                 (CP2K, XYZ, {'masses_amu': [1]}),
                 (CP2K, XYZ, {'masses_amu': [float('nan'), 1, 1]}),
                 (CP2K, XYZ.replace('H -.8', 'F -.8'), {}),
                 (CP2K.replace('512.0', '-512.0'), XYZ, {}),
                 (CP2K.replace('512.0', '0.0'), XYZ, {}),
                 (CP2K.replace('Electronic energy (U)', 'Not a reference'), XYZ, {}),
                 (CP2K.replace(' POISSON|', ' SCF run NOT converged\n POISSON|'), XYZ, {})]
        with patch('cp2kkit.thermochemistry.subprocess.run') as run:
            for cp2k, xyz, settings in cases:
                with self.subTest(settings=settings, cp2k=cp2k[-200:], xyz=xyz):
                    self.cp2k.write_text(cp2k)
                    self.xyz.write_text(xyz)
                    with self.assertRaises(KitError):
                        run_shermo(self.cp2k, self.xyz, **(self.settings | settings))
            run.assert_not_called()

    def test_harmonic_run_and_read_only_import(self):
        text = (SHERMO.replace("Grimme's interpolation for entropy", 'Harmonic approximation')
                .replace(' Vibrational frequency threshold used in the interpolation is 100.00 cm^-1\n', ''))
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(text)) as run:
            managed = run_shermo(self.cp2k, self.xyz, **self.settings, low_frequency='harmonic')
            path = self.root / 'harmonic.txt'
            path.write_text(text, encoding='utf-8')
            imported = read_shermo(path)
            run.assert_called_once()
        self.assertEqual(self.args[self.args.index('-imode') + 1], '0')
        self.assertEqual(self.args[self.args.index('-ilowfreq') + 1], '0')
        for result in (managed, imported):
            self.assertEqual(result['low_frequency_treatment'], 'harmonic')
            self.assertIsNone(result['low_frequency_cutoff'])
        self.assertNotIn('external_run', imported)
        self.assertNotIn('cp2k_reference', imported)

    def test_incomplete_wrong_version_settings_and_process_failure(self):
        for output in (SHERMO.replace('2.6.2', '2.6.1'), SHERMO.rsplit('\n', 2)[0],
                       SHERMO.replace('298.150', '300.000'), SHERMO.replace('-1.0070000', '-1.0090000'),
                       SHERMO + ' Note: There are 1 imaginary frequencies, they will be ignored in the calculation\n'):
            with self.subTest(output=output[-80:]), patch('cp2kkit.thermochemistry.subprocess.run',
                                                          side_effect=self.fake(output)):
                with self.assertRaises(ParseError):
                    run_shermo(self.cp2k, self.xyz, **self.settings)
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(status=1)):
            with self.assertRaisesRegex(KitError, 'status 1'):
                run_shermo(self.cp2k, self.xyz, **self.settings)
            self.assertFalse(self.scratch.exists())
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=subprocess.TimeoutExpired('shermo', 1)):
            with self.assertRaisesRegex(KitError, 'timeout'):
                run_shermo(self.cp2k, self.xyz, **self.settings, timeout=1)

    def test_cli_and_import_share_result_parser_and_protect_existing_paths(self):
        path = self.root / 'existing.txt'
        path.write_text(SHERMO)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(['shermo-read', str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), read_shermo(path))
        args = ['thermochemistry', str(self.cp2k), '--shermo', str(self.exe), '--geometry', str(self.xyz),
                '--frame', '0', '--masses-amu', '16', '1', '1', '--multiplicity', '1', '--confirm-reference']
        dest = self.root / 'result.json'
        args.extend(['--energy-output', str(self.sp), '--energy-segment', '1'])
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(SHERMO_SP)) as run:
            self.assertEqual(main([*args, '-o', str(dest)]), 0)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main([*args, '-o', str(dest)]), 5)
            run.assert_called_once()
        data = json.loads(dest.read_text())
        self.assertEqual(data['operation'], 'shermo_thermochemistry')
        self.assertEqual(data['cp2k_reference']['selected_electronic_energy']['kind'], 'cp2k_single_point')

    def test_tui_back_at_each_numeric_or_low_frequency_prompt_returns_without_running(self):
        report = parse_vibration(self.cp2k)
        paths = [str(self.sp), str(self.exe), str(self.xyz)]
        fields = ['1', '0', '16 1 1', '1', '', '', '', '']
        for index in range(len(fields)):
            with self.subTest(prompt=index), patch('cp2kkit.thermochemistry.run_shermo') as run:
                menu = Mock()
                menu.ask.side_effect = [*paths, *fields[:index], 'BaCk', 'yes']
                shermo_analysis(menu, report)
                self.assertEqual(menu.ask.call_count, len(paths) + index + 1)
                run.assert_not_called()
                menu.show.assert_not_called()

    def test_tui_decline_never_launches_and_yes_shows_same_backend(self):
        report = parse_vibration(self.cp2k)
        fields = [str(self.sp), str(self.exe), str(self.xyz), '1', '0', '16 1 1', '1', '', '', '', '']
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(SHERMO_SP)) as run:
            menu = Mock()
            menu.ask.side_effect = [*fields, '']
            shermo_analysis(menu, report)
            run.assert_not_called()
            menu.ask.side_effect = [*fields, 'yes', '']
            shermo_analysis(menu, report)
            run.assert_called_once()
            self.assertIn('Shermo thermochemistry', str(menu.show.call_args_list))
