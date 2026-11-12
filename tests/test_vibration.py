"""Hand-written water/ion fixtures and synthetic data; never execute CP2K."""
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.basis_registry import OPTIONS
from cp2kkit.cli import main
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.input_tui import command_arguments, run_interactive
from cp2kkit.inputgen import FUNCTIONALS, InputSettings, generate_input, write_input
from cp2kkit.structure import Structure, read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry
from tests.test_input_tui import TTY


class VibrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root/'water.xyz'
        self.path.write_text('3\nsynthetic, not optimized\nO 0 0 0\nH .76 0 .58\nH -.76 0 .58\n')
        self.water = read_structure(self.path)
        self.settings = InputSettings(run_type='VIBRATIONAL_ANALYSIS', periodic='NONE')
        self.output = self.root/'freq.inp'
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def generate(self, **changes):
        return generate_input(self.water, replace(self.settings, **changes))

    def test_default_task_nesting_units_and_provenance(self):
        text, m = self.generate()
        self.assertIn('RUN_TYPE VIBRATIONAL_ANALYSIS\n', text)
        self.assertIn('&END FORCE_EVAL\n&VIBRATIONAL_ANALYSIS\n', text)
        self.assertIn('DX [bohr] 0.01\n', text)
        for line in ('NPROC_REP 1', 'FULLY_PERIODIC F', 'INTENSITIES F', 'THERMOCHEMISTRY F',
                     'UKS F', 'MULTIPLICITY 1', 'EPS_DEFAULT 1.0E-14', 'CUTOFF [Ry] 400', 'REL_CUTOFF [Ry] 55'):
            self.assertIn(line, text)
        self.assertEqual(text.count('EPS_SCF 1.0E-08\n'), 2)
        self.assertNotIn('&MOTION', text)
        self.assertNotIn('&MOMENTS', text)
        stack = []
        for line in text.splitlines():
            words = line.split()
            if words and words[0] == '&END':
                self.assertEqual(stack.pop(), words[1])
            elif words and words[0].startswith('&'):
                stack.append(words[0][1:])
        self.assertEqual(stack, [])
        v = m['vibrational_analysis']
        self.assertEqual(v['displacement_origin'], 'native_default_explicit')
        self.assertEqual(v['eps_scf_origin'], 'task_preset')
        self.assertEqual(v['qs_eps_default'], 1e-14)
        self.assertEqual(m['poisson_solver'], 'MT')
        self.assertEqual(v['poisson_solver_origin'], 'task_preset')
        self.assertIn('POISSON_SOLVER MT\n', text)
        self.assertNotIn('WAVELET', text)
        self.assertFalse(v['mt_box']['density_extent_verified'])
        self.assertEqual(v['mt_box']['cell_lengths_angstrom'], [11.52, 10., 10.58])
        self.assertFalse(any('WAVELET requires' in w for w in m['warnings']))
        self.assertIn('PRINT_LEVEL LOW', text)
        self.assertIn('  &PRINT\n    &PROGRAM_RUN_INFO ON\n      FILENAME __STD_OUT__\n'
                      '    &END PROGRAM_RUN_INFO\n  &END PRINT\n&END VIBRATIONAL_ANALYSIS', text)
        self.assertTrue(v['program_run_info'])
        self.assertEqual(v['program_run_info_origin'], 'task_preset')
        self.assertTrue(any('"Minimum Structure"' in w for w in m['warnings']))
        self.assertFalse(v['runtime_validated'])
        self.assertFalse(v['stationary_point_verified'])
        self.assertEqual(m['source_structure'], self.water.to_dict())
        self.assertEqual(m['source_structure']['source']['sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertIsNone(m['settings']['eps_scf'])
        self.assertIsNone(m['settings']['vibration_displacement_bohr'])
        self.assertTrue(any('stationary point' in w for w in m['warnings']))
        self.assertEqual((text, m), self.generate())
        json.dumps(m, allow_nan=False)

    def test_explicit_numerics_and_charge_are_preserved(self):
        dx = 0.02345678901234567
        text, m = self.generate(vibration_displacement_bohr=dx, eps_scf=2e-9, charge=2, multiplicity=1,
                                cutoff=650., rel_cutoff=80., max_scf=40, max_outer_scf=30)
        self.assertEqual(float(next(line.split()[-1] for line in text.splitlines() if 'DX [' in line)), dx)
        self.assertEqual(m['settings']['charge'], 2)
        self.assertEqual(m['settings']['multiplicity'], 1)
        self.assertEqual(m['vibrational_analysis']['eps_scf_origin'], 'user_explicit')
        self.assertEqual(m['vibrational_analysis']['displacement_origin'], 'user_explicit')
        self.assertEqual(m['effective_eps_scf'], 2e-9)
        self.assertIn('MAX_SCF 40', text)
        self.assertIn('MAX_SCF 30', text)
        self.assertIn('CUTOFF [Ry] 650', text)

    def test_classic_basis_subsets_and_overrides(self):
        for option in OPTIONS:
            if option.protocol == 'classic' and option.selectable:
                with self.subTest(basis=option.id):
                    # UCL SR TZVP/TZV2P deliberately lack H/O fixed-q entries.
                    structure = (Structure(['Be', 'Be'], [[0., 0., 0.], [2., 0., 0.]], None, None,
                                           {'path': 'synthetic-be2.xyz'})
                                 if option.number in (8, 9) else self.water)
                    _, m = generate_input(structure, replace(self.settings, basis=option.id))
                    self.assertEqual(m['basis_selection']['id'], option.id)
        _, m = self.generate(basis_overrides=(('H', 'molopt-tzvp'),))
        self.assertEqual(m['settings']['basis_overrides'], (('H', 'molopt-tzvp'),))

    def test_mt_preserves_explicit_non_cubic_cell_and_positions(self):
        cell = [[12., 0., 0.], [0., 10., 0.], [0., 0., 11.]]
        positions = [[v+5. for v in row] for row in self.water.positions]
        structure = replace(self.water, cell=cell, positions=positions, pbc=[False]*3)
        text, m = generate_input(structure, self.settings)
        self.assertEqual(m['generated_structure']['cell'], cell)
        self.assertEqual(m['generated_structure']['positions'], positions)
        self.assertFalse(m['coordinates_translated'])
        self.assertIn('POISSON_SOLVER MT', text)
        self.assertTrue(any('twice the electronic-density extent' in w for w in m['warnings']))

    def test_mt_rejects_small_skew_or_misplaced_boxes_without_repair(self):
        with self.assertRaisesRegex(KitError, 'twice the displaced atomic span'):
            self.generate(vacuum=.5)
        with self.assertRaisesRegex(KitError, 'place the molecule explicitly'):
            self.generate(cell=(12., 12., 12.))  # Source coordinates straddle the cell face.
        skew = replace(self.water, positions=[[v+5. for v in row] for row in self.water.positions],
                       cell=[[12., 0., 0.], [1., 12., 0.], [0., 0., 12.]])
        with self.assertRaisesRegex(KitError, 'axis-aligned orthorhombic'):
            generate_input(skew, self.settings)
        # A displacement can invalidate an otherwise fitting atomic envelope.
        with self.assertRaisesRegex(KitError, 'twice the displaced atomic span'):
            self.generate(vibration_displacement_bohr=10.)
        with self.assertRaisesRegex(KitError, 'finite'):
            self.generate(vibration_displacement_bohr=1e308)
        self.assertEqual(self.settings.vacuum, 5.)
        self.assertEqual(skew.cell[1][0], 1.)

    def test_rejects_single_atom_but_keeps_linear_molecules(self):
        atom = Structure(['He'], [[0., 0., 0.]], None, [False]*3, {'path': 'synthetic-he.xyz'})
        with self.assertRaisesRegex(KitError, 'at least two atoms'):
            generate_input(atom, self.settings)
        with self.assertRaisesRegex(KitError, 'at least two atoms'):
            write_input(atom, self.settings, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse(Path(str(self.output)+'.json').exists())
        molecule = Structure(['H', 'H'], [[0., 0., 0.], [0.74, 0., 0.]], None,
                             [False]*3, {'path': 'synthetic-h2.xyz'})
        text, m = generate_input(molecule, self.settings)
        self.assertIn('FULLY_PERIODIC F', text)
        self.assertEqual(m['generated_structure']['symbols'], ['H', 'H'])

    def test_displacement_must_be_representable_at_generated_coordinates(self):
        for dx in (1e-300, 5e-324):
            with self.subTest(dx=dx), self.assertRaisesRegex(KitError, 'coordinate precision'):
                self.generate(vibration_displacement_bohr=dx)
        with redirect_stderr(io.StringIO()):
            code = main(['generate-input', str(self.path), '-o', str(self.output),
                         '--periodic', 'NONE', '--run-type', 'VIBRATIONAL_ANALYSIS',
                         '--vibration-displacement-bohr', '1e-300'])
        self.assertEqual(code, 2)
        self.assertFalse(self.output.exists())

    def test_legacy_tasks_keep_poisson_and_text_defaults(self):
        for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT'):
            text, m = self.generate(run_type=task)
            self.assertEqual(m['poisson_solver'], 'WAVELET')
            self.assertIn('POISSON_SOLVER WAVELET', text)
            self.assertIsNone(m['vibrational_analysis'])
            self.assertNotIn('PROGRAM_RUN_INFO', text)
            self.assertIn('EPS_SCF 1.0E-06', text)

    def test_all_other_functionals_rejected(self):
        for functional in FUNCTIONALS:
            if functional != 'PBE':
                with self.subTest(functional=functional), self.assertRaises(KitError):
                    self.generate(functional=functional)

    def test_unsupported_matrix(self):
        cases = [dict(method=m) for m in ('GFN0-xTB', 'GFN1-xTB', 'GFN2-xTB')]
        cases += [dict(cp2k_version=v) for v in ('2024.1', '2024.2', '2024.3', '2025.1', '2025.2', '2026.1')]
        cases += [dict(periodic=p) for p in ('X', 'Y', 'Z', 'XY', 'XZ', 'YZ', 'XYZ')]
        cases += [dict(scf='diag'), dict(ot_algorithm='IRAC'), dict(kpoints=(2, 1, 1)),
                  dict(smearing=300.), dict(added_mos=1), dict(charge=1), dict(multiplicity=3),
                  dict(magnetism=()), dict(magnetism=(('O', 0.),)), dict(dft_plus_u=(('O', 1, 2.),)),
                  dict(dispersion='d3'), dict(dispersion='d3bj'), dict(density_difference=True),
                  dict(admm=True), dict(ri_hfx=True), dict(basis='ae-6-31g-star'), dict(basis='uzh-pbe-dzvp'),
                  dict(basis='custom'), dict(basis_overrides=(('H', 'uzh-pbe-dzvp'),))]
        cases += [{name: True} for name in ('electron_density', 'spin_density', 'hartree_potential', 'mo_cubes')]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(KitError):
                self.generate(**changes)
        # A source cell/PBC is respected rather than silently isolated.
        solid = replace(self.water, cell=[[12., 0., 0.], [0., 12., 0.], [0., 0., 12.]], pbc=[True]*3)
        with self.assertRaises(KitError):
            generate_input(solid, replace(self.settings, periodic=None))
        with self.assertRaisesRegex(KitError, 'Periodicity is unknown'):
            self.generate(periodic=None)

    def test_damaged_numeric_configs(self):
        for field in ('vibration_displacement_bohr', 'eps_scf'):
            for value in (0, -1, float('nan'), float('inf'), -float('inf'), True, False, '0.01', [], {}, 10**1000):
                with self.subTest(field=field, value=repr(value)[:30]), self.assertRaises(KitError):
                    settings = InputSettings.from_config({**asdict(self.settings), field: value})
                    generate_input(self.water, settings)
        with self.assertRaisesRegex(KitError, '<= 1e-8'):
            self.generate(eps_scf=1.00001e-8)
        for value in (0.0001, 0.1):
            self.assertEqual(self.generate(vibration_displacement_bohr=value)[1]['vibrational_analysis']['displacement_bohr'], value)

    def test_retained_settings_not_silently_active(self):
        text, m = self.generate(fixed_atoms='1', optimizer='LBFGS', trust_radius=.3, trajectory_format='PDB')
        self.assertEqual(m['settings']['fixed_atoms'], '1')
        self.assertFalse(m['constraints']['enabled'])
        self.assertFalse(m['motion_output']['enabled'])
        self.assertNotIn('TRUST_RADIUS', text)
        self.assertTrue(any('retained but inactive' in w for w in m['warnings']))
        for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT', 'CELL_OPT'):
            with self.subTest(task=task), self.assertRaisesRegex(KitError, 'requires VIBRATIONAL_ANALYSIS'):
                self.generate(run_type=task, vibration_displacement_bohr=.01)
        with self.assertRaises(KitError):
            self.generate(run_type='ENERGY', method='GFN1-xTB', vibration_displacement_bohr=.01)

    def test_config_sidecar_and_cli_replay(self):
        settings = replace(self.settings, eps_scf=3e-9, vibration_displacement_bohr=.015, write_json=True)
        text, m = generate_input(self.water, settings)
        for config in (asdict(settings), json.loads(json.dumps(m))):
            loaded = InputSettings.from_config(config)
            self.assertEqual(generate_input(self.water, loaded)[0], text)
            self.assertEqual(generate_input(self.water, loaded)[1]['vibrational_analysis'], m['vibrational_analysis'])
        args = command_arguments(self.path, -1, self.output, settings)
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_text(), text)
        self.assertEqual(json.loads(Path(str(self.output)+'.json').read_text())['vibrational_analysis'], m['vibrational_analysis'])
        self.assertIn('stationary point', result.stderr)

    def test_tui_edit_review_and_generation_match_api(self):
        log = TTY()
        code = run_interactive(str(self.path), -1, str(self.output), InputSettings(periodic='NONE', write_json=True),
                               stdin=TTY('-1\nVIBRATIONAL_ANALYSIS\n640\n0.02\n303\n2e-9\nr\n\n0\n'),
                               stdout=log, plain=True)
        self.assertEqual(code, 0, log.getvalue())
        settings = replace(self.settings, vibration_displacement_bohr=.02, eps_scf=2e-9, write_json=True)
        self.assertEqual(self.output.read_text(), generate_input(self.water, settings)[0])
        self.assertIn('0.02 bohr [user_explicit]', log.getvalue())
        self.assertIn('QS EPS_DEFAULT: 1e-14 [task_preset]', ' '.join(log.getvalue().split()))
        self.assertIn('stationary point NOT verified', log.getvalue())
        self.assertIn('Poisson: MT [task_preset]', ' '.join(log.getvalue().split()))
        self.assertIn('PROGRAM_RUN_INFO: ON [task_preset]', ' '.join(log.getvalue().split()))

    def test_explicit_frame_is_geometry_not_convergence_evidence(self):
        first = self.path.read_text()
        trajectory = self.root/'final-optimized.xyz'
        trajectory.write_text(first + first.replace('H .76', 'H .80'))
        selected = read_structure(trajectory, frame=0)
        _, m = generate_input(selected, self.settings)
        self.assertEqual(m['source_structure']['frame'], 0)
        self.assertEqual(m['source_structure'], selected.to_dict())
        self.assertFalse(m['vibrational_analysis']['stationary_point_verified'])
        self.assertNotEqual(selected.positions, read_structure(trajectory, frame=1).positions)

    def test_tui_hidden_displacement_requires_explicit_reset(self):
        log = TTY()
        settings = replace(self.settings, vibration_displacement_bohr=.02)
        code = run_interactive(str(self.path), -1, str(self.output), settings,
                               stdin=TTY('-1\nENERGY\n0\n\n-1\nVIBRATIONAL_ANALYSIS\n640\nauto\n0\n'),
                               stdout=log, plain=True)
        self.assertEqual(code, 0, log.getvalue())
        self.assertIn('reset it to auto/None', log.getvalue())
        self.assertEqual(self.output.read_text(), self.generate()[0])

    def test_cli_invalid_does_not_publish(self):
        for args in (['--scf', 'diag'], ['--eps-scf', 'nan'], ['--vibration-displacement-bohr', '0']):
            with self.subTest(args=args), redirect_stderr(io.StringIO()):
                code = main(['generate-input', str(self.path), '-o', str(self.output), '--periodic', 'NONE',
                             '--run-type', 'VIBRATIONAL_ANALYSIS', *args])
                self.assertEqual(code, 2)
                self.assertFalse(self.output.exists())

    def test_source_data_collision_and_rollback(self):
        settings = replace(self.settings, write_json=True)
        self.output.write_text('existing input')
        sidecar = Path(str(self.output)+'.json')
        sidecar.write_text('existing metadata')
        with self.assertRaises(OutputExists):
            write_input(self.water, settings, self.output)
        self.assertEqual(self.output.read_text(), 'existing input')
        sidecar.unlink()  # Test-owned synthetic metadata only.
        with patch('cp2kkit.inputgen.os.replace', side_effect=OSError('synthetic publication failure')):
            with self.assertRaises(OSError):
                write_input(self.water, settings, self.output)
        self.assertFalse(sidecar.exists())
        self.assertEqual(self.output.read_text(), 'existing input')
        self.assertEqual(list(self.root.glob('.*.tmp')), [])
        with self.assertRaises(KitError):
            write_input(self.water, settings, self.path)
        data = self.root/'data'
        data.mkdir()
        basis = data/'BASIS_MOLOPT'
        potential = data/'GTH_POTENTIALS'
        basis.write_text(basis_entry('H', 'DZVP-MOLOPT-SR-GTH-q1') + basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6'))
        potential.write_text(potential_entry('H', 1, 'GTH-PBE-q1') + potential_entry('O', 6, 'GTH-PBE-q6'))
        checked = replace(settings, data_dir=str(data))
        _, m = generate_input(self.water, checked)
        self.assertEqual(m['basis_validation']['status'], 'data_checked')
        for path in (basis, potential):
            original = path.read_bytes()
            alias = self.root/(path.name+'.inp')
            os.link(path, alias)
            with self.assertRaises(KitError):
                write_input(self.water, checked, alias)
            self.assertEqual(path.read_bytes(), original)
        symlink = self.root/'link.inp'
        symlink.symlink_to(self.output)
        with self.assertRaises(OutputExists):
            write_input(self.water, settings, symlink)
        self.assertEqual(self.output.read_text(), 'existing input')
