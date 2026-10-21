"""Synthetic GFN-xTB generation/interface tests; no CP2K/tblite execution.

Parameter-byte fixtures below are invented text. Patched expected hashes test
plumbing/protection only, not real parameter compatibility or numerical science.
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import build_parser, main
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.input_editor import FIELDS, applicable_entries
from cp2kkit.input_tui import command_arguments, parse_value, run_interactive
from cp2kkit.inputgen import InputSettings, automatic_multiplicity, generate_input, write_input
from cp2kkit.structure import Structure, read_restart, read_structure
from cp2kkit.xtb import METHODS, XTB_COUNTS, XTB_NUMBERS, parse_method
from tests.test_input_tui import TTY


class XtbTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root/'water.xyz'
        self.source.write_text('3\nsynthetic\nO 0 0 0\nH .76 0 .58\nH -.76 0 .58\n')
        self.water = read_structure(self.source)
        self.output = self.root/'water.inp'
        self.settings = InputSettings(periodic='NONE', method='GFN1-xTB', write_json=True)
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def settings_for(self, method, **kwargs):
        return replace(self.settings, method=method,
                       **({'scf': 'diag', 'tblite_available': True} if method == 'GFN2-xTB' else {}), **kwargs)

    def test_numbers_names_and_namespace_boundaries(self):
        self.assertEqual(XTB_NUMBERS, {30: 'GFN1-xTB', 31: 'GFN0-xTB', 32: 'GFN2-xTB'})
        for number, name in XTB_NUMBERS.items():
            self.assertEqual(parse_value(FIELDS['method'], str(number)), name)
            self.assertEqual(parse_method(name.lower()), name)
            self.assertEqual(InputSettings.from_config({'method': name.lower()}).method, name)
        for raw in ('1', '2', '3', '4', 'GFN3-xTB', '32', 'PBE0', 'GFN2\n&HF'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_method(raw)
        for raw in ('1', '2', '3', '4', '33'):
            with self.assertRaises(ValueError):
                parse_value(FIELDS['method'], raw)

    def test_three_models_and_tasks_deterministic_balanced_and_no_dft_payload(self):
        for method in METHODS[1:]:
            for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
                with self.subTest(method=method, task=task):
                    settings = replace(self.settings_for(method), run_type=task)
                    text, report = generate_input(self.water, settings)
                    self.assertEqual((text, report), generate_input(self.water, settings))
                    self.assertEqual(report['explicit_electron_count'], 8)
                    self.assertEqual(report['electron_count_model'], 'xtb_reference_occupation')
                    self.assertIsNone(report['valence_electron_count'])
                    self.assertFalse(report['runtime_validated'])
                    self.assertFalse(report['method_profile']['build_verified'])
                    self.assertEqual(report['input_sha256'], hashlib.sha256(text.encode()).hexdigest())
                    self.assertEqual(report['basis_validation']['status'], 'not_applicable')
                    for token in ('&XC', '&MGRID', '&POISSON', '&KIND', 'BASIS_SET', 'POTENTIAL ',
                                  '&VDW_POTENTIAL', '&KPOINTS', 'CHECK_ATOMIC_CHARGES F'):
                        self.assertNotIn(token, text)
                    stack = []
                    for line in text.splitlines():
                        line = line.strip()
                        if line.startswith('&END'):
                            self.assertEqual(stack.pop(), line.split()[1])
                        elif line.startswith('&'):
                            stack.append(line.split()[0][1:])
                    self.assertFalse(stack)
                    self.assertEqual('&MOTION' in text, task == 'GEO_OPT')
                    restored = InputSettings.from_config(report)
                    self.assertEqual((text, report), generate_input(self.water, restored))

    def test_native_gfn1_ot_diag_controls(self):
        text, report = generate_input(self.water, replace(self.settings, eps_scf=2e-7, max_scf=33, max_outer_scf=7, ot_algorithm='IRAC'))
        for token in ('GFN_TYPE 1', 'PARAM_FILE_NAME xTB1_parameters', 'DISPERSION_PARAMETER_FILE dftd3.dat',
                      'PRECONDITIONER FULL_SINGLE_INVERSE', 'ALGORITHM IRAC', 'EPS_SCF 2.0E-07', 'MAX_SCF 33', 'MAX_SCF 7'):
            self.assertIn(token, text)
        self.assertEqual(report['method_profile']['intrinsic_dispersion'], 'D3(BJ)')
        diag, _ = generate_input(self.water, replace(self.settings, scf='diag'))
        self.assertIn('&DIAGONALIZATION', diag)
        self.assertIn('METHOD BROYDEN_MIXING', diag)
        self.assertNotIn('&OT', diag)

    def test_gfn0_is_non_scc_but_diagonalizes_once(self):
        text, report = generate_input(self.water, self.settings_for('GFN0-xTB'))
        for token in ('EPS_SCF', 'MAX_SCF', '&MIXING', '&OUTER_SCF', '&OT', 'ACCURACY', 'dftd3.dat'):
            self.assertNotIn(token, text)
        self.assertIn('GFN_TYPE 0', text)
        self.assertIn('&DIAGONALIZATION', text)
        self.assertIsNone(report['effective_eps_scf'])
        self.assertFalse(report['method_profile']['self_consistent'])
        self.assertEqual(report['method_profile']['intrinsic_dispersion'], 'D4')
        for kwargs in ({'eps_scf': 1e-8}, {'max_scf': 1}, {'max_outer_scf': 1}, {'ot_algorithm': 'STRICT'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(KitError):
                generate_input(self.water, replace(self.settings_for('GFN0-xTB'), **kwargs))

    def test_gfn2_backend_assertion_solver_and_accuracy(self):
        for settings, message in ((replace(self.settings, method='GFN2-xTB', scf='diag'), 'tblite-linked'),
                                  (replace(self.settings, method='GFN2-xTB'), 'tblite-linked')):
            with self.assertRaisesRegex(KitError, message):
                generate_input(self.water, settings)
        text, report = generate_input(self.water, replace(self.settings_for('GFN2-xTB'), xtb_accuracy=.1, eps_scf=3e-8, max_scf=140))
        for token in ('GFN_TYPE TBLITE', '&TBLITE', 'METHOD GFN2', 'SCC_MIXER AUTO', 'ACCURACY 0.100', 'MAX_SCF 140'):
            self.assertIn(token, text)
        self.assertNotIn('&MIXING', text)
        self.assertNotIn('&PARAMETER', text)
        self.assertEqual(report['method_profile']['accuracy'], .1)
        self.assertEqual(report['effective_eps_scf'], 3e-8)
        self.assertEqual(report['method_profile']['backend'], 'tblite')
        self.assertEqual(report['method_profile']['data_validation'], 'backend_unchecked')
        self.assertEqual(report['data_sources'], {})

    def test_reference_counts_not_gth_and_charge_parity(self):
        self.assertEqual(len(XTB_COUNTS), 86)
        for element, count in (('Li', 1), ('Na', 1), ('Mg', 2), ('Fe', 8), ('Zn', 2), ('La', 3), ('Lu', 3), ('Rn', 8)):
            atom = Structure([element]*2, [[0., 0., 0.], [2., 0., 0.]], None, None, {'path': 'synthetic.xyz'})
            for method in METHODS[1:]:
                with self.subTest(element=element, method=method):
                    _, report = generate_input(atom, self.settings_for(method))
                    self.assertEqual(report['explicit_electron_count'], 2*count)
        self.assertEqual(automatic_multiplicity(self.water, replace(self.settings, charge=1)), 2)
        for changes in ({'charge': 1}, {'multiplicity': 3}, {'charge': 8}, {'charge': 1, 'multiplicity': 1},
                        {'multiplicity': True}, {'charge': 0.5}):
            with self.subTest(changes=changes), self.assertRaises(KitError):
                generate_input(self.water, replace(self.settings, **changes))
        _, report = generate_input(self.water, replace(self.settings, charge=2))
        self.assertEqual(report['explicit_electron_count'], 6)
        atom = Structure(['U'], [[0., 0., 0.]], None, None, {'path': 'synthetic.xyz'})
        with self.assertRaisesRegex(KitError, 'H-Rn'):
            generate_input(atom, self.settings)

    def test_invalid_combinations_do_not_silently_change_physics(self):
        bad = ({'method': 'GFN3-xTB'}, {'cp2k_version': '2024.1'}, {'run_type': 'CELL_OPT'},
               {'periodic': 'XYZ', 'cell': (10., 10., 10.)}, {'kpoints': (2, 1, 1)},
               {'density_difference': True}, {'electron_density': True}, {'spin_density': True},
               {'cube_stride': (1, 1, 1)}, {'magnetism': ()}, {'dft_plus_u': (('O', 1, 2.),)},
               {'functional': 'SCAN'}, {'basis': 'ae-6-31g-star'}, {'dispersion': 'd3bj'},
               {'basis_overrides': (('O', 'molopt-sr-dzvp'),)}, {'basis_files': ('data',)},
               {'potential_files': ('data',)}, {'custom_basis_name': 'test'}, {'cutoff': 500.},
               {'libxc_available': True}, {'allow_pbe_potential': True}, {'smearing': 300.},
               {'added_mos': 5}, {'xtb_accuracy': .1}, {'eps_scf': float('nan')},
               {'xtb_accuracy': float('inf')}, {'xtb_accuracy': True}, {'trust_radius': -1.},
               {'kpoints': (True, True, True)}, {'added_mos': False}, {'pressure': float('nan')},
               {'max_scf': True}, {'max_iter': 0}, {'tblite_available': 'yes'}, {'project': 'bad\n&HF'})
        for kwargs in bad:
            with self.subTest(kwargs=kwargs), self.assertRaises(KitError):
                generate_input(self.water, replace(self.settings, **kwargs))
        with self.assertRaisesRegex(KitError, 'Periodicity is unknown'):
            generate_input(self.water, replace(self.settings, periodic=None))

    def test_geometry_constraints_round_trip_and_source_unchanged(self):
        original = self.water.to_dict()
        for method in METHODS[1:]:
            s = replace(self.settings_for(method), run_type='GEO_OPT', fixed_atoms='1,3', trust_radius=.35)
            text, report = generate_input(self.water, s)
            self.output.write_text(text)
            parsed = read_restart(self.output)
            self.assertEqual(parsed.positions, report['generated_structure']['positions'])
            self.assertEqual(parsed.cell, report['generated_structure']['cell'])
            self.assertEqual(report['constraints']['fixed_atoms'], [1, 3])
            self.assertIn('TRUST_RADIUS [angstrom] 0.35', text)
            self.assertIn('LIST 1 3', text)
            self.assertEqual(self.water.to_dict(), original)
        for water in (replace(self.water, positions=[[float('nan'), 0., 0.]]*3),
                      replace(self.water, positions=[]), replace(self.water, cell=[[0.]*3]*3)):
            with self.assertRaises(KitError):
                generate_input(water, self.settings)

    def synthetic_data(self, method):
        from cp2kkit.xtb import PARAMETER_HASHES
        root = self.root/'synthetic data'
        root.mkdir(exist_ok=True)
        hashes = dict(PARAMETER_HASHES)
        for name in ('xTB0_parameters', 'xTB1_parameters', 'dftd3.dat'):
            content = f'SYNTHETIC hash plumbing only: {name}\n'
            (root/name).write_text(content)
            hashes[name] = hashlib.sha256(content.encode()).hexdigest()
        return root, hashes

    def test_data_hashes_paths_and_missing_modified_data(self):
        data, hashes = self.synthetic_data('GFN1-xTB')
        with self.assertRaisesRegex(KitError, 'pinned'):
            generate_input(self.water, replace(self.settings, data_dir=str(data)))
        with patch('cp2kkit.xtb.PARAMETER_HASHES', hashes):
            text, report = generate_input(self.water, replace(self.settings, data_dir=str(data)))
            self.assertIn(f'PARAM_FILE_NAME "{data}/xTB1_parameters"', text)
            self.assertEqual(report['method_profile']['data_validation'], 'source_bytes_checked')
            self.assertEqual(report['data_sources']['xTB1_parameters']['sha256'], hashes['xTB1_parameters'])
            with patch.dict(os.environ, CP2K_DATA_DIR=str(data)):
                env_text, env_report = generate_input(self.water, self.settings)
                self.assertEqual(text, env_text)
                self.assertEqual(report['data_sources'], env_report['data_sources'])
            (data/'xTB1_parameters').unlink()
            with self.assertRaises(KitError):
                generate_input(self.water, replace(self.settings, data_dir=str(data)))

    def test_writer_protects_inputs_json_symlinks_and_data(self):
        write_input(self.water, self.settings, self.output)
        before = self.output.read_bytes()
        with self.assertRaises(OutputExists):
            write_input(self.water, self.settings, self.output)
        self.assertEqual(self.output.read_bytes(), before)
        link = self.root/'link.inp'
        link.symlink_to(self.output)
        with self.assertRaises(OutputExists):
            write_input(self.water, replace(self.settings, write_json=False), link)
        with self.assertRaises(KitError):
            write_input(self.water, self.settings, self.source)
        data, hashes = self.synthetic_data('GFN1-xTB')
        with patch('cp2kkit.xtb.PARAMETER_HASHES', hashes), self.assertRaisesRegex(KitError, 'source/data'):
            write_input(self.water, replace(self.settings, data_dir=str(data)), data/'xTB1_parameters')
        with patch('cp2kkit.inputgen.os.replace', side_effect=OSError('synthetic publication failure')):
            with self.assertRaises(OSError):
                write_input(self.water, replace(self.settings, write_json=False), self.output)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertFalse(list(self.root.glob('.*.tmp')))

    def test_cli_config_replay_and_subprocess(self):
        for method in METHODS[1:]:
            s = self.settings_for(method)
            output = self.root/(method+'.inp')
            args = command_arguments(str(self.source), -1, str(output), s)
            parsed = build_parser().parse_args(args[3:])
            restored = InputSettings.from_config({n: getattr(parsed, n) for n in InputSettings.__dataclass_fields__})
            self.assertEqual(generate_input(self.water, s), generate_input(self.water, restored))
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(args[3:]), 0)
            report = json.loads(Path(str(output)+'.json').read_text())
            self.assertEqual(report['method_profile']['model'], method)
        target = self.root/'subprocess.inp'
        result = subprocess.run([sys.executable, '-m', 'cp2kkit', 'generate-input', str(self.source),
                                 '-o', str(target), '--periodic', 'NONE', '--method', 'GFN0-xTB'],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('GFN_TYPE 0', target.read_text())
        self.assertFalse(Path(str(target)+'.json').exists())

    def test_version_model_task_matrix_and_target_specific_syntax(self):
        from cp2kkit.xtb_versions import XTB_TARGETS
        for target in XTB_TARGETS:
            for method in METHODS[1:]:
                unsupported = (method == 'GFN0-xTB' and target.startswith('2024') or
                               method == 'GFN2-xTB' and target in {'2024.2', '2024.3', '2025.1'})
                for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
                    with self.subTest(target=target, method=method, task=task):
                        s = replace(self.settings_for(method), cp2k_version=target, run_type=task)
                        if unsupported:
                            with self.assertRaisesRegex(KitError, 'requires CP2K'):
                                generate_input(self.water, s)
                            continue
                        text, report = generate_input(self.water, s)
                        self.assertEqual((text, report), generate_input(self.water, InputSettings.from_config(report)))
                        source = report['method_profile']['version_compatibility']['sources']['input']
                        self.assertIn(f'/v{target}/src/input_cp2k_tb.F', source['url'])
                        self.assertEqual(len(source['sha256']), 64)
                        self.assertFalse(report['runtime_validated'])
                        if target.startswith('2024'):
                            self.assertIn('PARAM_FILE_NAME xTB_parameters', text)
                            self.assertNotIn('GFN_TYPE', text)
                        elif method != 'GFN2-xTB':
                            self.assertIn('GFN_TYPE '+('0' if method == 'GFN0-xTB' else '1'), text)
                        if method == 'GFN2-xTB' and target != '2026.2':
                            self.assertIn('&TBLITE T', text)
                            self.assertNotIn('GFN_TYPE', text)
                            self.assertNotIn('ACCURACY', text)
                            self.assertNotIn('SCC_MIXER', text)
                            self.assertIn('METHOD DIRECT_P_MIXING', text)
                            self.assertIn('ALPHA 0.2', text)
                            self.assertIsNone(report['method_profile']['accuracy'])

    def test_gfn2_modern_ot_keeps_default_and_convergence_semantics(self):
        # Modern target keeps default OT; legacy defaults are rejected below.
        s = replace(self.settings, method='GFN2-xTB', tblite_available=True,
                    eps_scf=2e-7, max_scf=31, max_outer_scf=9, ot_algorithm='IRAC')
        text, report = generate_input(self.water, s)
        self.assertIn('&OT', text)
        self.assertIn('PRECONDITIONER FULL_SINGLE_INVERSE', text)
        self.assertIn('ALGORITHM IRAC', text)
        self.assertIn('MAX_SCF 31', text)
        self.assertIn('MAX_SCF 9', text)
        self.assertNotIn('SCC_MIXER', text)
        self.assertNotIn('&DIAGONALIZATION', text)
        self.assertEqual(report['method_profile']['convergence_control'], 'CP2K EPS_SCF')
        self.assertIsNone(report['method_profile']['scc_mixer'])
        self.assertIn('GFN_TYPE TBLITE', text)
        self.assertIn('ACCURACY 1', text)
        self.assertEqual(report['method_profile']['accuracy_role'], 'numerical setup only')
        auto, _ = generate_input(self.water, replace(self.settings, method='GFN2-xTB',
                                                   tblite_available=True))
        self.assertIn('MAX_SCF 25', auto)
        self.assertIn('MAX_SCF 20', auto)

    def test_legacy_gfn2_ot_gate_is_shared_by_api_config_and_writer(self):
        from cp2kkit.xtb_versions import version_profile
        self.output.write_text('preserve existing input\n')
        for target in ('2025.2', '2026.1'):
            self.assertFalse(version_profile(target, 'GFN2-xTB')['gfn2_ot_enabled'])
            for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
                for algorithm in (None, 'STRICT', 'IRAC'):
                    with self.subTest(target=target, task=task, algorithm=algorithm):
                        s = replace(self.settings, method='GFN2-xTB', cp2k_version=target,
                                    tblite_available=True, run_type=task, ot_algorithm=algorithm)
                        before = asdict(s)
                        restored = InputSettings.from_config(before)
                        for request in (s, restored):
                            with self.assertRaisesRegex(KitError, 'OT is disabled.*'+target):
                                generate_input(self.water, request)
                        with self.assertRaisesRegex(KitError, '--scf diag'):
                            write_input(self.water, s, self.output)
                        self.assertEqual(asdict(s), before)
                        self.assertEqual(self.output.read_text(), 'preserve existing input\n')
                        self.assertFalse(Path(str(self.output)+'.json').exists())
            diag_settings = replace(s, scf='diag', ot_algorithm=None)
            diag, manifest = generate_input(self.water, diag_settings)
            with self.assertRaisesRegex(KitError, 'no ACCURACY keyword'):
                generate_input(self.water, replace(diag_settings, xtb_accuracy=.1))
            self.assertIn('METHOD DIRECT_P_MIXING', diag)
            self.assertNotIn('&OT', diag)
            self.assertEqual(manifest['settings']['scf'], 'diag')
            self.assertFalse(manifest['method_profile']['version_compatibility']['gfn2_ot_enabled'])
        _, modern = generate_input(self.water, replace(self.settings, method='GFN2-xTB', tblite_available=True))
        self.assertTrue(modern['method_profile']['version_compatibility']['gfn2_ot_enabled'])
        self.assertFalse(modern['runtime_validated'])
        self.assertFalse(list(self.root.glob('.*.tmp')))

    def test_legacy_gfn2_ot_cli_rejects_without_replacing_or_creating_files(self):
        self.output.write_text('existing input\n')
        new_output = self.root/'new.inp'
        for target in ('2025.2', '2026.1'):
            for output in (self.output, new_output):
                for selector in ([], ['--scf', 'ot']):
                    with self.subTest(target=target, output=output, selector=selector):
                        errors = io.StringIO()
                        with redirect_stderr(errors):
                            code = main(['generate-input', str(self.source), '-o', str(output),
                                         '--method', 'GFN2-xTB', '--cp2k-version', target,
                                         '--periodic', 'NONE', '--tblite-available', '--write-json', *selector])
                        self.assertEqual(code, 2)
                        self.assertIn('--scf diag', errors.getvalue())
                        self.assertIn('does not upgrade the executable', errors.getvalue())
                        self.assertEqual(self.output.read_text(), 'existing input\n')
                        self.assertFalse(new_output.exists())
                        self.assertFalse(Path(str(output)+'.json').exists())

    def test_legacy_gfn2_tui_requires_explicit_solver_change(self):
        for target in ('2025.2', '2026.1'):
            output = self.root/(target+'.inp')
            settings = replace(self.settings, method='GFN2-xTB', cp2k_version=target,
                               tblite_available=True)
            log = TTY()
            run_interactive(str(self.source), -1, str(output), settings,
                            stdin=TTY('0\nq\n'), stdout=log, plain=True)
            self.assertIn('--scf diag', log.getvalue())
            self.assertFalse(output.exists())
            self.assertFalse(Path(str(output)+'.json').exists())
            run_interactive(str(self.source), -1, str(output), settings,
                            stdin=TTY('320\ndiag\n0\n'), stdout=TTY(), plain=True)
            self.assertIn('&DIAGONALIZATION', output.read_text())
            self.assertNotIn('&OT', output.read_text())
            manifest = json.loads(Path(str(output)+'.json').read_text())
            self.assertEqual(manifest['settings']['scf'], 'diag')
            self.assertEqual(manifest['target_version'], target)

    def test_version_specific_data_files_hashes_and_no_alias_fallback(self):
        from cp2kkit.xtb import parameter_hashes, PARAMETER_HASHES
        from cp2kkit.xtb_versions import XTB_TARGETS
        self.assertNotEqual(parameter_hashes('2024.2')['dftd3.dat'], PARAMETER_HASHES['dftd3.dat'])
        for target in XTB_TARGETS:
            root = self.root/target
            root.mkdir()
            name = 'xTB_parameters' if target.startswith('2024') else 'xTB1_parameters'
            expected = {}
            for file in (name, 'dftd3.dat'):
                payload = f'SYNTHETIC {target} {file}\n'
                (root/file).write_text(payload)
                expected[file] = hashlib.sha256(payload.encode()).hexdigest()
            s = replace(self.settings, cp2k_version=target, data_dir=str(root))
            with patch('cp2kkit.xtb.parameter_hashes', return_value=expected):
                text, report = generate_input(self.water, s)
                self.assertEqual(set(report['data_sources']), {name, 'dftd3.dat'})
                self.assertEqual(report['method_profile']['expected_data_sha256'], expected)
                self.assertIn('PARAM_FILE_NAME '+str(root/name), text)
                (root/name).rename(root/'wrong-name')
                with self.assertRaises(KitError):
                    generate_input(self.water, s)

    def test_old_version_constraints_and_trajectory_boundaries(self):
        from cp2kkit.xtb_versions import XTB_TARGETS, SOURCE_HASHES
        for target in XTB_TARGETS:
            s = replace(self.settings, cp2k_version=target, run_type='GEO_OPT', fixed_atoms='1,3')
            text, report = generate_input(self.water, s)
            self.assertIn('LIST 1 3', text)
            self.assertEqual(report['constraints']['keyword_reference']['target'], target)
            self.assertEqual(report['constraints']['keyword_reference']['sha256'], SOURCE_HASHES[target]['constraints'])
            self.assertIn('FORMAT XYZ', text)
            if target.startswith('2026'):
                text, _ = generate_input(self.water, replace(s, trajectory_format='EXTXYZ'))
                self.assertIn('FORMAT EXTXYZ', text)
            else:
                with self.assertRaisesRegex(KitError, 'EXTXYZ.*2026.1'):
                    generate_input(self.water, replace(s, trajectory_format='EXTXYZ'))

    def test_version_dependent_menu_fields_and_cli_replay(self):
        for target in ('2025.2', '2026.1', '2026.2'):
            s = replace(self.settings, method='GFN2-xTB', tblite_available=True, cp2k_version=target)
            values = {**asdict(s), 'path': str(self.source), 'frame': -1}
            visible = {entry.field for entry in applicable_entries(values)}
            self.assertTrue({'ot_algorithm', 'max_outer_scf', 'tblite_available'} <= visible)
            self.assertEqual('xtb_accuracy' in visible, target == '2026.2')
            replay = command_arguments(self.source, -1, self.output, s)
            args = build_parser().parse_args(replay[3:])
            restored = InputSettings.from_config({name: getattr(args, name) for name in InputSettings.__dataclass_fields__})
            if target == '2026.2':
                self.assertEqual(generate_input(self.water, s), generate_input(self.water, restored))
            else:
                for request in (s, restored):
                    with self.assertRaisesRegex(KitError, '--scf diag'):
                        generate_input(self.water, request)
        log = TTY()
        run_interactive(str(self.source), -1, str(self.output),
                        replace(self.settings, cp2k_version='2024.2'),
                        stdin=TTY('1\n30\np\n\n0\n'), stdout=log, plain=True)
        self.assertIn('PARAM_FILE_NAME xTB_parameters', self.output.read_text())
        self.assertNotIn('GFN_TYPE', self.output.read_text())
        output = self.root/'default-gfn2-ot.inp'
        run_interactive(str(self.source), -1, str(output), self.settings,
                        stdin=TTY('1\n32\n141\ny\n0\n'), stdout=TTY(), plain=True)
        self.assertIn('&OT', output.read_text())
        self.assertNotIn('SCC_MIXER', output.read_text())

    def test_unavailable_model_versions_fail_before_input_publication(self):
        self.output.write_text('preserve existing input\n')
        for target, method in (('2024.2', 'GFN0-xTB'), ('2024.3', 'GFN0-xTB'),
                               ('2024.2', 'GFN2-xTB'), ('2024.3', 'GFN2-xTB'), ('2025.1', 'GFN2-xTB')):
            with self.subTest(target=target, method=method), redirect_stderr(io.StringIO()):
                result = main(['generate-input', str(self.source), '-o', str(self.output),
                               '--method', method, '--cp2k-version', target, '--periodic', 'NONE',
                               '--tblite-available', '--write-json'])
                self.assertEqual(result, 2)
                self.assertEqual(self.output.read_text(), 'preserve existing input\n')
                self.assertFalse(Path(str(self.output)+'.json').exists())

    def test_cli_invalid_combinations_preserve_existing_input(self):
        self.output.write_text('existing input must survive validation failure\n')
        before = self.output.read_bytes()
        for extra in (['--method', 'GFN2-xTB'],
                      ['--method', 'GFN1-xTB', '--dispersion', 'd3'],
                      ['--method', 'GFN0-xTB', '--max-scf', '1']):
            with self.subTest(extra=extra), redirect_stderr(io.StringIO()):
                self.assertEqual(main(['generate-input', str(self.source), '-o', str(self.output),
                                       '--periodic', 'NONE', '--write-json', *extra]), 2)
            self.assertEqual(self.output.read_bytes(), before)
            self.assertFalse(Path(str(self.output)+'.json').exists())

    def test_tui_common_method_numbers_review_and_generate(self):
        for number, method in XTB_NUMBERS.items():
            output = self.root/(method+'.inp')
            setup = '320\ndiag\n141\ny\n142\n0.2\n' if number == 32 else ''
            log = TTY()
            self.assertEqual(run_interactive(str(self.source), -1, str(output), InputSettings(periodic='NONE', write_json=True),
                             stdin=TTY(f'1\n{number}\n'+setup+'p\n\n0\n'), stdout=log, plain=True), 0)
            report = json.loads(Path(str(output)+'.json').read_text())
            self.assertEqual(report['method_profile']['model'], method)
            self.assertIn('30. GFN1-xTB', log.getvalue())
            self.assertIn('31. GFN0-xTB', log.getvalue())
            self.assertIn('32. GFN2-xTB', log.getvalue())
            self.assertIn('backend:', log.getvalue())

    def test_tui_applicability_cannot_be_bypassed_and_dft_restoration(self):
        values = {**asdict(self.settings_for('GFN0-xTB')), 'path': str(self.source), 'frame': -1}
        visible = {entry.field for entry in applicable_entries(values)}
        self.assertTrue({'functional', 'method', 'charge', 'multiplicity'} <= visible)
        self.assertFalse({'basis', 'cutoff', 'eps_scf', 'density_difference', 'electron_density', 'tblite_available'} & visible)
        log = TTY()
        run_interactive(str(self.source), -1, str(self.output), self.settings,
                        stdin=TTY('140\n31\n301\n110\n1\n0\n'), stdout=log, plain=True)
        self.assertIn('not applicable', log.getvalue())
        report = json.loads(Path(str(self.output)+'.json').read_text())
        self.assertEqual(report['settings']['method'], 'DFT')
        self.assertIn('METHOD GPW', self.output.read_text())


if __name__ == '__main__':
    unittest.main()
