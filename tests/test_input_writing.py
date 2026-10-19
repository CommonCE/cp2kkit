"""Input-only defaults and narrowly authorized replacement; no calculations."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cli import main
from cp2kkit.errors import KitError, OutputExists
from cp2kkit.input_tui import run_interactive
from cp2kkit.inputgen import InputSettings, generate_input, write_input
from cp2kkit.structure import Structure
from tests.test_input_tui import TTY


class InputWritingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root/'source.xyz'
        self.path.write_text('1\nsynthetic\nO 0 0 0\n')
        self.atom = Structure(['O'], [[0., 0., 0.]], None, None, {'path': str(self.path)})
        self.settings = InputSettings(periodic='NONE')
        self.output = self.root/'new.inp'
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('CP2K_DATA_DIR', None)

    def test_default_writes_only_input_and_returns_null_sidecar(self):
        with patch('cp2kkit.inputgen.json_text', side_effect=AssertionError('JSON disabled')):
            output, sidecar, _ = write_input(self.atom, self.settings, self.output)
        self.assertEqual(output, self.output)
        self.assertIsNone(sidecar)
        self.assertFalse(Path(str(output)+'.json').exists())
        self.assertEqual(output.read_text(), generate_input(self.atom, self.settings)[0])

    def test_regular_inp_is_replaced_with_current_input(self):
        self.output.write_text('old input')
        old_inode = self.output.stat().st_ino
        write_input(self.atom, self.settings, self.output)
        self.assertNotEqual(self.output.stat().st_ino, old_inode)
        self.assertIn('METHOD GPW', self.output.read_text())
        write_input(self.atom, replace(self.settings, cutoff=612.), self.output)
        self.assertIn('CUTOFF [Ry] 612', self.output.read_text())

    def test_disabled_json_keeps_old_sidecar_and_warns(self):
        sidecar = Path(str(self.output)+'.json')
        sidecar.write_text('old metadata')
        self.output.write_text('old input')
        _, returned, warnings = write_input(self.atom, self.settings, self.output)
        self.assertIsNone(returned)
        self.assertEqual(sidecar.read_text(), 'old metadata')
        self.assertTrue(any('earlier input' in w for w in warnings))

    def test_json_is_explicit_and_existing_json_blocks_input_replacement(self):
        settings = replace(self.settings, write_json=True)
        _, sidecar, _ = write_input(self.atom, settings, self.output)
        self.assertEqual(json.loads(sidecar.read_text())['input_text'], self.output.read_text())
        old = self.output.read_bytes()
        with self.assertRaises(OutputExists):
            write_input(self.atom, replace(settings, cutoff=612.), self.output)
        self.assertEqual(self.output.read_bytes(), old)
        self.assertEqual(list(self.root.glob('.*.tmp')), [])

    def test_json_serialization_failure_preserves_existing_input(self):
        self.output.write_text('old input')
        with patch('cp2kkit.inputgen.json_text', side_effect=ValueError('synthetic')):
            with self.assertRaises(ValueError):
                write_input(self.atom, replace(self.settings, write_json=True), self.output)
        self.assertEqual(self.output.read_text(), 'old input')
        self.assertFalse(Path(str(self.output)+'.json').exists())
        self.assertEqual(list(self.root.glob('.*.tmp')), [])

    def test_publication_failure_preserves_old_input_and_removes_new_json(self):
        self.output.write_text('old input')
        with patch('cp2kkit.inputgen.os.replace', side_effect=OSError('synthetic failure')):
            with self.assertRaises(OSError):
                write_input(self.atom, replace(self.settings, write_json=True), self.output)
        self.assertEqual(self.output.read_text(), 'old input')
        self.assertFalse(Path(str(self.output)+'.json').exists())
        self.assertEqual(list(self.root.glob('.*.tmp')), [])

    def test_non_inp_results_cannot_be_overwritten(self):
        for name in ('result.out', 'result.chk', 'result.wfn', 'result.cube', 'result.json', 'result.restart'):
            path = self.root/name
            path.write_text('expensive existing data')
            with self.subTest(name=name), self.assertRaises(OutputExists):
                write_input(self.atom, self.settings, path)
            self.assertEqual(path.read_text(), 'expensive existing data')

    def test_symlinks_and_directories_are_not_replaced(self):
        original = self.root/'existing.out'
        original.write_text('expensive')
        self.output.symlink_to(original)
        with self.assertRaises(OutputExists):
            write_input(self.atom, self.settings, self.output)
        self.assertEqual(original.read_text(), 'expensive')
        self.output.unlink()
        self.output.symlink_to(self.root/'missing')
        with self.assertRaises(OutputExists):
            write_input(self.atom, self.settings, self.output)
        self.output.unlink()
        self.output.symlink_to(self.output)
        with self.assertRaises(OutputExists):
            write_input(self.atom, self.settings, self.output)
        self.output.unlink()
        self.output.mkdir()
        with self.assertRaises(OutputExists):
            write_input(self.atom, self.settings, self.output)

    def test_source_and_source_hardlinks_remain_protected(self):
        self.output.write_text('source content')
        atom = replace(self.atom, source={'path': str(self.output)})
        with self.assertRaises(KitError):
            write_input(atom, self.settings, self.output)
        alias = self.root/'alias.inp'
        os.link(self.output, alias)
        with self.assertRaises(KitError):
            write_input(atom, self.settings, alias)
        self.assertEqual(self.output.read_text(), 'source content')
        from tests.synthetic_cp2k_data import basis_entry
        library = self.root/'basis.inp'
        library.write_text(basis_entry('O', 'DZVP-MOLOPT-SR-GTH-q6'))
        with self.assertRaises(KitError):
            write_input(self.atom, replace(self.settings, basis_files=(str(library),)), library)
        self.assertTrue(library.read_text().startswith('O DZVP-'))

    def test_validation_failure_does_not_touch_existing_input(self):
        self.output.write_text('old input')
        with self.assertRaises(KitError):
            write_input(self.atom, replace(self.settings, multiplicity=2), self.output)
        self.assertEqual(self.output.read_text(), 'old input')

    def test_cli_default_overwrites_inp_without_json(self):
        args = ['generate-input', str(self.path), '--periodic', 'NONE', '-o', str(self.output)]
        with redirect_stderr(io.StringIO()) as log:
            self.assertEqual(main(args), 0)
            self.assertEqual(main(args+['--cutoff', '612']), 0)
        self.assertIn('CUTOFF [Ry] 612', self.output.read_text())
        self.assertNotIn('and None', log.getvalue())
        self.assertFalse(Path(str(self.output)+'.json').exists())

    def test_cli_json_opt_in(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(['generate-input', str(self.path), '--periodic', 'NONE',
                                   '-o', str(self.output), '--write-json']), 0)
        self.assertTrue(Path(str(self.output)+'.json').exists())

    def test_menu_default_input_only_and_confirmation_before_replacement(self):
        self.output.write_text('old input')
        log = TTY()
        run_interactive(str(self.path), -1, str(self.output), self.settings,
                        stdin=TTY('0\n\n-10\n'), stdout=log, plain=True)
        self.assertEqual(self.output.read_text(), 'old input')
        run_interactive(str(self.path), -1, str(self.output), self.settings,
                        stdin=TTY('0\ny\n\n'), stdout=log, plain=True)
        self.assertIn('may be replaced', log.getvalue())
        self.assertFalse(Path(str(self.output)+'.json').exists())
        self.assertIn('JSON output: disabled', log.getvalue())

    def test_menu_132_enables_json(self):
        run_interactive(str(self.path), -1, str(self.output), self.settings,
                        stdin=TTY('132\ny\n0\ny\n\n'), stdout=TTY(), plain=True)
        self.assertTrue(Path(str(self.output)+'.json').exists())

    def test_library_filenames_have_no_quotes(self):
        for basis in ('molopt-sr-dzvp', 'ae-pob-tzvp', 'ae-uzh-svp'):
            text, _ = generate_input(self.atom, replace(self.settings, basis=basis))
            self.assertNotIn('BASIS_SET_FILE_NAME "', text)
            self.assertNotIn('POTENTIAL_FILE_NAME "', text)
            self.assertIn('POTENTIAL_FILE_NAME ', text)
            self.assertIn('BASIS_SET_FILE_NAME ', text)

    def test_multiwfn_grid_emission_for_all_enabled_builtin_profiles(self):
        from cp2kkit.basis_registry import OPTIONS
        for option in OPTIONS:
            if not option.selectable or option.protocol == 'custom':
                continue
            element = 'Fe' if option.id in ('molopt-sr-tzvp', 'molopt-sr-tzv2p') else 'O'
            atom = replace(self.atom, symbols=[element])
            with self.subTest(basis=option.id):
                text, manifest = generate_input(atom, replace(self.settings, basis=option.id))
                five = option.id in {'molopt-tzvp', 'molopt-tzv2p', 'molopt-tzv2px'}
                self.assertEqual('NGRIDS 5' in text, five)
                self.assertEqual('NGRIDS' in text, five)
                self.assertEqual(manifest['method_profile']['ngrids'], 5 if five else None)

    def test_json_flag_api_type_is_checked(self):
        with self.assertRaises(KitError):
            write_input(self.atom, replace(self.settings, write_json='false'), self.output)
