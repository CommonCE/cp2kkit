"""Synthetic print-contract tests; no CP2K execution or scientific certification."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from cp2kkit.cli import build_parser
from cp2kkit.cube import check_cube
from cp2kkit.cube_profile import planar_profile
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.input_editor import edit_cube_output
from cp2kkit.input_tui import Menu, command_arguments, run_interactive, visible_fields, GROUPS
from cp2kkit.inputgen import CP2K_VERSIONS, InputSettings, generate_input, write_input
from cp2kkit.structure import read_structure
from tests.test_input_tui import TTY
from tests.test_cube import synthetic_cube


class CubeOutputTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root/'water.xyz'
        self.path.write_text('3\nsynthetic\nO 0 0 0\nH 1 0 0\nH 0 1 0\n')
        self.water = read_structure(self.path)
        self.settings = InputSettings(periodic='NONE', hartree_potential=True, mo_cubes=True,
                                      write_json=True)

    def test_combined_placement_cadence_and_shared_stride_all_tasks(self):
        for task in ('ENERGY', 'ENERGY_FORCE', 'GEO_OPT', 'CELL_OPT'):
            with self.subTest(task=task):
                text, report = generate_input(self.water, replace(self.settings, run_type=task,
                                              periodic='XYZ', cell=(12., 12., 12.),
                                              electron_density=True, cube_stride=(1, 2, 3)))
                stack, found = [], []
                for line in text.splitlines():
                    tokens = line.split()
                    if not tokens or tokens[0].startswith('#'):
                        continue
                    if tokens[0] == '&END':
                        self.assertEqual(stack.pop(), tokens[1])
                    elif tokens[0].startswith('&'):
                        if tokens[0] in ('&E_DENSITY_CUBE', '&V_HARTREE_CUBE', '&MO_CUBES'):
                            self.assertEqual(stack, ['FORCE_EVAL', 'DFT', 'PRINT'])
                            self.assertEqual(tokens[1], 'ON')
                            found.append(tokens[0])
                        stack.append(tokens[0][1:])
                self.assertEqual(len(found), 3)
                self.assertEqual(stack, [])
                for token in ('STRIDE 1 2 3', 'APPEND F', 'ADD_LAST NUMERIC', 'QS_SCF 0',
                              'JUST_ENERGY 1', 'GEO_OPT 0', 'CELL_OPT 0'):
                    self.assertEqual(text.count(token), 3)
                self.assertIn('WRITE_CUBE T', text)
                self.assertIn('NHOMO 1', text)
                self.assertIn('NLUMO 1', text)
                self.assertEqual(report['density_output']['stride'], [1, 2, 3])
                for output in report['extra_cube_output'].values():
                    self.assertEqual(output['stride'], [1, 2, 3])
                    self.assertFalse(output['runtime_validated'])
                    for source in output['sources'].values():
                        self.assertIn('/v2026.2/', source['url'])
                        self.assertEqual(len(source['sha256']), 64)
                self.assertEqual(report['input_sha256'], hashlib.sha256(text.encode()).hexdigest())

    def test_defaults_and_independent_outputs(self):
        default = InputSettings(periodic='NONE')
        text, report = generate_input(self.water, default)
        self.assertNotIn('&V_HARTREE_CUBE', text)
        self.assertNotIn('&MO_CUBES', text)
        for output in report['extra_cube_output'].values():
            self.assertFalse(output['enabled'])
            self.assertIsNone(output['stride'])
            self.assertIsNone(output['each'])
        for key, flag, section in [('potential', 'hartree_potential', 'V_HARTREE_CUBE'),
                                   ('orbitals', 'mo_cubes', 'MO_CUBES')]:
            with self.subTest(flag=flag):
                text, report = generate_input(self.water, replace(default, **{flag: True}, cube_stride=(2, 3, 4)))
                self.assertIn('&'+section+' ON', text)
                self.assertFalse(report['density_output']['enabled'])
                self.assertTrue(report['extra_cube_output'][key]['enabled'])
                self.assertEqual(report['extra_cube_output'][key]['stride'], [2, 3, 4])

    def test_sign_units_and_spin_metadata(self):
        _, report = generate_input(self.water, replace(self.settings, charge=1, multiplicity=2))
        extra = report['extra_cube_output']
        self.assertEqual(extra['potential']['physical_esp_sign_factor'], -1)
        self.assertFalse(extra['potential']['sign_conversion_applied'])
        self.assertEqual(extra['potential']['spatial_unit'], 'bohr')
        self.assertEqual(extra['orbitals']['scalar_unit'], 'bohr^(-3/2)')
        self.assertEqual(extra['orbitals']['spin_channels'], ['alpha', 'beta'])
        self.assertEqual(extra['orbitals']['virtual_state_source'], 'post-SCF OT eigensolver')
        self.assertFalse(extra['orbitals']['virtual_convergence_verified'])
        self.assertTrue(any('opposite sign' in w for w in report['warnings']))
        self.assertTrue(any('not electron density' in w for w in report['warnings']))
        _, report = generate_input(self.water, replace(self.settings, magnetism=()))
        self.assertEqual(report['extra_cube_output']['orbitals']['spin_channels'], ['alpha', 'beta'])

    def test_explicit_diagonalization_virtual_orbitals_without_silent_changes(self):
        with self.assertRaisesRegex(KitError, 'added_mos >= mo_nlumo'):
            generate_input(self.water, replace(self.settings, scf='diag'))
        settings = replace(self.settings, scf='diag', added_mos=2, mo_nlumo=2)
        text, report = generate_input(self.water, settings)
        self.assertIn('ADDED_MOS 2', text)
        self.assertIn('NLUMO 2', text)
        self.assertEqual(report['settings']['added_mos'], 2)
        self.assertEqual(report['extra_cube_output']['orbitals']['virtual_state_source'], 'SCF added orbitals')
        self.assertEqual(settings.added_mos, 2)
        _, report = generate_input(self.water, self.settings)
        self.assertEqual(report['settings']['scf'], 'ot')
        self.assertEqual(report['settings']['added_mos'], 0)

    def test_occupied_only_and_virtual_only(self):
        for homo, lumo in ((2, 0), (0, 2)):
            with self.subTest(homo=homo, lumo=lumo):
                text, report = generate_input(self.water, replace(self.settings, mo_nhomo=homo, mo_nlumo=lumo))
                self.assertIn(f'NHOMO {homo}', text)
                self.assertIn(f'NLUMO {lumo}', text)
                if not lumo:
                    self.assertIsNone(report['extra_cube_output']['orbitals']['virtual_state_source'])

    def test_invalid_controls_retained_requests_and_occupations(self):
        changes = [dict(hartree_potential=1), dict(mo_cubes='yes'), dict(mo_nhomo=True),
                   dict(mo_nlumo=1.0), dict(mo_nhomo=None), dict(mo_nlumo=-1),
                   dict(mo_nhomo=0, mo_nlumo=0), dict(mo_cubes=False, mo_nhomo=2),
                   dict(mo_nhomo=5), dict(scf='diag', smearing=300, added_mos=5),
                   dict(charge=1, multiplicity=2, mo_nhomo=4),
                   dict(cube_stride=(0, 1, 1)), dict(cube_stride=(True, 1, 1))]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(KitError):
                generate_input(self.water, replace(self.settings, **change))
        atom = replace(self.water, symbols=['H'], positions=[[0., 0., 0.]])
        with self.assertRaisesRegex(KitError, 'channel is empty'):
            generate_input(atom, self.settings)

    def test_scope_versions_gapw_kpoints_and_xtb(self):
        for version in CP2K_VERSIONS[:-1]:
            with self.subTest(version=version), self.assertRaisesRegex(KitError, '2026.2'):
                generate_input(self.water, replace(self.settings, cp2k_version=version))
        for change in (dict(basis='ae-6-31g-star'),
                       dict(kpoints=(2, 2, 2), periodic='XYZ', scf='diag', added_mos=1),
                       dict(method='GFN1-xTB')):
            with self.subTest(change=change), self.assertRaises(KitError):
                generate_input(self.water, replace(self.settings, **change))

    def test_potential_only_retains_smearing_policy(self):
        settings = replace(self.settings, mo_cubes=False, scf='diag', smearing=300)
        _, report = generate_input(self.water, settings)
        self.assertEqual(report['settings']['smearing'], 300)
        self.assertEqual(report['settings']['added_mos'], 30)
        self.assertTrue(report['extra_cube_output']['potential']['enabled'])
        self.assertFalse(report['extra_cube_output']['orbitals']['enabled'])

    def test_analysis_does_not_mislabel_potential_or_orbital_as_density(self):
        for title in ('HARTREE POTENTIAL', 'WAVEFUNCTION 4 spin 1 i.e. HOMO - 0'):
            with self.subTest(title=title):
                path = self.root/'non-density.cube'
                path.write_text(synthetic_cube([1, -1, 2, -2], comments=('-Quickstep-', title)))
                report = check_cube(path)
                self.assertEqual(report['scalar_type'], 'unknown')
                self.assertEqual(report['scalar_unit'], 'unknown')
                self.assertEqual(report['statistics']['integral']['quantity'], 'raw_numerical_integral')
                with self.assertRaises(KitError):
                    planar_profile(path)

    def test_config_replay_and_determinism(self):
        settings = replace(self.settings, mo_nhomo=2, mo_nlumo=3, cube_stride=(1, 2, 3))
        first = generate_input(self.water, settings)
        self.assertEqual(first, generate_input(self.water, settings))
        loaded = InputSettings.from_config(json.loads(json.dumps(first[1])))
        self.assertEqual(first, generate_input(self.water, loaded))
        argv = command_arguments(self.path, -1, self.root/'out.inp', settings)
        args = build_parser().parse_args(argv[3:])
        for name in ('hartree_potential', 'mo_cubes', 'mo_nhomo', 'mo_nlumo'):
            self.assertEqual(getattr(args, name), getattr(settings, name))
        old = InputSettings.from_config({'periodic': 'NONE'})
        self.assertFalse(old.mo_cubes)
        self.assertFalse(old.hartree_potential)

    def test_cli_subprocess_and_collision(self):
        output = self.root/'out.inp'
        argv = command_arguments(self.path, -1, output, self.settings)
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(Path(str(output)+'.json').read_text())
        self.assertTrue(report['extra_cube_output']['potential']['enabled'])
        self.assertTrue(report['extra_cube_output']['orbitals']['enabled'])
        before = output.read_bytes()
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 5, proc.stderr)
        self.assertEqual(output.read_bytes(), before)
        invalid = self.root/'invalid.inp'
        proc = subprocess.run(command_arguments(self.path, -1, invalid,
                                                replace(self.settings, mo_nhomo=-1)),
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertFalse(invalid.exists())
        self.assertFalse(Path(str(invalid)+'.json').exists())

    def test_invalid_request_preserves_existing_input_and_sidecar_collision(self):
        output = self.root/'protected.inp'
        output.write_text('existing input\n')
        with self.assertRaises(KitError):
            write_input(self.water, replace(self.settings, mo_nhomo=-1), output)
        self.assertEqual(output.read_text(), 'existing input\n')
        sidecar = Path(str(output)+'.json')
        sidecar.symlink_to(self.root/'absent')
        with self.assertRaises(OutputExists):
            write_input(self.water, self.settings, output)
        self.assertEqual(output.read_text(), 'existing input\n')
        self.assertTrue(sidecar.is_symlink())
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_selector_combination_none_and_cdd_guard(self):
        values = asdict(InputSettings())
        for choice, field in [('2', 'hartree_potential'), ('3', 'mo_cubes'), ('1', 'electron_density')]:
            edit_cube_output(Menu(TTY(choice+'\n'), TTY(), True), values)
            self.assertTrue(values[field])
        self.assertTrue(all(values[name] for name in ('electron_density', 'hartree_potential', 'mo_cubes')))
        values.update(mo_nhomo=3, cube_stride=(2, 2, 2))
        edit_cube_output(Menu(TTY('0\n'), TTY(), True), values)
        self.assertFalse(any(values[name] for name in ('electron_density', 'spin_density', 'hartree_potential', 'mo_cubes')))
        self.assertEqual((values['mo_nhomo'], values['mo_nlumo']), (1, 1))
        self.assertIsNone(values['cube_stride'])
        values.update(density_difference=True, electron_density=True, hartree_potential=True)
        before = values.copy()
        edit_cube_output(Menu(TTY('0\nback\n'), TTY(), True), values)
        self.assertEqual(values, before)

    def test_tui_direct_fields_match_cli_and_review(self):
        output = self.root/'menu.inp'
        stream = TTY()
        code = run_interactive(str(self.path), -1, str(output),
                               InputSettings(periodic='NONE', write_json=True),
                               stdin=TTY('610\ny\n607\ny\n608\n2\n609\n3\n605\n2 3 4\nw\ny\n'),
                               stdout=stream, plain=True)
        self.assertEqual(code, 0, stream.getvalue())
        expected = replace(self.settings, mo_nhomo=2, mo_nlumo=3, cube_stride=(2, 3, 4))
        self.assertEqual(output.read_text(), generate_input(self.water, expected)[0])
        self.assertIn('Native potential CUBE: True', stream.getvalue())
        self.assertIn('NHOMO=2, NLUMO=3', stream.getvalue())

    def test_xtb_hides_but_does_not_clear_controls(self):
        values = asdict(replace(self.settings, method='GFN1-xTB'))
        fields = [field for _, fields in GROUPS for field in fields]
        visible = {f.name for f in visible_fields(fields, values)}
        self.assertTrue(visible.isdisjoint({'hartree_potential', 'mo_cubes', 'mo_nhomo', 'mo_nlumo'}))
        self.assertTrue(values['hartree_potential'])
        with self.assertRaises(KitError):
            generate_input(self.water, InputSettings(**values))

    def test_density_bundle_inherits_outputs_without_changing_geometry(self):
        settings = replace(self.settings, density_difference=True, fragment_a_indices='1',
                           fragment_a_charge=0, fragment_a_multiplicity=1,
                           fragment_b_charge=0, fragment_b_multiplicity=1)
        _, report = generate_input(self.water, settings)
        components = report['density_difference']['components']
        for component in components.values():
            self.assertTrue(component['density_output']['enabled'])
            self.assertTrue(component['extra_cube_output']['potential']['enabled'])
            self.assertTrue(component['extra_cube_output']['orbitals']['enabled'])
            self.assertEqual(component['generated_structure']['cell'], report['generated_structure']['cell'])
        # Whole and O fragment have >=2 occupied orbitals; H2 fragment has only 1.
        # Reject the entire bundle before publishing any inputs/map/sidecar.
        output = self.root/'invalid-bundle.inp'
        with self.assertRaisesRegex(KitError, 'mo_nhomo exceeds'):
            write_input(self.water, replace(settings, mo_nhomo=2), output)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['water.xyz'])


if __name__ == '__main__':
    unittest.main()
