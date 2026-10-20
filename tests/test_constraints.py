"""Fixed-atom contracts against synthetic structures; no CP2K execution."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import build_parser, main
from cp2kkit.constraints import parse_fixed_atoms
from cp2kkit.errors import KitError
from cp2kkit.input_tui import command_arguments, run_interactive
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.structure import Structure, read_structure
from tests.test_input_tui import TTY
from tests.test_structure_formats import CIF


class ConstraintTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root/'water.xyz'
        self.source.write_text('3\nsynthetic\nO 0 0 0\nH 1 0 0\nH 0 1 0\n')
        self.structure = read_structure(self.source)
        self.settings = InputSettings(periodic='NONE', run_type='GEO_OPT')
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def generate(self, structure=None, **kwargs):
        return generate_input(structure or self.structure, replace(self.settings, **kwargs))

    def session(self, lines, **kwargs):
        output = self.root/'menu.inp'
        log = TTY()
        run_interactive(str(self.source), -1, str(output), replace(self.settings, **kwargs),
                        stdin=TTY(lines), stdout=log, plain=True)
        return output, log.getvalue()

    def test_compact_range_parser_and_clear(self):
        self.assertEqual(parse_fixed_atoms('8, 3-5 1'), '1,3-5,8')
        self.assertEqual(parse_fixed_atoms('2-2'), '2')
        for raw in ('off', 'OFF', 'none', '0', ' off '):
            self.assertEqual(parse_fixed_atoms(raw), 'off')

    def test_invalid_syntax_duplicates_and_injection(self):
        for raw in ('', '1,', ',1', '1,,2', '0,1', '-1', '1.5', '3-1', '1-0',
                    '1-2,2', '1,1', '2-3,1-2', '1;2', '1 #comment', '1\n2',
                    '1\x002', '1..3', 'optH', True, [1], None):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_fixed_atoms(raw)

    def test_default_is_unconstrained_and_matches_previous_input_bytes(self):
        text, m = self.generate()
        self.assertNotIn('&CONSTRAINT', text)
        self.assertEqual(text, self.generate(fixed_atoms='0')[0])
        self.assertEqual(m['settings']['fixed_atoms'], 'off')
        self.assertFalse(m['constraints']['enabled'])
        self.assertEqual(m['constraints']['fixed_atoms'], [])
        self.assertIsNone(m['constraints']['components_to_fix'])

    def test_both_tasks_and_all_optimizers_emit_correct_nesting(self):
        for task in ('GEO_OPT', 'CELL_OPT'):
            for optimizer in ('BFGS', 'LBFGS', 'CG'):
                with self.subTest(task=task, optimizer=optimizer):
                    text, m = self.generate(run_type=task, optimizer=optimizer, periodic='XYZ',
                                            cell=(12., 12., 12.), fixed_atoms='3,1')
                    self.assertIn('&CONSTRAINT\n    &FIXED_ATOMS\n      COMPONENTS_TO_FIX XYZ\n', text)
                    self.assertIn('      LIST 1 3\n    &END FIXED_ATOMS\n  &END CONSTRAINT\n  &PRINT', text)
                    self.assertLess(text.index('&END '+task), text.index('  &CONSTRAINT'))
                    self.assertEqual(m['settings']['fixed_atoms'], '1,3')
                    self.assertEqual(m['constraints']['fixed_atoms'], [1, 3])
                    self.assertEqual(m['constraints']['index_base'], 1)
                    self.assertEqual(m['constraints']['coordinate_space'], 'fractional')
                    self.assertEqual(m['constraints']['keyword_reference']['target'], '2026.2')
                    self.assertFalse(m['constraints']['runtime_validated'])

    def test_active_bounds_are_checked_before_range_expansion(self):
        for raw in ('4', '1-4', '1-1000000000000000000000000000000'):
            with self.subTest(raw=raw), self.assertRaisesRegex(KitError, '3 atoms'):
                self.generate(fixed_atoms=raw)

    def test_invalid_api_types_use_domain_errors(self):
        for raw in ([1, 2], (1,), None, 0, True):
            with self.subTest(raw=raw), self.assertRaises(KitError):
                self.generate(fixed_atoms=raw)

    def test_energy_hides_and_retains_selection_without_expansion(self):
        for task in ('ENERGY', 'ENERGY_FORCE'):
            text, m = self.generate(run_type=task, fixed_atoms='1-1000000000000000000000000')
            self.assertNotIn('&MOTION', text)
            self.assertFalse(m['constraints']['enabled'])
            self.assertEqual(m['constraints']['fixed_atoms'], [])
            self.assertEqual(m['settings']['fixed_atoms'], '1-1000000000000000000000000')
            self.assertTrue(any('retained but inactive' in w for w in m['warnings']))

    def test_target_gate_only_for_active_nonempty_constraints(self):
        with self.assertRaisesRegex(KitError, '2026.2'):
            self.generate(fixed_atoms='1', cp2k_version='2024.1')
        self.generate(cp2k_version='2024.1')
        self.generate(run_type='ENERGY', fixed_atoms='1', cp2k_version='2024.1')

    def test_cell_constraint_and_all_fixed_warnings(self):
        _, m = self.generate(fixed_atoms='1-3', run_type='CELL_OPT', periodic='XYZ', cell=(12., 12., 12.))
        self.assertTrue(any('fractional XYZ' in w and 'changing cell' in w for w in m['warnings']))
        self.assertTrue(any('All atoms are fixed' in w for w in m['warnings']))

    def test_constraints_do_not_change_geometry_spin_or_kind_order(self):
        args = dict(magnetism=(('@2', 1.), ('@3', -1.)), multiplicity=1)
        _, before = self.generate(**args)
        _, after = self.generate(fixed_atoms='3,1', **args)
        for key in ('source_structure', 'generated_structure', 'kinds', 'electronic_extensions',
                    'explicit_electron_count', 'method_profile'):
            self.assertEqual(before[key], after[key])
        self.assertEqual(after['constraints']['fixed_atoms'], [1, 3])

    def test_all_electron_uses_same_constraint_writer(self):
        for profile in ('auto', 'native'):
            text, m = self.generate(basis='ae-pob-tzvp', gapw_profile=profile, fixed_atoms='1')
            self.assertIn('METHOD GAPW', text)
            self.assertIn('LIST 1\n', text)
            self.assertEqual(m['constraints']['fixed_atoms'], [1])

    def test_large_selection_repeats_bounded_list_lines(self):
        structure = Structure(['He']*65, [[float(i), 0., 0.] for i in range(65)],
                              None, [False]*3, {'path': 'synthetic.xyz'})
        text, m = self.generate(structure, fixed_atoms='1-65')
        lines = [line for line in text.splitlines() if line.strip().startswith('LIST ')]
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(len(line.split()) <= 21 for line in lines))
        self.assertEqual([int(token) for line in lines for token in line.split()[1:]], list(range(1, 66)))
        self.assertEqual(m['constraints']['fixed_atoms'], list(range(1, 66)))

    def test_config_and_cli_replay_are_equivalent(self):
        settings = replace(self.settings, fixed_atoms='3,1-2')
        text, m = generate_input(self.structure, settings)
        loaded = InputSettings.from_config(json.loads(json.dumps(m)))
        self.assertEqual(generate_input(self.structure, loaded)[0], text)
        parsed = build_parser().parse_args(command_arguments(self.source, -1, 'next.inp', settings)[3:])
        self.assertEqual(parsed.fixed_atoms, '1-2,3')
        self.assertEqual(self.generate(fixed_atoms=parsed.fixed_atoms)[0], text)

    def test_old_config_without_selection_stays_unconstrained(self):
        _, m = self.generate()
        del m['settings']['fixed_atoms']
        self.assertEqual(InputSettings.from_config(m).fixed_atoms, 'off')

    def test_cli_generates_explicit_constraint_and_invalid_bounds_write_nothing(self):
        output = self.root/'cli.inp'
        args = ['generate-input', str(self.source), '-o', str(output), '--periodic', 'NONE',
                '--run-type', 'GEO_OPT', '--fixed-atoms', '1,3']
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 0)
            args[-1] = '9'
            original = output.read_bytes()
            self.assertEqual(main(args), 2)
            self.assertEqual(output.read_bytes(), original)
            output2 = self.root/'invalid.inp'
            args[args.index('-o')+1] = str(output2)
            self.assertEqual(main(args), 2)
        self.assertFalse(output2.exists())
        self.assertFalse(Path(str(output2)+'.json').exists())

    def test_menu_shows_atom_table_and_preserves_enter_and_back(self):
        output, log = self.session('9\n3,1\n9\n\n9\nback\nw\ny\n\n', write_json=True)
        self.assertIn('  1: O ', log)
        self.assertIn('  2: H ', log)
        self.assertIn('  3: H ', log)
        self.assertIn('9. Fixed atoms:', log)
        self.assertIn('Fixed atoms (1-based, fractional XYZ): 1,3; count=2', log)
        m = json.loads(Path(str(output)+'.json').read_text())
        self.assertEqual(m['constraints']['fixed_atoms'], [1, 3])

    def test_menu_zero_clears_and_task_changes_retain_hidden_selection(self):
        output, log = self.session('9\n1\n-1\nENERGY\n9\n-1\nGEO_OPT\n9\n0\n0\ny\n\n')
        self.assertIn('Invalid menu number', log)
        self.assertIn('9. Fixed atoms: 1', log)
        self.assertNotIn('&CONSTRAINT', output.read_text())

    def test_menu_retries_bad_syntax_and_reports_bounds_without_clearing(self):
        output, log = self.session('9\n1,1\n5\nw\n9\n2\nw\ny\n\n')
        self.assertIn('Invalid input:', log)
        self.assertIn('5', log)
        self.assertIn('3 atoms', log)
        self.assertIn('Values retained; no automatic changes', log)
        self.assertIn('LIST 2\n', output.read_text())

    def test_source_change_warns_and_revalidates_retained_indices(self):
        other = self.root/'one.xyz'
        other.write_text('1\nsynthetic\nHe 0 0 0\n')
        output, log = self.session(f'9\n3\ns\n{other}\nw\n9\noff\nw\ny\n\n')
        self.assertIn('not remapped', log)
        self.assertIn('1 atom', log)
        self.assertIn('Fixed atoms: 3', log)
        self.assertNotIn('&CONSTRAINT', output.read_text())

    def test_selected_frame_controls_bounds(self):
        self.source.write_text(self.source.read_text()+'1\nsecond frame\nHe 0 0 0\n')
        first = read_structure(self.source, 0)
        last = read_structure(self.source, 1)
        self.generate(first, fixed_atoms='3')
        with self.assertRaisesRegex(KitError, '1 atom'):
            self.generate(last, fixed_atoms='3')

    def test_cif_selection_uses_expanded_atom_order_not_site_labels(self):
        cif = self.root/'expanded.cif'
        cif.write_text(CIF.replace('_space_group_IT_number 1',
                                  "loop_\n_space_group_symop_operation_xyz\n'x,y,z'\n'-x,-y,-z'"))
        structure = read_structure(cif)
        self.assertEqual(structure.symbols, ['O', 'O'])
        _, m = self.generate(structure, periodic='XYZ', fixed_atoms='2')
        self.assertEqual(m['constraints']['fixed_atoms'], [2])
        self.assertEqual(m['source_structure']['positions'], structure.positions)
        self.assertEqual(m['generated_structure']['symbols'], ['O', 'O'])

    def test_source_constraints_are_never_inherited(self):
        self.structure.source['selective_dynamics'] = [['F', 'F', 'F']]*3
        text, m = self.generate()
        self.assertNotIn('&CONSTRAINT', text)
        self.assertFalse(m['constraints']['enabled'])
        self.assertTrue(any('NOT inherited' in w for w in m['warnings']))
