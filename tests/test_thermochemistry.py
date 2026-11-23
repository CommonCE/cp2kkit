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
        prefix = ['', str(self.sp), str(self.exe), str(self.xyz)]
        fields = ['1', '0', '16 1 1', '1', '', '', '', '']
        for index in range(len(fields)):
            with self.subTest(prompt=index), patch('cp2kkit.thermochemistry.run_shermo') as run:
                menu = Mock()
                menu.ask.side_effect = [*prefix, *fields[:index], 'BaCk', 'yes']
                shermo_analysis(menu, report)
                self.assertEqual(menu.ask.call_count, len(prefix) + index + 1)
                run.assert_not_called()
                menu.show.assert_not_called()

    def test_tui_decline_never_launches_and_yes_shows_same_backend(self):
        report = parse_vibration(self.cp2k)
        fields = ['', str(self.sp), str(self.exe), str(self.xyz), '1', '0', '16 1 1', '1', '', '', '', '']
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(SHERMO_SP)) as run:
            menu = Mock()
            menu.ask.side_effect = [*fields, '']
            shermo_analysis(menu, report)
            run.assert_not_called()
            menu.ask.side_effect = [*fields, 'yes', '']
            shermo_analysis(menu, report)
            run.assert_called_once()
            self.assertIn('Shermo thermochemistry', str(menu.show.call_args_list))

    def test_vibrational_only_imode1_harmonic_grimme_element_masses_and_read(self):
        surface_cp2k = (
            ' **** **** ******  **  PROGRAM STARTED AT                synthetic\n'
            ' CP2K| version string:                                      CP2K version 2026.2\n'
            ' GLOBAL| Run type                                            VIBRATIONAL_ANALYSIS\n'
            ' CELL| Periodicity                                                           XYZ\n'
            ' DFT| Charge                                                                   0\n'
            ' DFT| Multiplicity                                                             1\n'
            ' POISSON| Periodicity                                                        XYZ\n'
            ' VIB| Internal  Low frequencies ---\n'
            ' VIB| 1.0E+00 2.0E+00 3.0E+00 4.0E+00 5.0E+00\n'
            ' VIB| 6.0E+00\n'
            ' VIB|                        NORMAL MODES - CARTESIAN DISPLACEMENTS\n'
            ' VIB|\n'
            ' VIB|                         1                    2                    3\n'
            ' VIB|Frequency (cm^-1)  5.6081757307E+01    3.2525299057E+02    4.8814109742E+02\n'
            ' VIB|Red.Masses (a.u.)  1.0000000000E+00    1.0000000000E+00    1.0000000000E+00\n'
            ' VIB|Frc consts (a.u.)  1.0000000000E-02    2.0000000000E-02    3.0000000000E-02\n'
            '  ATOM  EL               X     Y     Z       X     Y     Z       X     Y     Z\n'
            '     3  O              -0.03 -0.02 -0.01    0.22 -0.03  0.08   -0.10 -0.34 -0.03\n'
            '     4  H               0.29 -0.57  0.23    0.76 -0.28 -0.06   -0.31 -0.29  0.08\n'
            '\n'
            ' VIB|                         4                    5                    6\n'
            ' VIB|Frequency (cm^-1)  6.7130895208E+02    1.5862967520E+03    3.6170421442E+03\n'
            ' VIB|Red.Masses (a.u.)  1.0000000000E+00    1.0000000000E+00    1.0000000000E+00\n'
            ' VIB|Frc consts (a.u.)  1.0000000000E-02    2.0000000000E-02    3.0000000000E-01\n'
            '  ATOM  EL               X     Y     Z       X     Y     Z       X     Y     Z\n'
            '     3  O               0.11 -0.09  0.23   -0.33  0.10  0.35    0.02  0.12  0.02\n'
            '     4  H              -0.54  0.09  0.51    0.64 -0.21 -0.04   -0.42 -0.11  0.51\n'
            '\n'
            ' -                                DBCSR STATISTICS                             -\n'
            + END
        )
        slab_xyz = (
            '4\nLattice="12 0 0 0 12 0 0 0 22" Properties=species:S:1:pos:R:3 pbc="T T T"\n'
            'Ga 0 0 1\nO 2 2 1\nO 3 3 5\nH 3.8 3 5.6\n'
        )
        shermo_imode1_harm = ''' Shermo: A general code for calculating molecular thermochemistry properties
 Version 2.6.2  Release date: 2026-May-19
 Running parameters:
 Temperature:     298.150 K
 Pressure:          1.000 atm
 Scale factor of vibrational frequencies for ZPE:        1.0000
 Scale factor of vibrational frequencies for U(T)-U(0):  1.0000
 Scale factor of vibrational frequencies for S(T):       1.0000
 Scale factor of vibrational frequencies for CV:         1.0000
 Low frequencies treatment: Harmonic approximation
 ======= Molecular information =======
 Electronic energy:        -2.00000000 a.u.
 Point group: C1
 Rotation information is not shown here since imode=1
 There are     6 frequencies (cm^-1):
    56.1   325.3   488.1   671.3  1586.3  3617.0
 Translation contribution is ignored since imode=1
 Rotation contribution is ignored since imode=1
 ========== Total ==========
 Zero point energy (ZPE):     40.000 kJ/mol,      9.560 kcal/mol    0.015000 a.u.
 Thermal correction to U:     44.634 kJ/mol     10.668 kcal/mol    0.017000 a.u.
 Thermal correction to H:     44.634 kJ/mol     10.668 kcal/mol    0.017000 a.u.
 Thermal correction to G:     36.757 kJ/mol      8.785 kcal/mol    0.014000 a.u.
 Electronic energy:         -2.0000000 a.u.
 Sum of electronic energy and thermal correction to U:          -1.9830000 a.u.
 Sum of electronic energy and thermal correction to H:          -1.9830000 a.u.
 Sum of electronic energy and thermal correction to G:          -1.9860000 a.u.
'''
        shermo_imode1_grimme = shermo_imode1_harm.replace(
            'Low frequencies treatment: Harmonic approximation',
            "Low frequencies treatment: Grimme's interpolation for entropy\n"
            ' Vibrational frequency threshold used in the interpolation is 100.00 cm^-1'
        )
        self.cp2k.write_text(surface_cp2k)
        self.xyz.write_text(slab_xyz)
        self.sp.write_text(SINGLE_POINT.replace('DFT| Multiplicity', 'DFT| Charge   0\nDFT| Multiplicity'))

        # Default low_frequency for vibrational-only is harmonic, with -imode 1 -PGlabel C1.
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(shermo_imode1_harm)):
            res = run_shermo(self.cp2k, self.xyz, executable=self.exe, frame=0,
                             element_masses={'Ga': 69.723, 'O': 15.9994, 'H': 1.0079},
                             multiplicity=1, confirm_reference=True, energy_output=self.sp,
                             thermo_model='vibrational-only', active_atoms='3-4')
        self.assertEqual(self.args[self.args.index('-imode') + 1], '1')
        self.assertEqual(self.args[self.args.index('-PGlabel') + 1], 'C1')
        self.assertEqual(self.args[self.args.index('-ilowfreq') + 1], '0')
        self.assertEqual(res['thermo_model'], 'vibrational-only')
        self.assertEqual(res['imode'], 1)
        self.assertEqual(res['standard_state'], 'vibrational_only_no_translation_rotation')
        self.assertIsNone(res['point_group'])
        self.assertIsNone(res['rotational_symmetry_number'])
        self.assertIsNone(res['linear'])
        self.assertEqual(res['low_frequency_treatment'], 'harmonic')
        self.assertEqual(res['mode_count'], 6)
        self.assertEqual(res['thermal_corrections']['U']['value'], res['thermal_corrections']['H']['value'])
        self.assertTrue(any('selected-mode correction' in w for w in res['warnings']))
        self.assertFalse(any('Grimme' in w for w in res['warnings']))
        ref = res['cp2k_reference']
        self.assertEqual(ref['thermo_model'], 'vibrational-only')
        self.assertEqual(ref['hessian_atom_scope'], 'partial_active_atoms')
        self.assertEqual(ref['active_atoms'], [3, 4])
        self.assertEqual(ref['periodicity'], 'XYZ')
        self.assertEqual(ref['atomic_masses_amu'], [69.723, 15.9994, 15.9994, 1.0079])

        # Explicit grimme under imode=1 is allowed with explicit rotational-inertia caveat.
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(shermo_imode1_grimme)):
            gres = run_shermo(self.cp2k, self.xyz, executable=self.exe, frame=0,
                              masses_amu=[69.723, 15.9994, 15.9994, 1.0079],
                              multiplicity=1, confirm_reference=True, energy_output=self.sp,
                              thermo_model='vibrational-only', active_atoms='3,4', low_frequency='grimme')
        self.assertEqual(self.args[self.args.index('-ilowfreq') + 1], '2')
        self.assertEqual(gres['low_frequency_treatment'], 'grimme')
        self.assertEqual(gres['low_frequency_cutoff']['value'], 100.0)
        self.assertTrue(any('moment-of-inertia' in w for w in gres['warnings']))

        # Read-only shermo-read handles imode=1 cleanly and rejects partial/inconsistent markers or U!=H.
        imode1_file = self.root / 'imode1.txt'
        imode1_file.write_text(shermo_imode1_harm)
        imported = read_shermo(imode1_file)
        self.assertEqual(imported['thermo_model'], 'vibrational-only')
        self.assertEqual(imported['imode'], 1)
        self.assertIsNone(imported['rotational_symmetry_number'])
        self.assertIsNone(imported['linear'])
        self.assertNotIn('external_run', imported)
        for bad in (
            shermo_imode1_harm.replace('Rotation contribution is ignored since imode=1\n', ''),
            shermo_imode1_harm.replace('Point group: C1\n', 'Point group: C1\n Rotational symmetry number: 1\n'),
            shermo_imode1_harm.replace('Point group: C1\n', 'Point group: C1\n Rotational symmetry number: 0\n'),
            shermo_imode1_harm.replace('Point group: C1\n', 'Point group: C1\n This is a bad linear molecule\n'),
            shermo_imode1_harm + ' Rotation contribution is ignored since imode=1\n',
            shermo_imode1_harm.replace('-1.9830000 a.u.\n Sum of electronic energy and thermal correction to G:',
                                       '-1.9830001 a.u.\n Sum of electronic energy and thermal correction to G:'),
            shermo_imode1_harm.replace('Thermal correction to H:     44.634 kJ/mol     10.668 kcal/mol    0.017000 a.u.',
                                       'Thermal correction to H:     47.260 kJ/mol     11.295 kcal/mol    0.018000 a.u.')
                              .replace('-1.9830000 a.u.\n Sum of electronic energy and thermal correction to G:',
                                       '-1.9820000 a.u.\n Sum of electronic energy and thermal correction to G:'),
        ):
            imode1_file.write_text(bad)
            with self.assertRaises(ParseError):
                read_shermo(imode1_file)

        # Strict element-mass and masses_amu validation (no underscores, duplicates, or raw TypeError).
        from cp2kkit.thermochemistry import parse_element_masses, resolve_masses
        for bad_tokens in (['Ga=69_723'], ['Ga=nan'], ['Ga=0'], ['Ga=-1'], ['ga=69.7'], ['Ga=1', 'Ga=2'], ['Ga']):
            with self.subTest(bad_tokens=bad_tokens), self.assertRaises(KitError):
                parse_element_masses(bad_tokens)
        for bad_masses in (16.0, '16', b'16'):
            with self.subTest(bad_masses=bad_masses), self.assertRaises(KitError):
                resolve_masses(['O'], masses_amu=bad_masses)

        # CLI enforces mutually exclusive required mass specification and supports vibrational-only.
        out = self.root / 'surface-thermo.json'
        cli_args = ['thermochemistry', str(self.cp2k), '--shermo', str(self.exe), '--geometry', str(self.xyz),
                    '--frame', '0', '--thermo-model', 'vibrational-only', '--active-atoms', '3-4',
                    '--element-masses', 'Ga=69.723', 'O=15.9994', 'H=1.0079',
                    '--energy-output', str(self.sp), '--multiplicity', '1', '--confirm-reference', '-o', str(out)]
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main([*cli_args, '--masses-amu', '69.723', '15.9994', '15.9994', '1.0079'])
            self.assertEqual(cm.exception.code, 2)
        err = io.StringIO()
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(shermo_imode1_harm)), redirect_stderr(err):
            self.assertEqual(main(cli_args), 0, err.getvalue())
        self.assertIn('WARNING:', err.getvalue())
        self.assertEqual(json.loads(out.read_text())['imode'], 1)
        report = parse_vibration(self.cp2k)
        # TUI skips pressure prompt for vibrational-only, shows pre-launch Grimme warning, and supports back.
        tui_prefix = ['vibrational-only', str(self.sp), str(self.exe), str(self.xyz)]
        tui_fields = ['1', '0', '3-4', 'Ga=69.723 O=15.9994 H=1.0079', '1', '', '', '']
        for index in range(len(tui_fields)):
            with self.subTest(tui_back=index), patch('cp2kkit.thermochemistry.run_shermo') as run:
                menu = Mock()
                menu.ask.side_effect = [*tui_prefix, *tui_fields[:index], 'back', 'yes']
                shermo_analysis(menu, report)
                run.assert_not_called()
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(shermo_imode1_grimme)) as run:
            menu = Mock()
            menu.ask.side_effect = [*tui_prefix, *tui_fields[:-1], 'grimme', '', '']  # decline after seeing warning
            shermo_analysis(menu, report)
            run.assert_not_called()
            self.assertIn('pressure unused in imode=1', str(menu.show.call_args_list))
            self.assertIn('moment-of-inertia', str(menu.show.call_args_list))
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(shermo_imode1_harm)) as run:
            menu = Mock()
            menu.ask.side_effect = [*tui_prefix, *tui_fields, 'yes', '']
            shermo_analysis(menu, report)
            run.assert_called_once()
            self.assertIn('imode=1', str(menu.show.call_args_list))

        # Strict rejection gates before launching Shermo.
        with patch('cp2kkit.thermochemistry.subprocess.run') as run:
            for kwargs, pattern in (
                (dict(thermo_model='vibrational-only', active_atoms='3-4', energy_output=None,
                      element_masses={'Ga': 69.723, 'O': 15.9994, 'H': 1.0079}), 'requires an independent'),
                (dict(thermo_model='vibrational-only', active_atoms=None, energy_output=self.sp,
                      element_masses={'Ga': 69.723, 'O': 15.9994, 'H': 1.0079}), 'requires an explicit --active-atoms'),
                (dict(thermo_model='vibrational-only', active_atoms='2-3', energy_output=self.sp,
                      element_masses={'Ga': 69.723, 'O': 15.9994, 'H': 1.0079}), 'do not match'),
                (dict(thermo_model='vibrational-only', active_atoms='3-4', energy_output=self.sp,
                      element_masses={'Ga': 69.723, 'O': 15.9994}), 'Missing explicit atomic masses'),
                (dict(thermo_model='vibrational-only', active_atoms='3-4', energy_output=self.sp,
                      masses_amu=[69.723, 15.9994, 15.9994, 1.0079],
                      element_masses={'Ga': 69.723, 'O': 15.9994, 'H': 1.0079}), 'not both'),
                (dict(thermo_model='ideal-gas', active_atoms='3-4', energy_output=self.sp,
                      masses_amu=[69.723, 15.9994, 15.9994, 1.0079]), 'only with thermo_model'),
                (dict(thermo_model='ideal-gas', energy_output=self.sp,
                      masses_amu=[69.723, 15.9994, 15.9994, 1.0079]), 'periodic XYZ'),
            ):
                with self.subTest(pattern=pattern), self.assertRaisesRegex(KitError, pattern):
                    run_shermo(self.cp2k, self.xyz, executable=self.exe, frame=0,
                               multiplicity=1, confirm_reference=True, **kwargs)
            # Gas-phase ROT| projection is rejected for vibrational-only.
            rot_cp2k = (CP2K.replace(' POISSON|', ' ROT| Number of rotovibrational vectors     6\n POISSON|'))
            rot_path = self.root / 'rot.out'
            rot_path.write_text(rot_cp2k)
            mol_xyz = self.root / 'mol.xyz'
            mol_xyz.write_text(XYZ)
            with self.assertRaisesRegex(KitError, 'rotovibrational projection'):
                run_shermo(rot_path, mol_xyz, executable=self.exe, frame=0,
                           element_masses={'O': 15.9994, 'H': 1.0079},
                           multiplicity=1, confirm_reference=True, energy_output=self.sp,
                           thermo_model='vibrational-only', active_atoms='1-3')
            # Wrong mode count (3 modes for 2 active atoms) is rejected.
            self.cp2k.write_text(surface_cp2k.split(' VIB|                         4')[0]
                                 .replace(' VIB| 6.0E+00\n', '')
                                 .replace('4.0E+00 5.0E+00\n', '\n')
                                 + ' -                                DBCSR STATISTICS                             -\n' + END)
            with self.assertRaisesRegex(KitError, '3 \\* active_atom_count'):
                run_shermo(self.cp2k, self.xyz, executable=self.exe, frame=0,
                           element_masses={'Ga': 69.723, 'O': 15.9994, 'H': 1.0079},
                           multiplicity=1, confirm_reference=True, energy_output=self.sp,
                           thermo_model='vibrational-only', active_atoms='3-4')
            run.assert_not_called()

    def test_single_point_smearing_entropy_and_full_system_consistency_gates(self):
        surface_cp2k = (
            ' **** **** ******  **  PROGRAM STARTED AT                synthetic\n'
            ' CP2K| version string:                                      CP2K version 2026.2\n'
            ' GLOBAL| Run type                                            VIBRATIONAL_ANALYSIS\n'
            ' CELL| Periodicity                                                           XYZ\n'
            ' DFT| Charge                                                                   0\n'
            ' DFT| Multiplicity                                                             1\n'
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
            '     4  H               0.11 -0.09  0.23   -0.33  0.10  0.35    0.02  0.12  0.02\n'
            '\n'
            ' -                                DBCSR STATISTICS                             -\n'
            + END
        )
        slab_xyz = (
            '4\nLattice="12 0 0 0 12 0 0 0 22" Properties=species:S:1:pos:R:3 pbc="T T T"\n'
            'Ga 0 0 1\nO 2 2 1\nO 3 3 5\nH 3.8 3 5.6\n'
        )
        shermo_3 = ''' Shermo: A general code for calculating molecular thermochemistry properties
 Version 2.6.2  Release date: 2026-May-19
 Running parameters:
 Temperature:     298.150 K
 Pressure:          1.000 atm
 Scale factor of vibrational frequencies for ZPE:        1.0000
 Scale factor of vibrational frequencies for U(T)-U(0):  1.0000
 Scale factor of vibrational frequencies for S(T):       1.0000
 Scale factor of vibrational frequencies for CV:         1.0000
 Low frequencies treatment: Harmonic approximation
 ======= Molecular information =======
 Electronic energy:        -2.00000000 a.u.
 Point group: C1
 Rotation information is not shown here since imode=1
 There are     3 frequencies (cm^-1):
    56.1   325.3  1586.3
 Translation contribution is ignored since imode=1
 Rotation contribution is ignored since imode=1
 ========== Total ==========
 Zero point energy (ZPE):     15.753 kJ/mol,      3.765 kcal/mol    0.006000 a.u.
 Thermal correction to U:     21.004 kJ/mol      5.020 kcal/mol    0.008000 a.u.
 Thermal correction to H:     21.004 kJ/mol      5.020 kcal/mol    0.008000 a.u.
 Thermal correction to G:     13.127 kJ/mol      3.138 kcal/mol    0.005000 a.u.
 Electronic energy:         -2.0000000 a.u.
 Sum of electronic energy and thermal correction to U:          -1.9920000 a.u.
 Sum of electronic energy and thermal correction to H:          -1.9920000 a.u.
 Sum of electronic energy and thermal correction to G:          -1.9950000 a.u.
'''
        self.cp2k.write_text(surface_cp2k)
        self.xyz.write_text(slab_xyz)

        def make_sp(*extra_lines):
            return SINGLE_POINT.replace(
                'SCF run converged in 10 steps\n',
                ''.join(line + '\n' for line in extra_lines) + 'SCF run converged in 10 steps\n'
            )

        base_kwargs = dict(executable=self.exe, frame=0,
                           element_masses={'Ga': 69.723, 'O': 15.9994, 'H': 1.0079},
                           multiplicity=1, confirm_reference=True,
                           thermo_model='vibrational-only', active_atoms='4')

        # 1. Smearing / electronic entropy cases: missing (null), explicit zero, nonzero, damaged.
        self.sp.write_text(make_sp('  - Atoms:   4', ' CELL| Periodicity   XYZ', ' POISSON| Periodicity   XYZ'))
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(shermo_3)):
            res_missing = run_shermo(self.cp2k, self.xyz, energy_output=self.sp, **base_kwargs)
        sel = res_missing['cp2k_reference']['selected_electronic_energy']
        self.assertEqual(sel['electronic_entropic_energy'],
                         {'status': 'missing', 'value': None, 'unit': 'hartree', 'sources': []})
        self.assertEqual(sel['smearing_free_energy_correction'],
                         {'status': 'missing', 'value': None, 'unit': 'hartree', 'sources': []})
        self.assertEqual(sel['extrapolated_t0_energy'],
                         {'status': 'missing', 'value': None, 'unit': 'hartree', 'sources': []})
        self.assertEqual(sel['extrapolated_sigma0_energy'],
                         {'status': 'missing', 'value': None, 'unit': 'hartree', 'sources': []})
        self.assertEqual(sel['atom_count']['value'], 4)
        self.assertEqual(sel['periodicity']['value'], 'XYZ')

        # Explicit zero Fermi-Dirac entropy and explicit zero Gaussian/MP/MV smearing correction stay distinct.
        self.sp.write_text(make_sp(
            '  - Atoms:   4', ' CELL| Periodicity   XYZ',
            '  Electronic entropic energy:    -0.00000000000000',
            '  Total energy (extrapolated to T->0):  -2.00000000000000',
        ))
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(shermo_3)):
            res_zero = run_shermo(self.cp2k, self.xyz, energy_output=self.sp, **base_kwargs)
        sel_zero = res_zero['cp2k_reference']['selected_electronic_energy']
        self.assertEqual(sel_zero['electronic_entropic_energy']['status'], 'parsed')
        self.assertEqual(sel_zero['electronic_entropic_energy']['value'], 0.0)
        self.assertEqual(sel_zero['smearing_free_energy_correction']['status'], 'missing')
        self.assertIsNone(sel_zero['smearing_free_energy_correction']['value'])
        self.assertEqual(sel_zero['extrapolated_t0_energy']['value'], -2.0)

        self.sp.write_text(make_sp(
            '  - Atoms:   4', ' CELL| Periodicity   XYZ',
            '  Smearing free energy correction:    0.00000000000000',
            '  Total energy (extrapolated to sigma->0):  -2.00000000000000',
        ))
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(shermo_3)):
            res_smear_zero = run_shermo(self.cp2k, self.xyz, energy_output=self.sp, **base_kwargs)
        sel_sz = res_smear_zero['cp2k_reference']['selected_electronic_energy']
        self.assertEqual(sel_sz['smearing_free_energy_correction']['status'], 'parsed')
        self.assertEqual(sel_sz['smearing_free_energy_correction']['value'], 0.0)
        self.assertEqual(sel_sz['electronic_entropic_energy']['status'], 'missing')
        self.assertIsNone(sel_sz['electronic_entropic_energy']['value'])
        self.assertEqual(sel_sz['extrapolated_sigma0_energy']['value'], -2.0)

        # Reject nonzero entropy/smearing correction, differing T->0 or sigma->0 extrapolation,
        # damaged field delimiters/brackets, atom-count & periodicity conflicts.
        bad_sp_cases = (
            ('nonzero electronic entropic energy',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Electronic entropic energy:   -0.00015332267878')),
            ('nonzero smearing free energy correction',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Smearing free energy correction:   -0.00025000000000')),
            ('differing from Total FORCE_EVAL',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Total energy (extrapolated to T->0):  -1.99990000000000')),
            ('sigma->0 extrapolated energy.*differing from Total FORCE_EVAL',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Total energy (extrapolated to sigma->0):  -1.99985000000000')),
            ('damaged electronic entropic energy',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Electronic entropic energy -0.00015332267878')),
            ('damaged electronic entropic energy',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Electronic entropic energy [hartree: -0.00015332267878')),
            ('damaged electronic entropic energy',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Electronic entropic energy:   ***')),
            ('unusable electronic entropic energy',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Electronic entropic energy:   1e-999')),
            ('damaged smearing free energy correction',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Smearing free energy correction -0.00025')),
            ('damaged smearing free energy correction',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Smearing free energy correction [hartree: 0.0')),
            ('damaged T->0 extrapolated energy',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Total energy (extrapolated to T->0):  -2.0 extra')),
            ('damaged sigma->0 extrapolated energy',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Total energy (extrapolated to sigma->0) -2.0')),
            ('damaged sigma->0 extrapolated energy',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', '  Total energy (extrapolated to sigma->0: -2.0')),
            ('reports 1 total atoms, conflicting with 4',
             make_sp('  - Atoms: 1', ' CELL| Periodicity XYZ')),
            ('reports 3 total atoms, conflicting with 4',
             make_sp('  - Atoms: 3', ' CELL| Periodicity XYZ')),
            ('damaged total atom-count',
             make_sp('  - Atoms: 0', ' CELL| Periodicity XYZ')),
            ('damaged total atom-count',
             make_sp('  - Atoms 4', ' CELL| Periodicity XYZ')),
            ('conflicts with vibration segment periodicity',
             make_sp('  - Atoms: 4', ' POISSON| Periodicity NONE')),
            ('malformed periodicity',
             make_sp('  - Atoms: 4', ' POISSON| Periodicity: XY')),
            ('malformed periodicity',
             make_sp('  - Atoms: 4', ' POISSON| Periodicity XYZ extra')),
            ('conflicting periodicity',
             make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', ' POISSON| Periodicity NONE')),
        )
        out_path = self.root / 'must-not-exist.json'
        with patch('cp2kkit.thermochemistry.subprocess.run') as run:
            for pattern, text in bad_sp_cases:
                with self.subTest(pattern=pattern, sample=text.splitlines()[4]):
                    self.sp.write_text(text)
                    with self.assertRaisesRegex(KitError, pattern):
                        run_shermo(self.cp2k, self.xyz, energy_output=self.sp, **base_kwargs)
            # CLI leaves no result file and never launches Shermo on smearing/damaged rejection.
            for cli_line in (
                '  Smearing free energy correction:   -0.00025000000000',
                '  Total energy (extrapolated to sigma->0):  -1.99985000000000',
                '  Electronic entropic energy -0.00015332267878',
                '  Electronic entropic energy [hartree: -0.00015332267878',
            ):
                self.sp.write_text(make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ', cli_line))
                with redirect_stderr(io.StringIO()):
                    code = main(['thermochemistry', str(self.cp2k), '--shermo', str(self.exe),
                                 '--geometry', str(self.xyz), '--frame', '0',
                                 '--thermo-model', 'vibrational-only', '--active-atoms', '4',
                                 '--element-masses', 'Ga=69.723', 'O=15.9994', 'H=1.0079',
                                 '--energy-output', str(self.sp), '--multiplicity', '1',
                                 '--confirm-reference', '-o', str(out_path)])
                self.assertEqual(code, 2)
                self.assertFalse(out_path.exists())
            run.assert_not_called()

        # 2. Multi-segment isolation: bad unselected segment 1 (including Gaussian/MP/MV smearing)
        # must not taint clean selected segment 2.
        bad_seg1 = make_sp('  - Atoms: 3', ' CELL| Periodicity NONE',
                           '  Smearing free energy correction:   -0.123456',
                           '  Total energy (extrapolated to sigma->0):  -1.5')
        clean_seg2 = make_sp('  - Atoms: 4', ' CELL| Periodicity XYZ',
                             '  Smearing free energy correction:    0.00000000000000')
        self.sp.write_text(bad_seg1 + clean_seg2)
        with patch('cp2kkit.thermochemistry.subprocess.run', side_effect=self.fake(shermo_3)):
            res_seg2 = run_shermo(self.cp2k, self.xyz, energy_output=self.sp, energy_segment=2, **base_kwargs)
        self.assertEqual(res_seg2['cp2k_reference']['selected_electronic_energy']['segment'], 2)
        self.assertEqual(res_seg2['cp2k_reference']['selected_electronic_energy']['smearing_free_energy_correction']['value'], 0.0)
        self.assertIsNone(res_seg2['cp2k_reference']['selected_electronic_energy']['electronic_entropic_energy']['value'])

        # 3. Single-point periodicity conflict against reference XYZ even when vibration periodicity is unprinted.
        self.cp2k.write_text(surface_cp2k.replace(' CELL| Periodicity                                                           XYZ\n', '')
                             .replace(' POISSON| Periodicity                                                        XYZ\n', ''))
        self.sp.write_text(make_sp('  - Atoms: 4', ' POISSON| Periodicity NONE'))
        with patch('cp2kkit.thermochemistry.subprocess.run') as run:
            with self.assertRaisesRegex(KitError, 'conflicts with reference XYZ periodicity'):
                run_shermo(self.cp2k, self.xyz, energy_output=self.sp, **base_kwargs)
            run.assert_not_called()
