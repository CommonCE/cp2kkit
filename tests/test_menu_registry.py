"""Category/direct routing and isolated numeric namespaces; no scientific execution."""
import io
import json
import re
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.input_editor import FIELDS, applicable_entries, show_settings
from cp2kkit.input_tui import Menu, parse_value, run_interactive
from cp2kkit.inputgen import InputSettings, generate_input
from cp2kkit.menu_registry import BY_NUMBER, BY_TOKEN, CATEGORY_NAMES, ENTRIES, MENU_LAYOUT_VERSION
from cp2kkit.structure import read_structure
from tests.test_input_tui import TTY


class MenuRegistryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root/'water.xyz'
        self.source.write_text('3\nsynthetic\nO 0 0 0\nH 1 0 0\nH 0 1 0\n')
        self.output = self.root/'generated.inp'
        self.settings = InputSettings(periodic='NONE', write_json=True)

    def session(self, lines, **changes):
        log = TTY()
        code = run_interactive(str(self.source), -1, str(self.output), replace(self.settings, **changes),
                               stdin=TTY(lines), stdout=log, plain=True)
        self.assertEqual(code, 0)
        return log.getvalue()

    def manifest(self):
        return json.loads(Path(str(self.output)+'.json').read_text())

    def test_cube_selector_numbered_choices_and_uks_output(self):
        log = self.session('-3\n7\n1\n0\ny\n\n', multiplicity=3)
        self.assertIn('Only implemented output types', log)
        self.assertIn('select 0 or 1', log)
        report = self.manifest()
        self.assertTrue(report['settings']['electron_density'])
        self.assertTrue(report['density_output']['spin_density'])

    def test_cube_none_clears_density_and_spin_requests(self):
        self.session('601\n0\n0\ny\n\n', electron_density=True, spin_density=True, multiplicity=3)
        report = self.manifest()
        self.assertFalse(report['settings']['electron_density'])
        self.assertFalse(report['settings']['spin_density'])
        self.assertFalse(report['density_output']['enabled'])

    def test_cdd_enables_cube_blocks_disabling_and_keeps_on_after_cdd_disabled(self):
        log = self.session('602\n1\n0\n-3\n0\nback\n602\n1\n0\n0\ny\n\n')
        self.assertIn('automatically enabled', log)
        self.assertIn('Cannot disable electron density', log)
        report = self.manifest()
        self.assertFalse(report['settings']['density_difference'])
        self.assertTrue(report['settings']['electron_density'])

    def test_cdd_cli_seed_and_cube_enter_back_keep_output(self):
        from cp2kkit.input_editor import edit_cube_output
        values = asdict(replace(self.settings, density_difference=True))
        for line in ('\n', 'back\n'):
            before = values.copy()
            edit_cube_output(Menu(TTY(line), TTY(), True), values)
            self.assertEqual(values, before)
        log = self.session('-3\nback\n602\n1\n0\n0\ny\n\n', density_difference=True)
        self.assertIn('1 Electron density', log)
        self.assertTrue(self.manifest()['settings']['electron_density'])

    def test_unique_ids_aliases_categories_and_layout_version(self):
        self.assertEqual(len(BY_NUMBER), len(ENTRIES))
        self.assertEqual(len(BY_TOKEN), sum(1+len(e.aliases) for e in ENTRIES))
        self.assertEqual(MENU_LAYOUT_VERSION, 1)
        self.assertEqual(set(CATEGORY_NAMES), {100, 200, 300, 400, 500, 600})
        for entry in ENTRIES:
            if entry.field:
                self.assertIn(entry.field, FIELDS)
            for token in (entry.number, *entry.aliases):
                self.assertIs(BY_TOKEN[str(token)], entry)
        self.assertEqual(BY_TOKEN['112'].field, 'dft_plus_u')
        self.assertEqual(BY_TOKEN['341'].field, 'added_mos')
        for number in ('105', '124', '125', '132', '133', '700', '900', '1000', '304', '604'):
            self.assertNotIn(number, BY_TOKEN)

    def test_direct_edit_does_not_open_category_and_parameter_number_is_literal(self):
        log = self.session('101\n101\n101\n0\n0\ny\n\n')
        self.assertNotIn('=== 100.', log)
        self.assertIn('Total charge [e] (not inherited', log)
        self.assertEqual(self.manifest()['settings']['charge'], 0)
        self.assertEqual(self.manifest()['generator']['menu_layout_version'], 1)

    def test_category_uses_full_ids_and_preserves_origin_after_cross_category_edit(self):
        log = self.session('300\n101\n1\n102\n2\n0\n0\ny\n\n')
        self.assertEqual(log.count('=== 300. Numerical accuracy and SCF ==='), 3)
        self.assertNotIn('=== 100.', log)
        self.assertIn('301. CUTOFF [Ry]:', log)
        self.assertNotIn('  1. CUTOFF', log)
        self.assertEqual(self.manifest()['settings']['charge'], 1)
        self.assertEqual(self.manifest()['settings']['multiplicity'], 2)

    def test_shortcut_and_full_id_share_one_value_and_editor(self):
        log = self.session('4\ndiag\n300\n320\not\n0\n0\ny\n\n')
        self.assertIn('320. SCF algorithm: diag [user edit]', log)
        self.assertIn('4. SCF algorithm: ot [user edit]', log)
        self.assertEqual(self.output.read_text(), generate_input(read_structure(self.source), self.settings)[0])

    def test_category_zero_back_and_write_alias_do_not_publish(self):
        for lines in ('100\n0\n-10\n', '100\nback\n-10\n', '100\nw\n0\n-10\n', '100\n-10\n-10\n'):
            with self.subTest(lines=lines), patch('cp2kkit.input_editor.write_input') as writer:
                self.session(lines)
                writer.assert_not_called()
                self.assertFalse(self.output.exists())
        log = self.session('700\n900\n1000\n-10\n')
        self.assertEqual(log.count('Invalid menu number'), 3)
        self.assertNotIn('=== 700.', log)

    def test_direct_inapplicable_entries_cannot_bypass_visibility(self):
        log = self.session('341\n324\nback\n602\n0\n-10\n')
        self.assertIn('341 (ADDED_MOS) is not applicable', log)
        self.assertIn('602. Charge-density difference', log)
        log = self.session('602\n341\n-10\n', run_type='GEO_OPT')
        self.assertIn('602 (Charge-density difference inputs)', ' '.join(log.split()))
        self.assertNotIn('602 local option', log)

    def test_basis_and_atom_value_numbers_are_not_function_dispatch(self):
        log = self.session('220\n3\n0\ny\n\n')
        self.assertEqual(self.manifest()['settings']['basis'], 'molopt-tzvp')
        self.assertEqual(self.manifest()['basis_selection']['number'], 3)
        self.assertEqual(self.manifest()['settings']['charge'], 0)
        self.assertEqual(parse_value(FIELDS['fixed_atoms'], '101'), '101')
        self.assertEqual(parse_value(FIELDS['fragment_a_indices'], '602'), '602')
        self.assertNotIn('=== 300.', log)

    def test_local_602_does_not_dispatch_global_ids(self):
        log = self.session('602\n101\n0\n-10\n')
        self.assertIn('global function IDs are not active inside 602', log)
        self.assertNotIn('Total charge [e] (not inherited', log)
        self.assertFalse(self.output.exists())

    def test_source_output_project_and_version_controls_use_shared_fields(self):
        new_output = self.root/'new path.inp'
        log = self.session(f'500\n502\n{new_output}\n503\nexplicit\n504\n2025.2\n0\n0\ny\n\n')
        self.assertFalse(self.output.exists())
        report = json.loads(Path(str(new_output)+'.json').read_text())
        self.assertEqual(report['settings']['project'], 'explicit')
        self.assertEqual(report['target_version'], '2025.2')
        self.assertIn('502. Input output path:', log)
        self.assertIn(str(new_output.resolve()), log)

    def test_abandoned_output_edit_does_not_disable_automatic_source_target(self):
        other = self.root/'second.xyz'
        other.write_text(self.source.read_text())
        for answer in ('back', ''):
            log = TTY()
            run_interactive(str(self.source), -1, None, self.settings,
                            stdin=TTY(f'500\n502\n{answer}\n201\n{other}\n0\n-10\n'),
                            stdout=log, plain=True)
            self.assertIn('502. Input output path: second.inp', log.getvalue())
        self.assertEqual(set(self.root.iterdir()), {self.source, other})

    def test_custom_file_alias_pair_abandon_and_explicit_clear_are_transactional(self):
        log = self.session('233\nchanged-file\nback\n234\nauto\n0\ny\n\n',
                           custom_basis_file='retained-file', custom_basis_name='retained-alias')
        settings = self.manifest()['settings']
        self.assertEqual(settings['custom_basis_file'], 'retained-file')
        self.assertEqual(settings['custom_basis_name'], 'retained-alias')
        self.assertIsNone(settings['custom_potential_file'])
        self.assertNotIn('changed-file', log)

    def test_summary_and_full_preview_return_to_the_origin_without_writing(self):
        with patch('cp2kkit.input_editor.write_input') as writer:
            log = self.session('500\n550\n\np\n\n0\n-10\n')
        writer.assert_not_called()
        self.assertEqual(log.count('=== 500. Output, restart and provenance ==='), 3)
        self.assertIn('Reproducible command', log)
        self.assertIn('Input preview (not written)', log)
        self.assertNotIn('\x1b', log)
        self.assertFalse(self.output.exists())

    def test_render_and_dispatch_have_the_same_applicability(self):
        for scf in ('ot', 'diag'):
            for task in ('ENERGY', 'GEO_OPT', 'CELL_OPT'):
                settings = replace(self.settings, scf=scf, run_type=task)
                values = {**asdict(settings), 'path': str(self.source), 'frame': -1,
                          'output': str(self.output), '_edited': set(), '_origins': {}}
                expected = applicable_entries(values)
                for category in CATEGORY_NAMES:
                    stream = io.StringIO()
                    actual, _ = show_settings(Menu(TTY(), stream, plain=True), values, category)
                    self.assertEqual(actual, expected)
                    numbers = {int(n) for n in re.findall(r'^\s+(\d+)\.', stream.getvalue(), re.M)}-{0}
                    self.assertEqual(numbers, {e.number for e in expected if e.category == category})


if __name__ == '__main__':
    unittest.main()
