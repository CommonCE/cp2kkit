"""Synthetic bundle invariants and publication failures; never executes CP2K."""
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import build_parser, main
from cp2kkit.density_workflow import bundle_paths, partition
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.input_tui import command_arguments, run_interactive
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.structure import Structure, read_structure
from tests.synthetic_cp2k_data import basis_entry, potential_entry
from tests.test_input_tui import TTY
from tests.test_structure_formats import CIF


class DensityWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root/'water.xyz'
        self.source.write_text('3\nsynthetic\nO 0 0 0\nH 1 0 0\nH 0 1 0\n')
        self.structure = read_structure(self.source)
        self.output = self.root/'bundle.inp'
        self.settings = InputSettings(periodic='NONE', density_difference=True,
                                      fragment_a_indices='1', fragment_a_charge=0,
                                      fragment_a_multiplicity=3, fragment_b_charge=0,
                                      fragment_b_multiplicity=1)
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def generate(self, structure=None, **changes):
        return generate_input(self.structure if structure is None else structure, replace(self.settings, **changes))

    def test_partition_validates_before_expansion_and_preserves_order(self):
        self.assertEqual(partition('3,1', 4), ('1,3', (1, 3), (2, 4)))
        for selection in ('off', '1-3', '2,2', '0,1', '-1', '1;2', '3-2', '1\n2', '1-999999999999999999999999'):
            with self.subTest(selection=selection), self.assertRaises(KitError):
                partition(selection, 3)

    def test_isolated_box_built_once_and_fragments_are_not_recentered(self):
        before = self.structure.to_dict()
        text, manifest = self.generate()
        workflow = manifest['density_difference']
        components = workflow['components']
        whole = components['whole']['generated_structure']
        self.assertEqual(text, components['whole']['input_text'])
        self.assertEqual(whole['positions'], [[5., 5., 5.], [6., 5., 5.], [5., 6., 5.]])
        for name, indices in (('fragment_a', [1]), ('fragment_b', [2, 3])):
            geometry = components[name]['generated_structure']
            self.assertEqual(geometry['cell'], whole['cell'])
            self.assertEqual(geometry['pbc'], whole['pbc'])
            self.assertEqual(geometry['positions'], [whole['positions'][i-1] for i in indices])
            self.assertFalse(components[name]['coordinates_translated'])
            self.assertEqual(components[name]['source_structure']['source']['whole_atom_indices'], indices)
        self.assertEqual(self.structure.to_dict(), before)
        self.assertFalse(workflow['cube_grid_match_verified'])
        self.assertFalse(workflow['runtime_validated'])
        self.assertFalse(workflow['ghost_basis'])

    def test_noncontiguous_fragments_and_mapping_use_generated_coordinates(self):
        _, manifest = self.generate(fragment_a_indices='3,1', fragment_a_multiplicity=2, fragment_b_multiplicity=2)
        workflow = manifest['density_difference']
        self.assertEqual(workflow['fragment_a_indices'], [1, 3])
        self.assertEqual(workflow['fragment_b_indices'], [2])
        self.assertEqual([(r['whole_index'], r['fragment'], r['fragment_index']) for r in workflow['atom_mapping']],
                         [(1, 'A', 1), (2, 'B', 1), (3, 'A', 2)])
        self.assertEqual(workflow['atom_mapping'][1]['position_angstrom'], [6., 5., 5.])

    def test_triclinic_source_and_explicit_cell_preserve_common_geometry(self):
        cell = [[8., 0., 0.], [2., 9., 0.], [1., 3., 10.]]
        structure = replace(self.structure, cell=cell, pbc=[True]*3)
        for override in (None, (12., 13., 14.)):
            _, manifest = self.generate(structure, periodic=None, cell=override)
            expected = cell if override is None else [[12., 0., 0.], [0., 13., 0.], [0., 0., 14.]]
            for component in manifest['density_difference']['components'].values():
                self.assertEqual(component['generated_structure']['cell'], expected)
                self.assertFalse(component['coordinates_translated'])

    def test_explicit_fragment_charge_and_spin_are_required(self):
        for name in ('fragment_a_charge', 'fragment_a_multiplicity', 'fragment_b_charge', 'fragment_b_multiplicity'):
            for value in (None, True, 1.5, '1'):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(KitError, name):
                    self.generate(**{name: value})
        with self.assertRaisesRegex(KitError, 'charge must equal'):
            self.generate(fragment_a_charge=1)
        with self.assertRaisesRegex(KitError, 'Charge/multiplicity'):
            self.generate(fragment_a_multiplicity=2)
        with self.assertRaisesRegex(KitError, 'Charge/multiplicity'):
            self.generate(fragment_a_charge=1, fragment_b_charge=-1)
        with self.assertRaisesRegex(KitError, 'Charge/multiplicity'):
            self.generate(fragment_a_charge=6, fragment_b_charge=-6)

    def test_fragment_spins_need_not_add_to_the_whole_spin(self):
        _, manifest = self.generate(fragment_a_indices='1,3', fragment_a_multiplicity=2, fragment_b_multiplicity=2)
        components = manifest['density_difference']['components']
        self.assertEqual(components['whole']['settings']['multiplicity'], 1)
        self.assertEqual(components['fragment_a']['settings']['multiplicity'], 2)
        self.assertEqual(components['fragment_b']['settings']['multiplicity'], 2)
        self.assertEqual([components[key]['explicit_electron_count'] for key in ('whole', 'fragment_a', 'fragment_b')], [8, 7, 1])

    def test_charged_fragments_are_explicit_and_warn_without_repair(self):
        _, manifest = self.generate(fragment_a_charge=1, fragment_b_charge=-1,
                                    fragment_a_multiplicity=2, fragment_b_multiplicity=2)
        self.assertEqual(manifest['settings']['charge'], 0)
        self.assertEqual(manifest['density_difference']['components']['fragment_a']['settings']['charge'], 1)
        self.assertTrue(any('Charged fragments' in warning for warning in manifest['warnings']))

    def test_unsupported_tasks_models_and_bad_flags_write_nothing(self):
        for changes in ({'run_type': 'GEO_OPT'}, {'run_type': 'ENERGY_FORCE'}, {'basis': 'ae-def2-tzvp'},
                        {'density_difference': 1}, {'density_difference': 'on'}):
            with self.subTest(changes=changes), self.assertRaises(KitError):
                write_input(self.structure, replace(self.settings, **changes), self.output)
            self.assertFalse(self.output.exists())
        with self.assertRaisesRegex(KitError, 'Periodicity is unknown'):
            self.generate(periodic=None)

    def test_workflow_disabled_retains_requests_without_emitting_bundle(self):
        text, manifest = self.generate(density_difference=False, fragment_a_indices='off', fragment_a_charge=None)
        self.assertNotIn('density_difference', {k: v for k, v in manifest.items() if k != 'settings'})
        self.assertNotIn('&E_DENSITY_CUBE', text)
        self.assertIsNone(manifest['settings']['fragment_a_charge'])
        self.assertEqual(len(bundle_paths(replace(self.settings, density_difference=False), self.output)), 1)
        old = InputSettings.from_config({'periodic': 'NONE'})
        self.assertFalse(old.density_difference)
        self.assertIsNone(old.fragment_a_charge)

    def test_effective_grids_stride_scf_and_projects_are_shared(self):
        _, manifest = self.generate(basis_overrides=(('O', 'molopt-tzvp'),), cube_stride=(2, 3, 4),
                                    cutoff=550., rel_cutoff=70., eps_scf=2e-7, ot_algorithm='IRAC')
        components = manifest['density_difference']['components']
        for component in components.values():
            self.assertIn('NGRIDS 5', component['input_text'])
            self.assertEqual(component['method_profile']['ngrids'], 5)
            self.assertEqual(component['density_output']['stride'], [2, 3, 4])
            self.assertEqual(component['effective_eps_scf'], 2e-7)
            self.assertEqual(component['settings']['cutoff'], 550.)
            self.assertEqual(component['settings']['rel_cutoff'], 70.)
            self.assertIn('ALGORITHM IRAC', component['input_text'])
            self.assertFalse(component['constraints']['enabled'])
        self.assertEqual(components['fragment_b']['method_profile']['ngrids_selection'], 'whole-system workflow lock')
        self.assertEqual(len({c['settings']['project'] for c in components.values()}), 3)
        self.assertEqual(components['fragment_b']['settings']['basis_overrides'], ())
        _, omitted = self.generate()
        for component in omitted['density_difference']['components'].values():
            self.assertNotIn('NGRIDS', component['input_text'])
            self.assertIsNone(component['method_profile']['ngrids'])

    def test_global_basis_completely_overridden_does_not_create_false_grid_lock(self):
        _, manifest = self.generate(basis='molopt-tzvp', basis_overrides=(('H', 'molopt-sr-dzvp'), ('O', 'molopt-sr-dzvp')))
        for component in manifest['density_difference']['components'].values():
            self.assertNotIn('NGRIDS', component['input_text'])

    def test_diagonalization_and_automatic_empty_orbitals_resolve_once(self):
        structure = replace(self.structure, pbc=[True]*3, cell=[[10., 0., 0.], [0., 10., 0.], [0., 0., 10.]])
        _, manifest = self.generate(structure, periodic='XYZ', scf='diag', kpoints=(2, 2, 2), smearing=300.)
        for component in manifest['density_difference']['components'].values():
            self.assertEqual(component['settings']['added_mos'], 30)
            self.assertIn('MONKHORST-PACK 2 2 2', component['input_text'])
            self.assertNotIn('&OT', component['input_text'])

    def test_explicit_magnetic_seed_mapping_and_hubbard_filtering(self):
        structure = Structure(['Fe', 'Fe', 'O', 'O'], [[0., 0., 0.], [2., 0., 0.], [0., 2., 0.], [2., 2., 0.]],
                              None, [False]*3, self.structure.source)
        _, manifest = self.generate(structure, fragment_a_indices='2', fragment_a_multiplicity=1,
                                    magnetism=(('Fe', 4.), ('@2', -4.), ('@4', 0.)), dft_plus_u=(('Fe', 2, 4.), ('O', 1, 2.)))
        components = manifest['density_difference']['components']
        self.assertEqual(dict(components['fragment_a']['settings']['magnetism']), {'Fe': 4., '@1': -4.})
        self.assertEqual(dict(components['fragment_b']['settings']['magnetism']), {'Fe': 4., '@3': 0.})
        self.assertEqual(components['fragment_a']['settings']['dft_plus_u'], (('Fe', 2, 4.),))
        self.assertIn('MAGNETIZATION -4', components['fragment_a']['input_text'])
        self.assertIn('WHOLE', manifest['density_difference']['magnetic_seed_policy'].upper())
        for component in components.values():
            self.assertEqual(component['settings']['multiplicity'], 1)

    def test_actual_selected_data_and_hashes_are_checked_for_each_component(self):
        basis, potential = self.root/'basis', self.root/'potential'
        basis.write_text(basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6')+basis_entry('H', 'DZVP-MOLOPT-SR-GTH-q1'))
        potential.write_text(potential_entry('O', 6, 'GTH-PBE-q6')+potential_entry('H', 1, 'GTH-PBE-q1'))
        _, manifest = self.generate(basis_files=(str(basis),), potential_files=(str(potential),))
        for component in manifest['density_difference']['components'].values():
            self.assertEqual(component['basis_validation']['status'], 'data_checked')
            for kind in component['kinds'].values():
                self.assertEqual(kind['basis_source']['sha256'], hashlib.sha256(basis.read_bytes()).hexdigest())
                self.assertEqual(kind['potential_source']['sha256'], hashlib.sha256(potential.read_bytes()).hexdigest())

    def test_changed_library_between_components_is_rejected_before_publication(self):
        original = generate_input
        calls = 0
        def altered(structure, settings, **kwargs):
            nonlocal calls
            text, report = original(structure, settings, **kwargs)
            calls += 1
            if calls == 2:
                next(iter(report['kinds'].values()))['basis_file'] = 'changed-source'
            return text, report
        with patch('cp2kkit.inputgen.generate_input', side_effect=altered), self.assertRaisesRegex(KitError, 'changes O basis_file'):
            write_input(self.structure, self.settings, self.output)
        self.assertEqual(set(self.root.iterdir()), {self.source})

    def test_data_mutation_between_components_is_detected_by_actual_hash(self):
        basis, potential = self.root/'basis', self.root/'potential'
        basis.write_text(basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6')+basis_entry('H', 'DZVP-MOLOPT-SR-GTH-q1'))
        potential.write_text(potential_entry('O', 6, 'GTH-PBE-q6')+potential_entry('H', 1, 'GTH-PBE-q1'))
        settings = replace(self.settings, basis_files=(str(basis),), potential_files=(str(potential),))
        original = generate_input
        calls = 0
        def mutate(structure, requested, **kwargs):
            nonlocal calls
            text, report = original(structure, requested, **kwargs)
            calls += 1
            if calls == 1:
                basis.write_text(basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6', exponent=1.5)+
                                 basis_entry('H', 'DZVP-MOLOPT-SR-GTH-q1'))
            return text, report
        with patch('cp2kkit.inputgen.generate_input', side_effect=mutate), self.assertRaisesRegex(KitError, 'changes O basis_source'):
            write_input(self.structure, settings, self.output)
        self.assertEqual(set(self.root.iterdir()), {self.source, basis, potential})

    def test_selected_frame_and_expanded_cif_atom_order(self):
        self.source.write_text(self.source.read_text()+'1\nsecond frame\nHe 0 0 0\n')
        self.generate(read_structure(self.source, 0))
        with self.assertRaisesRegex(KitError, 'both contain atoms'):
            self.generate(read_structure(self.source, 1))
        cif = self.root/'expanded.cif'
        cif.write_text(CIF.replace('_space_group_IT_number 1', "loop_\n_space_group_symop_operation_xyz\n'x,y,z'\n'-x,-y,-z'"))
        structure = read_structure(cif)
        _, report = self.generate(structure, periodic=None, fragment_a_multiplicity=3, fragment_b_multiplicity=3)
        self.assertEqual(report['density_difference']['fragment_b_indices'], [2])
        self.assertEqual(report['density_difference']['atom_mapping'][1]['element'], 'O')

    def test_config_replay_and_generation_are_deterministic(self):
        text, manifest = self.generate()
        self.assertEqual((text, manifest), self.generate())
        restored = InputSettings.from_config(json.loads(json.dumps(manifest)))
        self.assertEqual(json.loads(json.dumps(generate_input(self.structure, restored)[1])), json.loads(json.dumps(manifest)))
        argv = command_arguments(self.source, -1, self.output, self.settings)
        args = build_parser().parse_args(argv[3:])
        replay = InputSettings.from_config({name: getattr(args, name) for name in InputSettings.__dataclass_fields__})
        self.assertEqual(generate_input(self.structure, replay), (text, manifest))

    def test_write_bundle_csv_optional_json_and_unique_paths(self):
        for write_json in (False, True):
            settings = replace(self.settings, write_json=write_json)
            output = self.root/('json.inp' if write_json else 'plain.inp')
            path, sidecar, warnings = write_input(self.structure, settings, output)
            paths = bundle_paths(settings, path)
            self.assertEqual(len(paths), 5 if write_json else 4)
            self.assertTrue(all(p.is_file() for p in paths))
            self.assertEqual(paths[0].read_text(), self.generate()[0])
            self.assertEqual(sidecar, Path(str(output)+'.json') if write_json else None)
            with paths[3].open(newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([(r['whole_index'], r['fragment'], r['fragment_index']) for r in rows], [('1', 'A', '1'), ('2', 'B', '1'), ('3', 'B', '2')])
            self.assertEqual(rows[1]['x_angstrom'], '6.00000000')
            self.assertTrue(warnings)
            if write_json:
                manifest = json.loads(sidecar.read_text())
                self.assertEqual(manifest['density_difference']['output_paths'], [str(p.resolve()) for p in paths])
                for target, key in zip(paths[:3], ('whole', 'fragment_a', 'fragment_b')):
                    component = manifest['density_difference']['components'][key]
                    self.assertEqual(component['input_text'], target.read_text())
                    self.assertEqual(component['input_sha256'], hashlib.sha256(target.read_bytes()).hexdigest())
        with self.assertRaisesRegex(KitError, '.inp output'):
            write_input(self.structure, self.settings, self.root/'invalid.out')

    def test_each_collision_is_exclusive_and_leaves_all_existing_bytes(self):
        settings = replace(self.settings, write_json=True)
        paths = bundle_paths(settings, self.output)
        for target in paths:
            with self.subTest(target=target):
                target.write_text('expensive existing data')
                with self.assertRaises(OutputExists):
                    write_input(self.structure, settings, self.output)
                self.assertEqual(target.read_text(), 'expensive existing data')
                self.assertEqual(set(self.root.iterdir()), {self.source, target})
                target.unlink()  # Only this test's synthetic output.

    def test_json_disabled_preserves_existing_sidecar_and_warns(self):
        sidecar = Path(str(self.output)+'.json')
        sidecar.write_text('old provenance')
        _, saved, warnings = write_input(self.structure, self.settings, self.output)
        self.assertIsNone(saved)
        self.assertEqual(sidecar.read_text(), 'old provenance')
        self.assertTrue(any('may describe an earlier input' in w for w in warnings))
        self.assertTrue(all(p.exists() for p in bundle_paths(self.settings, self.output)))

    def test_symlink_hardlink_directory_and_source_collisions_are_protected(self):
        target = bundle_paths(self.settings, self.output)[1]
        for mode in ('dangling', 'hardlink', 'directory'):
            with self.subTest(mode=mode):
                if mode == 'dangling':
                    target.symlink_to(self.root/'absent')
                elif mode == 'hardlink':
                    os.link(self.source, target)
                else:
                    target.mkdir()
                with self.assertRaises(KitError):
                    write_input(self.structure, self.settings, self.output)
                self.assertFalse(self.output.exists())
                target.rmdir() if mode == 'directory' else target.unlink()
        protected = self.root/'source.inp'
        protected.write_text('source bytes')
        with self.assertRaisesRegex(KitError, 'source/data'):
            write_input(replace(self.structure, source={'path': str(protected)}), self.settings, protected)
        self.assertEqual(protected.read_text(), 'source bytes')

    def test_late_publication_collision_rolls_back_only_own_files(self):
        paths = bundle_paths(self.settings, self.output)
        original = os.link
        def race(src, dst, *args, **kwargs):
            if Path(dst) == paths[2]:
                paths[2].write_text('concurrent result')
            return original(src, dst, *args, **kwargs)
        with patch('cp2kkit.io.os.link', side_effect=race), self.assertRaises(OutputExists):
            write_input(self.structure, self.settings, self.output)
        self.assertEqual(set(self.root.iterdir()), {self.source, paths[2]})
        self.assertEqual(paths[2].read_text(), 'concurrent result')

    def test_serialization_io_failure_and_interrupt_leave_no_partial_bundle(self):
        for target, failure in (('cp2kkit.density_workflow.json_text', ValueError('synthetic JSON failure')),
                                ('cp2kkit.io.os.fsync', OSError('synthetic disk failure')),
                                ('cp2kkit.io.os.link', KeyboardInterrupt())):
            with self.subTest(target=target), patch(target, side_effect=failure), self.assertRaises(type(failure)):
                write_input(self.structure, replace(self.settings, write_json=True), self.output)
            self.assertEqual(set(self.root.iterdir()), {self.source})

    def test_cli_smoke_reports_every_path_and_no_native_execution(self):
        argv = command_arguments(self.source, -1, self.output, self.settings)
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        for path in bundle_paths(self.settings, self.output):
            self.assertTrue(path.exists())
            self.assertIn(str(path), result.stderr)
        self.assertFalse(Path(str(self.output)+'.json').exists())
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(argv[3:]), 5)

    def test_menu_configures_local_602_then_previews_and_publishes_shared_bundle(self):
        log = TTY()
        lines = '600\n602\n1\n2\n1\n3\n4\n0 1 0 3 0 1\n5\n0\n0\np\n\n0\n\n'
        code = run_interactive(str(self.source), -1, str(self.output), InputSettings(periodic='NONE', write_json=True),
                               stdin=TTY(lines), stdout=log, plain=True)
        self.assertEqual(code, 0)
        self.assertIn('fragment_a preview', log.getvalue())
        self.assertIn('fragment_b preview', log.getvalue())
        self.assertIn('whole 3 (H) -> B:2', log.getvalue())
        self.assertNotIn('Atom indices below', log.getvalue())
        self.assertNotIn('1: O', log.getvalue())
        self.assertEqual(self.output.read_text(), self.generate()[0])
        report = json.loads(Path(str(self.output)+'.json').read_text())
        self.assertTrue(report['settings']['density_difference'])
        self.assertEqual(report['settings']['fragment_a_multiplicity'], 3)
        for path in bundle_paths(replace(self.settings, write_json=True), self.output):
            self.assertIn(str(path.resolve()), log.getvalue())

    def test_other_atom_tables_keep_coordinates(self):
        from cp2kkit.input_editor import atom_table
        from cp2kkit.input_tui import Menu
        for magnetic in (False, True):
            log = TTY()
            atom_table(Menu(TTY(), log, True), {'path': str(self.source), 'frame': -1}, magnetic=magnetic)
            self.assertIn('[angstrom]', log.getvalue())
            self.assertIn('0.00000000', log.getvalue())
            self.assertIn('@1: O' if magnetic else '1: O', log.getvalue())

    def test_menu_six_state_values_are_transactional(self):
        from cp2kkit.input_editor import edit_difference_states
        from cp2kkit.input_tui import Menu
        from dataclasses import asdict
        original = asdict(self.settings)
        values = dict(original)
        log = TTY()
        edit_difference_states(Menu(TTY('-1 1 1 1 -2 1\n'), log, True), values)
        for name, expected in (('charge', -1), ('multiplicity', 1),
                               ('fragment_a_charge', 1), ('fragment_a_multiplicity', 1),
                               ('fragment_b_charge', -2), ('fragment_b_multiplicity', 1)):
            self.assertEqual(values[name], expected)
        for raw in ('0 1 0 1', '0 1 0 1 0 1 2', '0 1 0 1 0 x',
                    '0 1 0 1 0 0', '0 0 0 1 0 1', '0 1 0 -1 0 1', '0 1 0 1 0 1.0',
                    '0 1 1 1 -2 1', '0 1 0 1 auto 1'):
            with self.subTest(raw=raw):
                values = dict(original)
                log = TTY()
                edit_difference_states(Menu(TTY(raw+'\nback\n'), log, True), values)
                self.assertEqual(values, original)
                self.assertIn('All six values unchanged', ' '.join(log.getvalue().split()))
        for raw in ('\n', 'back\n'):
            values = dict(original)
            edit_difference_states(Menu(TTY(raw), TTY(), True), values)
            self.assertEqual(values, original)

    def test_menu_source_change_retains_fragment_selection_and_requires_review(self):
        other = self.root/'one.xyz'
        other.write_text('1\nsynthetic\nHe 0 0 0\n')
        log = TTY()
        run_interactive(str(self.source), -1, str(self.output), self.settings,
                        stdin=TTY(f'201\n{other}\n0\n-10\n'), stdout=log, plain=True)
        self.assertIn('Fragment atom indices were retained, not remapped', log.getvalue())
        self.assertIn('both contain atoms', log.getvalue())
        self.assertFalse(self.output.exists())

    def test_cdd_automatic_output_tracks_toggle_and_preserves_explicit_path(self):
        from cp2kkit.input_editor import automatic_output, edit_difference, edit_source
        from cp2kkit.input_tui import Menu
        from dataclasses import asdict
        values = {**asdict(self.settings), 'path': str(self.source), 'frame': -1,
                  '_auto_output': True, 'density_difference': False, 'output': 'water.inp'}
        edit_difference(Menu(TTY('1\n0\n'), TTY(), True), values)
        self.assertEqual(values['output'], 'water-CDD.inp')
        self.assertEqual(automatic_output(values), 'water-CDD.inp')
        other = self.root/'other.xyz'
        other.write_text(self.source.read_text())
        edit_source(Menu(TTY(str(other)+'\n'), TTY(), True), values, 'path')
        self.assertEqual(values['output'], 'other-CDD.inp')
        edit_difference(Menu(TTY('1\n0\n'), TTY(), True), values)
        self.assertEqual(values['output'], 'other.inp')
        values.update(_auto_output=False, output='custom.inp')
        edit_difference(Menu(TTY('1\n0\n'), TTY(), True), values)
        self.assertEqual(values['output'], 'custom.inp')

    def test_seeded_cdd_automatic_output_name(self):
        from unittest.mock import patch
        log = TTY()
        target = self.root/'water-CDD.inp'
        with patch('cp2kkit.input_editor.write_input', return_value=(target, None, [])) as writer:
            run_interactive(str(self.source), -1, None, self.settings,
                            stdin=TTY('0\n'), stdout=log, plain=True)
        self.assertEqual(writer.call_args.args[2], 'water-CDD.inp')
        self.assertTrue(writer.call_args.args[1].electron_density)

    def test_cdd_main_zero_directly_writes_without_review_or_confirmation(self):
        log = TTY()
        run_interactive(str(self.source), -1, str(self.output), self.settings,
                        stdin=TTY('602\n0\n0\n\n'), stdout=log, plain=True)
        self.assertTrue(self.output.exists())
        self.assertTrue(all(p.exists() for p in bundle_paths(self.settings, self.output)))
        self.assertFalse(Path(str(self.output)+'.json').exists())
        self.assertNotIn('Write new whole/A/B', log.getvalue())
        self.assertNotIn('Sidecar path:', log.getvalue())

    def test_cdd_direct_write_invalid_draft_does_not_publish(self):
        log = TTY()
        run_interactive(str(self.source), -1, str(self.output), replace(self.settings, fragment_a_charge=1),
                        stdin=TTY('0\n\n-10\n'), stdout=log, plain=True)
        self.assertFalse(self.output.exists())
        self.assertIn('total charge must equal', log.getvalue())

    def test_cdd_local_toggle_twice_never_prompts_for_boolean(self):
        from cp2kkit.input_editor import edit_difference
        from cp2kkit.input_tui import Menu
        from dataclasses import asdict
        values = {**asdict(self.settings), 'path': str(self.source), 'frame': -1}
        values['density_difference'] = False
        log = TTY()
        edit_difference(Menu(TTY('1\n1\n0\n'), log, True), values)
        self.assertFalse(values['density_difference'])
        self.assertTrue(values['electron_density'])
        self.assertIn('Enable/disable: True', log.getvalue())
        self.assertNotIn('[y/N]', log.getvalue())

    def test_menu_cancel_eof_decline_and_local_zero_never_publish(self):
        for lines in ('602\n0\n-10\n', '602\nq\n', '602\ncancel\n', '602\n', 'w\nn\n-10\n', 'p\n\n-10\n'):
            with self.subTest(lines=lines):
                run_interactive(str(self.source), -1, str(self.output), self.settings,
                                stdin=TTY(lines), stdout=TTY(), plain=True)
                self.assertEqual(set(self.root.iterdir()), {self.source})


if __name__ == '__main__':
    unittest.main()
